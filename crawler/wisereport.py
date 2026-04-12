"""
wisereport (navercomp.wisereport.co.kr) 컨센서스 크롤러

파싱 대상: table.gHead03
  - 매출액 행 → 3년 CAGR 계산
  - EPS 행    → 2년 선행 증가율 계산
  - 영업이익률 행 → 추세 판단

헤더 Year 예: 2022/12A  2023/12A  2024/12E  2025/12E
A = actual, E = estimate
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={ticker}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://navercomp.wisereport.co.kr/",
}

REQUEST_TIMEOUT = 10
RETRY_DELAY    = 1.0


# ──────────────────────────────────────────────
# 저수준 파싱
# ──────────────────────────────────────────────

def _fetch_html(ticker: str) -> Optional[str]:
    url = BASE_URL.format(ticker=ticker)
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            logger.warning(f"[{ticker}] wisereport fetch attempt {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(RETRY_DELAY)
    return None


def _parse_table(html: str) -> Optional[dict]:
    """table.gHead03 에서 연도별 데이터 추출

    Returns:
        {
          "years": ["2022/12A", "2023/12A", "2024/12E", "2025/12E"],
          "rows":  {"매출액": [v1, v2, v3, v4], "EPS": [...], ...}
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.gHead03")
    if table is None:
        # fallback: 다른 클래스명 시도
        table = soup.find("table", class_=re.compile(r"gHead", re.I))
    if table is None:
        logger.debug("wisereport: table.gHead03 not found")
        return None

    rows = table.find_all("tr")
    if not rows:
        return None

    # 헤더 행에서 연도 추출
    header_row = rows[0]
    year_cells = header_row.find_all(["th", "td"])
    years = []
    for cell in year_cells:
        text = cell.get_text(strip=True)
        if re.search(r"\d{4}/\d{2}[AE]", text):
            years.append(text)

    if not years:
        return None

    # 데이터 행 파싱
    data_rows: dict[str, list[Optional[float]]] = {}
    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        label = cells[0].get_text(strip=True)
        values: list[Optional[float]] = []
        for cell in cells[1: len(years) + 1]:
            raw = cell.get_text(strip=True).replace(",", "").replace("%", "")
            try:
                values.append(float(raw))
            except ValueError:
                values.append(None)
        if values:
            data_rows[label] = values

    return {"years": years, "rows": data_rows}


def _extract_year_type(year_str: str) -> str:
    """'2024/12E' → 'E',  '2023/12A' → 'A'"""
    m = re.search(r"([AE])$", year_str.upper())
    return m.group(1) if m else "?"


def _find_row(rows: dict, keywords: list[str]) -> Optional[list]:
    """행 딕셔너리에서 키워드 매칭 행 반환"""
    for key, values in rows.items():
        if any(kw in key for kw in keywords):
            return values
    return None


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────

def get_consensus_data(ticker: str) -> dict:
    """컨센서스 데이터 파싱 후 스코어링에 필요한 값 반환

    Returns:
        {
          "eps_growth_pct":          float | None,   # 2년 선행 EPS 증가율
          "revenue_cagr_pct":        float | None,   # 3년 매출 CAGR
          "operating_margin_trend":  str | None,     # 'maintained'|'improved'|'sharply_improved'
          "forward_eps_1y":          float | None,
          "forward_eps_2y":          float | None,
          "forward_peg":             float | None,   # PEG = PER / EPS성장률 (PER 없으면 None)
        }
    """
    result: dict = {
        "eps_growth_pct":         None,
        "revenue_cagr_pct":       None,
        "operating_margin_trend": None,
        "forward_eps_1y":         None,
        "forward_eps_2y":         None,
        "forward_peg":            None,
    }

    html = _fetch_html(ticker)
    if html is None:
        return result

    parsed = _parse_table(html)
    if parsed is None:
        return result

    years = parsed["years"]
    rows  = parsed["rows"]

    year_types = [_extract_year_type(y) for y in years]
    estimate_indices = [i for i, t in enumerate(year_types) if t == "E"]
    actual_indices   = [i for i, t in enumerate(year_types) if t == "A"]

    # ── EPS 증가율 ──
    eps_row = _find_row(rows, ["EPS", "eps"])
    if eps_row and len(estimate_indices) >= 2:
        i1, i2 = estimate_indices[0], estimate_indices[1]
        e1 = eps_row[i1] if i1 < len(eps_row) else None
        e2 = eps_row[i2] if i2 < len(eps_row) else None
        result["forward_eps_1y"] = e1
        result["forward_eps_2y"] = e2

        # base: 마지막 actual EPS
        if actual_indices:
            base_i = actual_indices[-1]
            base_eps = eps_row[base_i] if base_i < len(eps_row) else None
            if base_eps and base_eps > 0 and e2 is not None:
                growth = (e2 - base_eps) / abs(base_eps) * 100
                result["eps_growth_pct"] = round(growth, 1)

    # ── 매출 CAGR ──
    rev_row = _find_row(rows, ["매출액", "매출", "Revenue"])
    if rev_row and len(actual_indices) >= 2:
        old_i = actual_indices[0]
        new_i = actual_indices[-1]
        n_years = new_i - old_i
        v_old = rev_row[old_i] if old_i < len(rev_row) else None
        v_new = rev_row[new_i] if new_i < len(rev_row) else None
        if v_old and v_new and v_old > 0 and n_years > 0:
            cagr = ((v_new / v_old) ** (1 / n_years) - 1) * 100
            result["revenue_cagr_pct"] = round(cagr, 1)

    # ── 영업이익률 추세 ──
    op_margin_row = _find_row(rows, ["영업이익률", "OPM", "영업마진"])
    if op_margin_row is None:
        # 직접 계산: 영업이익 / 매출액
        op_row  = _find_row(rows, ["영업이익", "OP"])
        if op_row and rev_row:
            op_margin_row = []
            for op, rev in zip(op_row, rev_row):
                if op is not None and rev and rev > 0:
                    op_margin_row.append(op / rev * 100)
                else:
                    op_margin_row.append(None)

    if op_margin_row and actual_indices:
        actual_margins = [
            op_margin_row[i] for i in actual_indices if i < len(op_margin_row)
        ]
        valid = [m for m in actual_margins if m is not None]
        if len(valid) >= 2:
            delta = valid[-1] - valid[0]
            if delta >= 5:
                result["operating_margin_trend"] = "sharply_improved"
            elif delta >= 1:
                result["operating_margin_trend"] = "improved"
            elif delta >= -1:
                result["operating_margin_trend"] = "maintained"

    return result
