"""
텐배거 스코어링 엔진 — 순수 함수 모음 (100점 만점)

카테고리별 배점:
  실적 성장성  40점  (EPS증가율 20 + 매출CAGR 10 + 영업이익률추세 10)
  섹터 패러다임 25점  (업종수급 10 + 애널리스트 8 + 뉴스 7)
  수급/모멘텀  20점  (거래량 10 + 52주위치 5 + 기관동시 5)
  밸류에이션   15점  (PEG 8 + PBR비율 7)
"""

from __future__ import annotations
from typing import Optional


# ──────────────────────────────────────────────
# 1. 실적 성장성 (40점)
# ──────────────────────────────────────────────

def score_eps_growth(eps_growth_pct: Optional[float]) -> int:
    """2년 선행 EPS 증가율 → 0~20점"""
    if eps_growth_pct is None:
        return 0
    if eps_growth_pct >= 300:
        return 20
    if eps_growth_pct >= 200:
        return 18
    if eps_growth_pct >= 100:
        return 12
    return 0


def score_revenue_cagr(cagr_pct: Optional[float]) -> int:
    """3년 매출 CAGR → 0~10점"""
    if cagr_pct is None:
        return 0
    if cagr_pct >= 40:
        return 10
    if cagr_pct >= 30:
        return 8
    if cagr_pct >= 20:
        return 6
    return 0


def score_operating_margin_trend(trend: Optional[str]) -> int:
    """영업이익률 추세 → 0~10점
    trend: 'maintained' | 'improved' | 'sharply_improved'
    """
    if trend is None:
        return 0
    return {"maintained": 4, "improved": 7, "sharply_improved": 10}.get(trend, 0)


# ──────────────────────────────────────────────
# 2. 섹터 패러다임 (25점)
# ──────────────────────────────────────────────

def score_sector_flow(flow_intensity: Optional[float]) -> int:
    """업종 외인+기관 순매수 강도 (0~10 스케일) → 0~10점"""
    if flow_intensity is None:
        return 0
    return min(10, max(0, round(flow_intensity)))


def score_analyst_reports(count: Optional[int]) -> int:
    """분기 신규 애널리스트 리포트 수 → 0~8점"""
    if count is None:
        return 0
    if count >= 6:
        return 8
    if count >= 4:
        return 6
    if count >= 2:
        return 4
    if count >= 1:
        return 2
    return 0


def score_news_multiplier(multiplier: Optional[float]) -> int:
    """뉴스 언급 배수 (3개월 평균 대비) → 0~7점"""
    if multiplier is None:
        return 0
    if multiplier >= 5:
        return 7
    if multiplier >= 3:
        return 5
    if multiplier >= 2:
        return 3
    if multiplier >= 1.5:
        return 1
    return 0


# ──────────────────────────────────────────────
# 3. 수급/모멘텀 (20점)
# ──────────────────────────────────────────────

def score_volume_multiplier(multiplier: Optional[float]) -> int:
    """거래량배수 (20일 평균 대비) → 0~10점"""
    if multiplier is None:
        return 0
    if multiplier >= 10:
        return 10
    if multiplier >= 7:
        return 8
    if multiplier >= 5:
        return 6
    if multiplier >= 3:
        return 4
    if multiplier >= 2:
        return 2
    return 0


def score_52week_position(position_pct: Optional[float]) -> int:
    """현재가/52주고점 × 100 → 80~95% 구간이면 5점, 나머지 0점"""
    if position_pct is None:
        return 0
    return 5 if 80.0 <= position_pct <= 95.0 else 0


def score_institutional_buying(is_buying: Optional[bool]) -> int:
    """외인+기관 동시 순매수 최근 5일 → 5점 or 0점"""
    if is_buying is None:
        return 0
    return 5 if is_buying else 0


# ──────────────────────────────────────────────
# 4. 밸류에이션 (15점)
# ──────────────────────────────────────────────

def score_forward_peg(peg: Optional[float]) -> int:
    """Forward PEG → 0~8점"""
    if peg is None or peg <= 0:
        return 0
    if peg <= 0.5:
        return 8
    if peg <= 0.8:
        return 6
    if peg <= 1.0:
        return 4
    if peg <= 1.5:
        return 2
    return 0


