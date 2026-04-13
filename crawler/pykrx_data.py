"""
pykrx 기반 수급/모멘텀 데이터 수집

주요 함수:
  get_volume_multiplier(ticker)       → 거래량 배수 (20일 평균 대비)
  get_52week_position(ticker)         → 현재가 / 52주 고점 × 100
  get_institutional_buying_5d(ticker) → 외인+기관 동시 순매수 최근 5일
  get_sector_flow_intensity(ticker)   → 업종 수급 강도 0~10
  get_market_cap(ticker)              → 시가총액 (억원)
  get_current_pbr(ticker)             → 현재 PBR
  get_all_tickers(min_cap_억=500)    → 시총 기준 필터링된 종목 리스트
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from pykrx import stock

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 날짜 헬퍼
# ──────────────────────────────────────────────

def _date_str(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def _trading_window(days_back: int) -> tuple[str, str]:
    """오늘 기준으로 calendar days를 넉넉히 잡아 충분한 거래일 확보"""
    end = datetime.today()
    start = end - timedelta(days=days_back)
    return _date_str(start), _date_str(end)



_cached_trading_date = None


def _last_trading_date():
    """가장 최근 거래일 날짜 반환 (주말/공휴일 자동 처리)"""
    global _cached_trading_date
    if _cached_trading_date:
        return _cached_trading_date
    d = datetime.today()
    for _ in range(10):
        if d.weekday() < 5:
            candidate = d.strftime("%Y%m%d")
            try:
                df = stock.get_market_cap_by_ticker(candidate, "KOSPI")
                if df is not None and not df.empty:
                    _cached_trading_date = candidate
                    return candidate
            except Exception:
                pass
        d -= timedelta(days=1)
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    _cached_trading_date = d.strftime("%Y%m%d")
    return _cached_trading_date


def _last_n_trading_days(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """거래량 > 0 행만 걸러 마지막 n거래일 반환"""
    valid = df[df.get("거래량", df.iloc[:, 0]) > 0] if "거래량" in df.columns else df
    return valid.tail(n)


# ──────────────────────────────────────────────
# 거래량 배수
# ──────────────────────────────────────────────

def get_volume_multiplier(ticker: str) -> Optional[float]:
    """최근 거래일 거래량 / 20일 평균 거래량"""
    try:
        start, end = _trading_window(60)
        df = stock.get_market_ohlcv_by_date(start, end, ticker)
        if df is None or df.empty:
            return None
        df = df[df["거래량"] > 0]
        if len(df) < 2:
            return None
        recent_vol = float(df["거래량"].iloc[-1])
        avg_vol    = float(df["거래량"].iloc[:-1].tail(20).mean())
        if avg_vol == 0:
            return None
        return round(recent_vol / avg_vol, 2)
    except Exception as e:
        logger.warning(f"[{ticker}] volume_multiplier: {e}")
        return None


# ──────────────────────────────────────────────
# 52주 고점 대비 위치
# ──────────────────────────────────────────────

def get_52week_position(ticker: str) -> Optional[float]:
    """현재가 / 52주 고가 × 100  (단위: %)"""
    try:
        start, end = _trading_window(380)
        df = stock.get_market_ohlcv_by_date(start, end, ticker)
        if df is None or df.empty:
            return None
        df = df[df["거래량"] > 0]
        if df.empty:
            return None
        high_52w     = float(df["고가"].max())
        current_price = float(df["종가"].iloc[-1])
        if high_52w == 0:
            return None
        return round(current_price / high_52w * 100, 2)
    except Exception as e:
        logger.warning(f"[{ticker}] 52week_position: {e}")
        return None


# ──────────────────────────────────────────────
# 외인+기관 동시 순매수 (최근 5거래일)
# ──────────────────────────────────────────────

def _get_net_buying_by_investor(ticker: str, investor: str, start: str, end: str) -> Optional[pd.Series]:
    """pykrx: 특정 투자자의 종목별 일별 순매수 시리즈 반환"""
    try:
        # get_market_trading_volume_by_date 는 매수/매도 거래량 반환
        # 순매수 = 매수 - 매도
        df = stock.get_market_trading_volume_by_date(start, end, ticker)
        if df is None or df.empty:
            return None
        # 컬럼: ['매도', '매수', '순매수'] or similar
        if "순매수" in df.columns:
            return df["순매수"]
        return None
    except Exception:
        return None


def get_institutional_buying_5d(ticker: str) -> Optional[bool]:
    """최근 5거래일 동안 외국인 AND 기관 모두 순매수 누적 > 0 이면 True"""
    try:
        start, end = _trading_window(21)

        # 외국인 일별 순매수
        df_f = stock.get_market_trading_value_by_date(start, end, ticker)
        # pykrx v1.x 반환 컬럼 예: ['매도거래대금', '매수거래대금', '순매수거래대금']
        # 투자자별 분리는 get_market_net_purchases_of_equities_by_ticker 사용
        # → 시장 전체 리턴이므로 해당 종목 행만 추출

        end_trading = df_f.index[-1].strftime("%Y%m%d") if df_f is not None and not df_f.empty else end

        # 최근 5거래일 날짜 리스트
        recent_dates: list[str] = []
        if df_f is not None and not df_f.empty:
            valid_idx = df_f.index[-5:]
            recent_dates = [d.strftime("%Y%m%d") for d in valid_idx]

        if not recent_dates:
            return None

        market = _guess_market(ticker)
        foreign_net = 0.0
        institution_net = 0.0

        for d in recent_dates:
            try:
                f_df = stock.get_market_net_purchases_of_equities_by_ticker(d, market, "외국인")
                if f_df is not None and ticker in f_df.index:
                    # 컬럼 이름이 다를 수 있으므로 마지막 컬럼(순매수) 사용
                    foreign_net += float(f_df.loc[ticker].iloc[-1])
            except Exception:
                pass
            try:
                i_df = stock.get_market_net_purchases_of_equities_by_ticker(d, market, "기관합계")
                if i_df is not None and ticker in i_df.index:
                    institution_net += float(i_df.loc[ticker].iloc[-1])
            except Exception:
                pass

        return foreign_net > 0 and institution_net > 0

    except Exception as e:
        logger.warning(f"[{ticker}] institutional_buying_5d: {e}")
        return None


def _guess_market(ticker: str) -> str:
    """종목코드로 시장 추정 (정확하지 않으면 KOSPI 우선)"""
    try:
        kospi = stock.get_market_ticker_list(market="KOSPI")
        return "KOSPI" if ticker in kospi else "KOSDAQ"
    except Exception:
        return "KOSPI"


# ──────────────────────────────────────────────
# 업종 수급 강도 (0~10)
# ──────────────────────────────────────────────

def get_sector_flow_intensity(ticker: str) -> Optional[float]:
    """업종 내 외인+기관 순매수 강도를 0~10 스케일로 반환

    방법: 최근 1거래일 기준 동일 업종 종목들의 외인+기관 순매수
          상위 몇 % 인지를 0~10으로 정규화
    """
    try:
        today = _last_trading_date()
        market = _guess_market(ticker)

        # 업종명 조회
        sector_name = _get_sector_name(ticker, market)
        if sector_name is None:
            return None

        # 업종 내 모든 종목 수급
        f_df = stock.get_market_net_purchases_of_equities_by_ticker(today, market, "외국인")
        i_df = stock.get_market_net_purchases_of_equities_by_ticker(today, market, "기관합계")

        if f_df is None or i_df is None:
            return None

        combined = f_df.iloc[:, -1] + i_df.reindex(f_df.index).iloc[:, -1].fillna(0)

        if ticker not in combined.index:
            return None

        rank_pct = (combined < combined[ticker]).mean()  # 0~1
        return round(rank_pct * 10, 1)

    except Exception as e:
        logger.warning(f"[{ticker}] sector_flow_intensity: {e}")
        return None


def _get_sector_name(ticker: str, market: str) -> Optional[str]:
    try:
        df = stock.get_market_sector_classifications(_last_trading_date(), market)
        if df is not None and ticker in df.index:
            return str(df.loc[ticker, "업종명"])
        return None
    except Exception:
        return None


# ──────────────────────────────────────────────
# 시가총액 / PBR
# ──────────────────────────────────────────────

def get_market_cap(ticker: str) -> Optional[float]:
    """시가총액 (억원)"""
    try:
        today = _last_trading_date()
        market = _guess_market(ticker)
        df = stock.get_market_fundamental_by_ticker(today, market)
        if df is None or ticker not in df.index:
            return None
        cap = stock.get_market_cap_by_ticker(today, market)
        if cap is None or ticker not in cap.index:
            return None
        return round(float(cap.loc[ticker, "시가총액"]) / 1e8, 0)
    except Exception as e:
        logger.warning(f"[{ticker}] market_cap: {e}")
        return None


def get_current_pbr(ticker: str) -> Optional[float]:
    """현재 PBR"""
    try:
        today = _last_trading_date()
        market = _guess_market(ticker)
        df = stock.get_market_fundamental_by_ticker(today, market)
        if df is None or ticker not in df.index:
            return None
        return float(df.loc[ticker, "PBR"])
    except Exception as e:
        logger.warning(f"[{ticker}] current_pbr: {e}")
        return None


# ──────────────────────────────────────────────
# 전체 종목 리스트 (시총 필터)
# ──────────────────────────────────────────────

def get_all_tickers(min_cap_억: float = 500) -> list[dict]:
    """KOSPI+KOSDAQ 시총 min_cap_억 억원 이상 종목 반환

    Returns:
        [{"ticker": "005930", "name": "삼성전자", "market": "KOSPI",
          "market_cap": 3000000, "sector": "전기전자"}, ...]
    """
    today = _last_trading_date()
    result = []

    for market in ("KOSPI", "KOSDAQ"):
        try:
            cap_df  = stock.get_market_cap_by_ticker(today, market)
            fund_df = stock.get_market_fundamental_by_ticker(today, market)

            if cap_df is None or cap_df.empty:
                continue

            # 시총 필터
            cap_df["시가총액_억"] = cap_df["시가총액"] / 1e8
            filtered = cap_df[cap_df["시가총액_억"] >= min_cap_억]

            # 종목명
            try:
                names = {t: stock.get_market_ticker_name(t) for t in filtered.index}
            except Exception:
                names = {}

            # 업종
            try:
                sector_df = stock.get_market_sector_classifications(today, market)
            except Exception:
                sector_df = None

            for ticker in filtered.index:
                entry: dict = {
                    "ticker":     ticker,
                    "name":       names.get(ticker, ticker),
                    "market":     market,
                    "market_cap": round(float(filtered.loc[ticker, "시가총액_억"]), 0),
                    "sector":     "",
                    "pbr":        None,
                }
                if sector_df is not None and ticker in sector_df.index:
                    entry["sector"] = str(sector_df.loc[ticker, "업종명"])
                if fund_df is not None and ticker in fund_df.index:
                    try:
                        entry["pbr"] = float(fund_df.loc[ticker, "PBR"])
                    except Exception:
                        pass
                result.append(entry)

        except Exception as e:
            logger.error(f"[{market}] get_all_tickers: {e}")

    return result
