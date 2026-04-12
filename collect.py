"""
일별 데이터 수집 파이프라인 (GitHub Actions에서 실행)

실행:
    python collect.py [--min-cap 500] [--workers 8] [--output data/scores.csv]
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from crawler.naver_news import get_analyst_report_count, get_news_multiplier
from crawler.pykrx_data import (
    get_52week_position,
    get_all_tickers,
    get_current_pbr,
    get_institutional_buying_5d,
    get_sector_flow_intensity,
    get_volume_multiplier,
)
from crawler.wisereport import get_consensus_data
from scorer import GRADE_COLORS, calculate_scores, get_grade

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# CSV 컬럼 순서
CSV_COLUMNS = [
    "ticker", "name", "market", "sector", "market_cap",
    # 총점
    "total_score", "grade",
    # 카테고리
    "growth_score", "sector_score", "momentum_score", "value_score",
    # 세부 점수
    "d_eps_growth", "d_revenue_cagr", "d_operating_margin",
    "d_sector_flow", "d_analyst_reports", "d_news_multiplier",
    "d_volume_multiplier", "d_week52_position", "d_institutional_buying",
    "d_forward_peg", "d_pbr_ratio",
    # 원시 데이터
    "raw_eps_growth_pct", "raw_revenue_cagr_pct", "raw_operating_margin_trend",
    "raw_volume_multiplier", "raw_week52_position_pct",
    "raw_institutional_buying", "raw_pbr_vs_sector", "raw_forward_peg",
    "raw_sector_flow", "raw_analyst_count", "raw_news_multiplier",
    # 메타
    "last_updated",
]


def collect_ticker(info: dict) -> dict[str, Any]:
    ticker = info["ticker"]
    name   = info["name"]
    logger.info(f"  → {ticker} {name}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── pykrx 데이터 ──
    vol_mul   = get_volume_multiplier(ticker)
    pos_52w   = get_52week_position(ticker)
    inst_buy  = get_institutional_buying_5d(ticker)
    sector_fl = get_sector_flow_intensity(ticker)
    cur_pbr   = info.get("pbr")

    # ── wisereport 컨센서스 ──
    consensus = get_consensus_data(ticker)
    eps_growth    = consensus["eps_growth_pct"]
    rev_cagr      = consensus["revenue_cagr_pct"]
    op_trend      = consensus["operating_margin_trend"]
    fwd_peg       = consensus["forward_peg"]

    # ── 뉴스/리포트 ──
    news_mul     = get_news_multiplier(name)
    analyst_cnt  = get_analyst_report_count(ticker)

    # ── PBR 업종 평균 비율 (단순화: 현재 PBR / 업종 중앙값은 데이터 없으면 None) ──
    pbr_vs_sector = None  # collect.py 레벨에서는 후처리로 계산 가능

    # ── 스코어링 ──
    scores = calculate_scores(
        eps_growth_pct=eps_growth,
        revenue_cagr_pct=rev_cagr,
        operating_margin_trend=op_trend,
        sector_flow_intensity=sector_fl,
        analyst_report_count=analyst_cnt,
        news_multiplier=news_mul,
        volume_multiplier=vol_mul,
        week52_position_pct=pos_52w,
        institutional_buying=inst_buy,
        forward_peg=fwd_peg,
        pbr_vs_sector=pbr_vs_sector,
    )

    d = scores["detail"]
    return {
        "ticker": ticker,
        "name":   name,
        "market": info["market"],
        "sector": info["sector"],
        "market_cap": info["market_cap"],
        "total_score":    scores["total"],
        "grade":          get_grade(scores["total"]),
        "growth_score":   scores["growth"],
        "sector_score":   scores["sector"],
        "momentum_score": scores["momentum"],
        "value_score":    scores["value"],
        # 세부
        "d_eps_growth":          d["eps_growth"],
        "d_revenue_cagr":        d["revenue_cagr"],
        "d_operating_margin":    d["operating_margin"],
        "d_sector_flow":         d["sector_flow"],
        "d_analyst_reports":     d["analyst_reports"],
        "d_news_multiplier":     d["news_multiplier"],
        "d_volume_multiplier":   d["volume_multiplier"],
        "d_week52_position":     d["week52_position"],
        "d_institutional_buying": d["institutional_buying"],
        "d_forward_peg":         d["forward_peg"],
        "d_pbr_ratio":           d["pbr_ratio"],
        # 원시값
        "raw_eps_growth_pct":         eps_growth,
        "raw_revenue_cagr_pct":       rev_cagr,
        "raw_operating_margin_trend": op_trend,
        "raw_volume_multiplier":      vol_mul,
        "raw_week52_position_pct":    pos_52w,
        "raw_institutional_buying":   inst_buy,
        "raw_pbr_vs_sector":          pbr_vs_sector,
        "raw_forward_peg":            fwd_peg,
        "raw_sector_flow":            sector_fl,
        "raw_analyst_count":          analyst_cnt,
        "raw_news_multiplier":        news_mul,
        "last_updated": now,
    }


def run(min_cap: float, workers: int, output: str) -> None:
    logger.info(f"종목 목록 수집 중 (시총 >= {min_cap}억) ...")
    tickers = get_all_tickers(min_cap_억=min_cap)
    logger.info(f"대상 종목: {len(tickers)}개 / workers={workers}")

    results = []
    failed  = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(collect_ticker, info): info for info in tickers}
        for fut in as_completed(futures):
            info = futures[fut]
            try:
                row = fut.result()
                results.append(row)
                logger.info(
                    f"[{row['ticker']}] {row['name']:12s} → "
                    f"총점 {row['total_score']:3d} ({row['grade']})"
                )
            except Exception as e:
                logger.error(f"[{info['ticker']}] 수집 실패: {e}")
                failed.append(info["ticker"])

    # 총점 내림차순 정렬
    results.sort(key=lambda r: r["total_score"], reverse=True)

    # CSV 저장
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"저장 완료 → {output}  (성공 {len(results)}, 실패 {len(failed)})")
    if failed:
        logger.warning(f"실패 종목: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="텐배거 데이터 수집")
    parser.add_argument("--min-cap",  type=float, default=500,             help="최소 시가총액 (억원, 기본 500)")
    parser.add_argument("--workers",  type=int,   default=6,               help="병렬 워커 수 (기본 6)")
    parser.add_argument("--output",   type=str,   default="data/scores.csv", help="출력 CSV 경로")
    args = parser.parse_args()

    run(min_cap=args.min_cap, workers=args.workers, output=args.output)