def score_pbr_ratio(pbr_vs_sector: Optional[float]) -> int:
    """현재PBR / 업종평균PBR → 0~7점"""
    if pbr_vs_sector is None or pbr_vs_sector <= 0:
        return 0
    if pbr_vs_sector <= 0.5:
        return 7
    if pbr_vs_sector <= 0.7:
        return 5
    if pbr_vs_sector <= 0.9:
        return 3
    return 0


# ──────────────────────────────────────────────
# 종합 계산
# ──────────────────────────────────────────────

def calculate_scores(
    eps_growth_pct: Optional[float] = None,
    revenue_cagr_pct: Optional[float] = None,
    operating_margin_trend: Optional[str] = None,
    sector_flow_intensity: Optional[float] = None,
    analyst_report_count: Optional[int] = None,
    news_multiplier: Optional[float] = None,
    volume_multiplier: Optional[float] = None,
    week52_position_pct: Optional[float] = None,
    institutional_buying: Optional[bool] = None,
    forward_peg: Optional[float] = None,
    pbr_vs_sector: Optional[float] = None,
) -> dict:
    """모든 입력값을 받아 카테고리별 · 상세 점수 딕셔너리 반환"""
    s_eps     = score_eps_growth(eps_growth_pct)
    s_cagr    = score_revenue_cagr(revenue_cagr_pct)
    s_margin  = score_operating_margin_trend(operating_margin_trend)
    s_sector  = score_sector_flow(sector_flow_intensity)
    s_analyst = score_analyst_reports(analyst_report_count)
    s_news    = score_news_multiplier(news_multiplier)
    s_vol     = score_volume_multiplier(volume_multiplier)
    s_52w     = score_52week_position(week52_position_pct)
    s_inst    = score_institutional_buying(institutional_buying)
    s_peg     = score_forward_peg(forward_peg)
    s_pbr     = score_pbr_ratio(pbr_vs_sector)

    growth   = s_eps + s_cagr + s_margin          # max 40
    sector   = s_sector + s_analyst + s_news       # max 25
    momentum = s_vol + s_52w + s_inst              # max 20
    value    = s_peg + s_pbr                       # max 15
    total    = growth + sector + momentum + value  # max 100

    return {
        "total": total,
        "growth": growth,
        "sector": sector,
        "momentum": momentum,
        "value": value,
        "detail": {
            "eps_growth":          s_eps,
            "revenue_cagr":        s_cagr,
            "operating_margin":    s_margin,
            "sector_flow":         s_sector,
            "analyst_reports":     s_analyst,
            "news_multiplier":     s_news,
            "volume_multiplier":   s_vol,
            "week52_position":     s_52w,
            "institutional_buying": s_inst,
            "forward_peg":         s_peg,
            "pbr_ratio":           s_pbr,
        },
    }


def get_grade(total: int) -> str:
    if total >= 85:
        return "텐배거 후보"
    if total >= 70:
        return "강력 후보"
    if total >= 55:
        return "유망 후보"
    if total >= 40:
        return "관심 종목"
    return "제외"


GRADE_COLORS = {
    "텐배거 후보": "#FF4444",
    "강력 후보":   "#FF8C00",
    "유망 후보":   "#FFD700",
    "관심 종목":   "#44AA44",
    "제외":        "#888888",
}


def get_grade_color(total: int) -> str:
    return GRADE_COLORS[get_grade(total)]


# ──────────────────────────────────────────────
# 점수 라벨 (UI 표시용)
# ──────────────────────────────────────────────

DETAIL_LABELS = {
    "eps_growth":           ("EPS 증가율",        20),
    "revenue_cagr":         ("매출 CAGR",         10),
    "operating_margin":     ("영업이익률 추세",   10),
    "sector_flow":          ("업종 수급 강도",    10),
    "analyst_reports":      ("애널리스트 리포트",  8),
    "news_multiplier":      ("뉴스 언급 배수",     7),
    "volume_multiplier":    ("거래량 배수",        10),
    "week52_position":      ("52주 고점 위치",      5),
    "institutional_buying": ("외인+기관 동시매수",  5),
    "forward_peg":          ("Forward PEG",        8),
    "pbr_ratio":            ("PBR/업종평균",        7),
}
