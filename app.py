"""
텐배거 스코어링 Streamlit 앱

실행:
    streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from scorer import DETAIL_LABELS, GRADE_COLORS, get_grade, get_grade_color

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

DATA_PATH = Path(__file__).parent / "data" / "scores.csv"

GRADE_ORDER = ["텐배거 후보", "강력 후보", "유망 후보", "관심 종목", "제외"]

CATEGORY_MAX = {
    "growth_score":   40,
    "sector_score":   25,
    "momentum_score": 20,
    "value_score":    15,
}

CATEGORY_LABELS = {
    "growth_score":   "실적 성장성 (40점)",
    "sector_score":   "섹터 패러다임 (25점)",
    "momentum_score": "수급/모멘텀 (20점)",
    "value_score":    "밸류에이션 (15점)",
}

st.set_page_config(
    page_title="텐배거 스코어링",
    page_icon="🚀",
    layout="wide",
)


# ──────────────────────────────────────────────
# 데이터 로드
# ──────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(DATA_PATH, dtype={"ticker": str})
    return df


def grade_badge(grade: str) -> str:
    color = GRADE_COLORS.get(grade, "#888888")
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:0.85em">{grade}</span>'


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def main() -> None:
    st.title("🚀 텐배거 스코어링 시스템")

    df = load_data()

    if df.empty:
        st.warning(
            "데이터가 없습니다.  \n"
            "`python collect.py` 를 실행하거나 GitHub Actions 결과를 기다려 주세요."
        )
        return

    # 마지막 수집 시각
    if "last_updated" in df.columns:
        last_time = df["last_updated"].max()
        st.caption(f"📅 마지막 데이터 수집: **{last_time}**")

    # ── 사이드바 필터 ──
    with st.sidebar:
        st.header("필터")

        min_score = st.slider("최소 총점", 0, 100, 40, step=5)

        all_grades = [g for g in GRADE_ORDER if g != "제외"]
        selected_grades = st.multiselect(
            "등급",
            options=all_grades,
            default=["텐배거 후보", "강력 후보", "유망 후보", "관심 종목"],
        )

        markets = ["전체"] + sorted(df["market"].dropna().unique().tolist())
        selected_market = st.selectbox("시장", markets)

        sectors = ["전체"] + sorted(df["sector"].dropna().unique().tolist())
        selected_sector = st.selectbox("업종", sectors)

        if "market_cap" in df.columns:
            cap_min = int(df["market_cap"].min() or 0)
            cap_max = int(df["market_cap"].max() or 100000)
            cap_range = st.slider(
                "시가총액 (억원)",
                min_value=cap_min,
                max_value=cap_max,
                value=(cap_min, cap_max),
                step=100,
            )
        else:
            cap_range = None

        st.markdown("---")
        if st.button("🔄 데이터 새로고침"):
            st.cache_data.clear()
            st.rerun()

    # ── 필터 적용 ──
    filtered = df.copy()
    filtered = filtered[filtered["total_score"] >= min_score]
    if selected_grades:
        filtered = filtered[filtered["grade"].isin(selected_grades)]
    if selected_market != "전체":
        filtered = filtered[filtered["market"] == selected_market]
    if selected_sector != "전체":
        filtered = filtered[filtered["sector"] == selected_sector]
    if cap_range and "market_cap" in filtered.columns:
        filtered = filtered[
            (filtered["market_cap"] >= cap_range[0]) &
            (filtered["market_cap"] <= cap_range[1])
        ]

    filtered = filtered.sort_values("total_score", ascending=False).reset_index(drop=True)

    # ── 요약 지표 ──
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("전체 종목", len(df))
    col2.metric("필터 결과", len(filtered))
    col3.metric("텐배거 후보", len(df[df["grade"] == "텐배거 후보"]))
    col4.metric("강력 후보",   len(df[df["grade"] == "강력 후보"]))

    st.markdown("---")

    # ── 등급별 탭 ──
    tab_all, *tab_grades = st.tabs(
        ["전체"] + [g for g in GRADE_ORDER if g in filtered["grade"].values]
    )

    def render_table(data: pd.DataFrame, tab) -> None:
        with tab:
            if data.empty:
                st.info("해당 조건의 종목이 없습니다.")
                return

            display_cols = ["ticker", "name", "sector", "market_cap",
                            "total_score", "grade",
                            "growth_score", "sector_score", "momentum_score", "value_score"]
            display_cols = [c for c in display_cols if c in data.columns]
            show = data[display_cols].copy()

            # 컬럼 한글 레이블
            rename = {
                "ticker":         "종목코드",
                "name":           "종목명",
                "sector":         "업종",
                "market_cap":     "시총(억)",
                "total_score":    "총점",
                "grade":          "등급",
                "growth_score":   "성장성",
                "sector_score":   "섹터",
                "momentum_score": "모멘텀",
                "value_score":    "밸류",
            }
            show = show.rename(columns=rename)

            st.dataframe(
                show,
                use_container_width=True,
                height=450,
                column_config={
                    "총점": st.column_config.ProgressColumn(
                        "총점", min_value=0, max_value=100, format="%d"
                    ),
                    "성장성": st.column_config.ProgressColumn(
                        "성장성", min_value=0, max_value=40, format="%d"
                    ),
                    "섹터": st.column_config.ProgressColumn(
                        "섹터", min_value=0, max_value=25, format="%d"
                    ),
                    "모멘텀": st.column_config.ProgressColumn(
                        "모멘텀", min_value=0, max_value=20, format="%d"
                    ),
                    "밸류": st.column_config.ProgressColumn(
                        "밸류", min_value=0, max_value=15, format="%d"
                    ),
                    "등급": st.column_config.TextColumn("등급"),
                },
                hide_index=True,
            )

    render_table(filtered, tab_all)
    for grade, tab in zip(
        [g for g in GRADE_ORDER if g in filtered["grade"].values], tab_grades
    ):
        render_table(filtered[filtered["grade"] == grade], tab)

    # ── 종목 상세 ──
    st.markdown("---")
    st.subheader("종목 상세 분석")

    if filtered.empty:
        st.info("분석할 종목이 없습니다.")
        return

    ticker_options = (
        filtered["ticker"].astype(str) + " " + filtered["name"].astype(str)
    ).tolist()
    selected = st.selectbox("종목 선택", ticker_options)

    if selected:
        sel_ticker = selected.split(" ")[0]
        row = filtered[filtered["ticker"] == sel_ticker].iloc[0]

        # 종목 헤더
        grade_color = GRADE_COLORS.get(row["grade"], "#888")
        total = int(row["total_score"])

        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        c1.markdown(
            f"### {row['name']} `{row['ticker']}`  \n"
            f"업종: {row.get('sector', '-')} · {row.get('market', '-')} · "
            f"시총 {row.get('market_cap', '-')}억"
        )
        c2.markdown(
            f"<div style='font-size:2.5rem;font-weight:bold;color:{grade_color}'>{total}점</div>",
            unsafe_allow_html=True,
        )
        c3.markdown(
            f"<div style='padding-top:0.6rem'>{grade_badge(row['grade'])}</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # 카테고리별 점수 바
        import plotly.graph_objects as go

        cat_labels = list(CATEGORY_LABELS.values())
        cat_scores = [
            int(row.get("growth_score", 0)),
            int(row.get("sector_score", 0)),
            int(row.get("momentum_score", 0)),
            int(row.get("value_score", 0)),
        ]
        cat_maxes = [40, 25, 20, 15]
        cat_colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]

        fig_cat = go.Figure()
        for label, score, max_v, color in zip(cat_labels, cat_scores, cat_maxes, cat_colors):
            fig_cat.add_trace(go.Bar(
                x=[score],
                y=[label],
                orientation="h",
                marker_color=color,
                text=f"{score}/{max_v}",
                textposition="outside",
                name=label,
            ))
        fig_cat.update_layout(
            title="카테고리별 점수",
            xaxis=dict(range=[0, 45], title="점수"),
            showlegend=False,
            height=220,
            margin=dict(l=0, r=60, t=40, b=20),
        )
        st.plotly_chart(fig_cat, use_container_width=True)

        # 세부 점수 바
        detail_keys = list(DETAIL_LABELS.keys())
        detail_names = [DETAIL_LABELS[k][0] for k in detail_keys]
        detail_maxes = [DETAIL_LABELS[k][1] for k in detail_keys]
        detail_scores = [int(row.get(f"d_{k}", 0)) for k in detail_keys]

        fig_det = go.Figure()
        fig_det.add_trace(go.Bar(
            x=detail_scores,
            y=detail_names,
            orientation="h",
            marker_color=[
                "#4C72B0" if s == m else "#7BA5D6" if s > 0 else "#E0E0E0"
                for s, m in zip(detail_scores, detail_maxes)
            ],
            text=[f"{s}/{m}" for s, m in zip(detail_scores, detail_maxes)],
            textposition="outside",
        ))
        fig_det.update_layout(
            title="세부 항목별 점수",
            xaxis=dict(range=[0, 25], title="점수"),
            showlegend=False,
            height=420,
            margin=dict(l=0, r=60, t=40, b=20),
        )
        st.plotly_chart(fig_det, use_container_width=True)

        # 원시 데이터 표시
        with st.expander("원시 데이터 보기"):
            raw_cols = [c for c in row.index if c.startswith("raw_")]
            raw_data = {c.replace("raw_", ""): row[c] for c in raw_cols}
            st.json(raw_data)


if __name__ == "__main__":
    main()
