"""scorer.py 순수 함수 단위 테스트"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from scorer import (
    calculate_scores,
    get_grade,
    score_52week_position,
    score_analyst_reports,
    score_eps_growth,
    score_forward_peg,
    score_institutional_buying,
    score_news_multiplier,
    score_operating_margin_trend,
    score_pbr_ratio,
    score_revenue_cagr,
    score_sector_flow,
    score_volume_multiplier,
)


class TestEpsGrowth:
    def test_none(self):        assert score_eps_growth(None) == 0
    def test_below_100(self):   assert score_eps_growth(50) == 0
    def test_100(self):         assert score_eps_growth(100) == 12
    def test_150(self):         assert score_eps_growth(150) == 12
    def test_200(self):         assert score_eps_growth(200) == 18
    def test_300(self):         assert score_eps_growth(300) == 20
    def test_500(self):         assert score_eps_growth(500) == 20


class TestRevenueCagr:
    def test_none(self):        assert score_revenue_cagr(None) == 0
    def test_10pct(self):       assert score_revenue_cagr(10) == 0
    def test_20pct(self):       assert score_revenue_cagr(20) == 6
    def test_30pct(self):       assert score_revenue_cagr(30) == 8
    def test_40pct(self):       assert score_revenue_cagr(40) == 10
    def test_50pct(self):       assert score_revenue_cagr(50) == 10


class TestOperatingMarginTrend:
    def test_none(self):              assert score_operating_margin_trend(None) == 0
    def test_maintained(self):        assert score_operating_margin_trend("maintained") == 4
    def test_improved(self):          assert score_operating_margin_trend("improved") == 7
    def test_sharply_improved(self):  assert score_operating_margin_trend("sharply_improved") == 10
    def test_unknown(self):           assert score_operating_margin_trend("bad_value") == 0


class TestVolumeMultiplier:
    def test_none(self):  assert score_volume_multiplier(None) == 0
    def test_1x(self):    assert score_volume_multiplier(1.0) == 0
    def test_2x(self):    assert score_volume_multiplier(2.0) == 2
    def test_3x(self):    assert score_volume_multiplier(3.0) == 4
    def test_5x(self):    assert score_volume_multiplier(5.0) == 6
    def test_7x(self):    assert score_volume_multiplier(7.0) == 8
    def test_10x(self):   assert score_volume_multiplier(10.0) == 10
    def test_15x(self):   assert score_volume_multiplier(15.0) == 10


class TestWeek52Position:
    def test_none(self):        assert score_52week_position(None) == 0
    def test_below_80(self):    assert score_52week_position(79.9) == 0
    def test_exactly_80(self):  assert score_52week_position(80.0) == 5
    def test_in_range(self):    assert score_52week_position(88.0) == 5
    def test_exactly_95(self):  assert score_52week_position(95.0) == 5
    def test_above_95(self):    assert score_52week_position(96.0) == 0
    def test_at_high(self):     assert score_52week_position(100.0) == 0


class TestInstitutionalBuying:
    def test_none(self):   assert score_institutional_buying(None) == 0
    def test_true(self):   assert score_institutional_buying(True) == 5
    def test_false(self):  assert score_institutional_buying(False) == 0


class TestForwardPeg:
    def test_none(self):      assert score_forward_peg(None) == 0
    def test_zero(self):      assert score_forward_peg(0) == 0
    def test_0_5(self):       assert score_forward_peg(0.5) == 8
    def test_0_6(self):       assert score_forward_peg(0.6) == 6
    def test_0_8(self):       assert score_forward_peg(0.8) == 6
    def test_0_9(self):       assert score_forward_peg(0.9) == 4
    def test_1_0(self):       assert score_forward_peg(1.0) == 4
    def test_1_2(self):       assert score_forward_peg(1.2) == 2
    def test_1_5(self):       assert score_forward_peg(1.5) == 2
    def test_2_0(self):       assert score_forward_peg(2.0) == 0


class TestPbrRatio:
    def test_none(self):      assert score_pbr_ratio(None) == 0
    def test_zero(self):      assert score_pbr_ratio(0) == 0
    def test_0_5(self):       assert score_pbr_ratio(0.5) == 7
    def test_0_6(self):       assert score_pbr_ratio(0.6) == 5
    def test_0_7(self):       assert score_pbr_ratio(0.7) == 5
    def test_0_8(self):       assert score_pbr_ratio(0.8) == 3
    def test_0_9(self):       assert score_pbr_ratio(0.9) == 3
    def test_1_0(self):       assert score_pbr_ratio(1.0) == 0


class TestGetGrade:
    def test_tenbagger(self):  assert get_grade(85) == "텐배거 후보"
    def test_strong(self):     assert get_grade(70) == "강력 후보"
    def test_promising(self):  assert get_grade(55) == "유망 후보"
    def test_watchlist(self):  assert get_grade(40) == "관심 종목"
    def test_excluded(self):   assert get_grade(39) == "제외"
    def test_max(self):        assert get_grade(100) == "텐배거 후보"
    def test_zero(self):       assert get_grade(0) == "제외"


class TestCalculateScores:
    def test_perfect_score(self):
        result = calculate_scores(
            eps_growth_pct=300,
            revenue_cagr_pct=40,
            operating_margin_trend="sharply_improved",
            sector_flow_intensity=10,
            analyst_report_count=6,
            news_multiplier=5,
            volume_multiplier=10,
            week52_position_pct=85,
            institutional_buying=True,
            forward_peg=0.5,
            pbr_vs_sector=0.5,
        )
        assert result["total"] == 100
        assert result["growth"] == 40
        assert result["sector"] == 25
        assert result["momentum"] == 20
        assert result["value"] == 15

    def test_all_none(self):
        result = calculate_scores()
        assert result["total"] == 0

    def test_detail_keys(self):
        result = calculate_scores()
        expected_keys = {
            "eps_growth", "revenue_cagr", "operating_margin",
            "sector_flow", "analyst_reports", "news_multiplier",
            "volume_multiplier", "week52_position", "institutional_buying",
            "forward_peg", "pbr_ratio",
        }
        assert set(result["detail"].keys()) == expected_keys

    def test_partial_score(self):
        result = calculate_scores(
            eps_growth_pct=200,      # 18
            volume_multiplier=5,     # 6
            institutional_buying=True,  # 5
        )
        assert result["total"] == 18 + 6 + 5
        assert result["growth"] == 18
        assert result["momentum"] == 11
