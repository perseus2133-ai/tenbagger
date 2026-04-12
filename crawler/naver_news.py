"""
네이버 뉴스 빈도 크롤러

뉴스 언급 배수 = 최근 30일 기사 수 / (최근 90일 기사 수 / 3)
  → 3개월 월 평균 대비 현재 월 배수
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://search.naver.com/",
}

REQUEST_TIMEOUT = 8
RETRY_DELAY    = 0.5


def _naver_news_count(query: str, period: str) -> Optional[int]:
    """
    period: '1m' = 1개월, '3m' = 3개월
    반환: 검색 결과 수 (None = 실패)
    """
    encoded = urllib.parse.quote(query)
    url = (
        f"https://search.naver.com/search.naver"
        f"?where=news&query={encoded}&nso=so:dd,p:{period}&start=1"
    )
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 총 건수 파싱: "1,234건" 형태
            total_el = soup.select_one(".total_count, .sc_new .info_num")
            if total_el is None:
                # 다른 선택자 시도
                total_el = soup.find(string=re.compile(r"\d[\d,]*건"))

            if total_el:
                raw = str(total_el)
                m = re.search(r"([\d,]+)건", raw)
                if m:
                    return int(m.group(1).replace(",", ""))

            # fallback: 결과 아이템 개수로 추정 (최대 10개/페이지)
            items = soup.select(".news_area, .list_news .bx")
            return len(items) if items else 0

        except Exception as e:
            logger.warning(f"naver_news_count({query}, {period}) attempt {attempt+1}: {e}")
            if attempt == 0:
                time.sleep(RETRY_DELAY)
    return None


def get_news_multiplier(company_name: str) -> Optional[float]:
    """뉴스 언급 배수 (최근 1개월 / 3개월 월평균)

    Args:
        company_name: 종목명 (예: "삼성전자")

    Returns:
        배수 (float) or None (크롤링 실패)
    """
    try:
        count_1m = _naver_news_count(company_name, "1m")
        count_3m = _naver_news_count(company_name, "3m")

        if count_1m is None or count_3m is None:
            return None

        # 3개월 월 평균
        monthly_avg = count_3m / 3.0
        if monthly_avg == 0:
            return None

        multiplier = count_1m / monthly_avg
        return round(multiplier, 2)

    except Exception as e:
        logger.warning(f"[{company_name}] news_multiplier: {e}")
        return None


def get_analyst_report_count(ticker: str) -> Optional[int]:
    """네이버 증권 리서치 페이지에서 최근 1분기(90일) 신규 리포트 수 파싱

    URL: https://finance.naver.com/research/company_list.naver?&page=1
    각 행의 종목코드로 필터링
    """
    count = 0
    try:
        for page in range(1, 6):  # 최대 5페이지
            url = (
                f"https://finance.naver.com/research/company_list.naver"
                f"?searchType=itemCode&itemCode={ticker}&page={page}"
            )
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")

            rows = soup.select("table.type_1 tr")
            if not rows:
                break

            page_count = 0
            for row in rows:
                tds = row.find_all("td")
                if not tds:
                    continue
                # 날짜 셀 확인 (보통 마지막 또는 앞에서 두번째)
                date_cell = None
                for td in reversed(tds):
                    text = td.get_text(strip=True)
                    if re.match(r"\d{2}\.\d{2}\.\d{2}", text):
                        date_cell = text
                        break
                if date_cell is None:
                    continue
                # 90일 이내 여부 확인 (YY.MM.DD)
                import datetime
                try:
                    dt = datetime.datetime.strptime(date_cell, "%y.%m.%d")
                    if (datetime.datetime.today() - dt).days <= 90:
                        count += 1
                        page_count += 1
                except ValueError:
                    pass

            if page_count == 0:
                break  # 이 페이지에 90일 이내 리포트 없으면 종료

        return count
    except Exception as e:
        logger.warning(f"[{ticker}] analyst_report_count: {e}")
        return None
