"""
Tests for data_engine/tools/tool_result_scorer.py

Covers:
- Empty-input edge case
- Weighted average arithmetic and threshold boundary
- Hard-block gate (is_safe_to_trade=False)
- All 10 specialized _score_*() methods
- Unknown-tool generic fallback
- Recommendation builder (circular guard, deep-news category tracking)
- Summary string builder
"""

import pytest
from data_engine.tools.tool_result_scorer import (
    ToolResult,
    ToolResultScorer,
    FLOOR_SCORE,
    PROCEED_THRESHOLD,
)

pytestmark = pytest.mark.data_engine

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def scorer():
    """Shared ToolResultScorer instance (stateless)."""
    return ToolResultScorer()


@pytest.fixture
def make_result():
    """Factory fixture: returns a callable that builds ToolResult objects."""
    def _factory(tool_name, output, params=None, weight=1.0):
        return ToolResult(
            tool_name=tool_name,
            output=output,
            params=params or {},
            weight=weight,
        )
    return _factory


@pytest.fixture
def error_output():
    """Standard error output dict reused across scorer error-path tests."""
    return {"status": "error", "message": "fetch failed"}


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreEmptyInput
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreEmptyInput:
    def test_empty_list_returns_no_proceed(self, scorer):
        report = scorer.score([])
        assert report.should_proceed is False
        assert report.avg_score == 0.0
        assert report.tool_scores == []
        assert report.hard_block is False

    def test_empty_list_summary_contains_thai_message(self, scorer):
        report = scorer.score([])
        assert "ไม่มี tool results" in report.summary


# ─────────────────────────────────────────────────────────────────────────────
# TestWeightedAverageArithmetic
# ─────────────────────────────────────────────────────────────────────────────


class TestWeightedAverageArithmetic:
    def test_single_tool_avg_equals_weighted_score(self, scorer, make_result):
        result = make_result(
            "detect_breakout_confirmation",
            {"is_confirmed_breakout": True, "details": {"body_strength_pct": 55.0}},
            weight=1.0,
        )
        report = scorer.score([result])
        assert report.avg_score == report.tool_scores[0].weighted_score

    def test_weighted_average_two_tools(self, scorer, make_result):
        # breakout confirmed (score=0.85) weight=2.0
        # bb_rsi not detected (score=FLOOR_SCORE) weight=1.0
        r1 = make_result(
            "detect_breakout_confirmation",
            {"is_confirmed_breakout": True, "details": {"body_strength_pct": 55.0}},
            weight=2.0,
        )
        r2 = make_result(
            "check_bb_rsi_combo",
            {"combo_detected": False},
            weight=1.0,
        )
        report = scorer.score([r1, r2])
        expected = round((0.85 * 2.0 + FLOOR_SCORE * 1.0) / 3.0, 4)
        assert report.avg_score == expected

    @pytest.mark.parametrize("combo_detected,expected_proceed", [
        # combo_detected=False → FLOOR_SCORE=0.2 → avg < 0.6 → False
        (False, False),
        # combo_detected=True → 0.85 → avg ≥ 0.6 → True
        (True, True),
    ])
    def test_proceed_boundary_via_single_tool(
        self, scorer, make_result, combo_detected, expected_proceed
    ):
        result = make_result("check_bb_rsi_combo", {"combo_detected": combo_detected})
        report = scorer.score([result])
        assert report.should_proceed is expected_proceed


# ─────────────────────────────────────────────────────────────────────────────
# TestHardBlock
# ─────────────────────────────────────────────────────────────────────────────


class TestHardBlock:
    def test_hard_block_when_is_safe_to_trade_false(self, scorer, make_result):
        result = make_result(
            "check_upcoming_economic_calendar",
            {
                "status": "success",
                "risk_level": "critical",
                "is_safe_to_trade": False,
                "trade_action": "avoid",
                "trade_note": "ห้ามเปิดออเดอร์ใหม่",
            },
        )
        report = scorer.score([result])
        assert report.hard_block is True
        assert report.should_proceed is False

    def test_hard_block_reason_contains_tool_name_and_action(self, scorer, make_result):
        result = make_result(
            "check_upcoming_economic_calendar",
            {
                "is_safe_to_trade": False,
                "trade_action": "avoid",
                "trade_note": "NFP imminent",
            },
        )
        report = scorer.score([result])
        assert "check_upcoming_economic_calendar" in report.hard_block_reason
        assert "trade_action=avoid" in report.hard_block_reason
        assert "NFP imminent" in report.hard_block_reason

    def test_hard_block_overrides_high_avg_score(self, scorer, make_result):
        """Even if most tools score high, a single is_safe_to_trade=False blocks."""
        r1 = make_result(
            "detect_breakout_confirmation",
            {"is_confirmed_breakout": True, "details": {"body_strength_pct": 80.0}},
        )
        r2 = make_result("check_bb_rsi_combo", {"combo_detected": True})
        r3 = make_result(
            "check_upcoming_economic_calendar",
            {"is_safe_to_trade": False, "trade_action": "avoid", "trade_note": ""},
        )
        report = scorer.score([r1, r2, r3])
        assert report.avg_score >= 0.6, "avg should be high from the two good tools"
        assert report.hard_block is True
        assert report.should_proceed is False

    def test_no_hard_block_when_is_safe_to_trade_true(self, scorer, make_result):
        result = make_result(
            "check_upcoming_economic_calendar",
            {"status": "success", "risk_level": "low", "is_safe_to_trade": True},
        )
        report = scorer.score([result])
        assert report.hard_block is False

    def test_hard_block_uses_first_unsafe_tool(self, scorer, make_result):
        r1 = make_result(
            "check_upcoming_economic_calendar",
            {"is_safe_to_trade": False, "trade_action": "avoid", "trade_note": "first"},
        )
        r2 = make_result(
            "get_intermarket_correlation",
            {"is_safe_to_trade": False, "trade_action": "reduce", "trade_note": "second"},
        )
        report = scorer.score([r1, r2])
        # hard_block_reason should reference the FIRST unsafe tool
        assert "check_upcoming_economic_calendar" in report.hard_block_reason


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreBreakoutConfirmation
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreBreakoutConfirmation:
    def test_confirmed_normal_body(self, scorer, make_result):
        r = make_result(
            "detect_breakout_confirmation",
            {"is_confirmed_breakout": True, "details": {"body_strength_pct": 55.0}},
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.85

    def test_confirmed_strong_body_gets_bonus(self, scorer, make_result):
        r = make_result(
            "detect_breakout_confirmation",
            {"is_confirmed_breakout": True, "details": {"body_strength_pct": 72.0}},
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.95  # 0.85 + 0.10

    def test_no_breakout_returns_floor(self, scorer, make_result):
        r = make_result(
            "detect_breakout_confirmation",
            {"is_confirmed_breakout": False},
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == FLOOR_SCORE

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("detect_breakout_confirmation", error_output)
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreBbRsiCombo
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreBbRsiCombo:
    def test_combo_detected(self, scorer, make_result):
        r = make_result("check_bb_rsi_combo", {"combo_detected": True})
        assert scorer.score([r]).tool_scores[0].score == 0.85

    def test_no_combo_returns_floor(self, scorer, make_result):
        r = make_result("check_bb_rsi_combo", {"combo_detected": False})
        assert scorer.score([r]).tool_scores[0].score == FLOOR_SCORE

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("check_bb_rsi_combo", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreRsiDivergence
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreRsiDivergence:
    def test_divergence_detected_builds_detail_string(self, scorer, make_result):
        r = make_result(
            "detect_rsi_divergence",
            {
                "divergence_detected": True,
                "data": {"Low1": 2300.0, "RSI1": 28.5, "Low2": 2280.0, "RSI2": 31.0},
            },
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.85
        for val in ["2300.0", "28.5", "2280.0", "31.0"]:
            assert val in ts.reason

    def test_no_divergence_includes_logic_string(self, scorer, make_result):
        r = make_result(
            "detect_rsi_divergence",
            {"divergence_detected": False, "logic": "price and RSI co-moving"},
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == FLOOR_SCORE
        assert "price and RSI co-moving" in ts.reason

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("detect_rsi_divergence", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreEmaDistance
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreEmaDistance:
    def test_overextended_normal_distance(self, scorer, make_result):
        r = make_result(
            "calculate_ema_distance",
            {"is_overextended": True, "distance_atr_ratio": 3.5},
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.75

    def test_overextended_far_distance_gets_bonus(self, scorer, make_result):
        r = make_result(
            "calculate_ema_distance",
            {"is_overextended": True, "distance_atr_ratio": 7.5},
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.90  # 0.75 + 0.15

    def test_not_overextended_returns_floor(self, scorer, make_result):
        r = make_result(
            "calculate_ema_distance",
            {"is_overextended": False, "distance_atr_ratio": 1.2},
        )
        assert scorer.score([r]).tool_scores[0].score == FLOOR_SCORE

    def test_negative_distance_uses_abs(self, scorer, make_result):
        """Price is far BELOW EMA20 — abs() should still trigger the bonus."""
        r = make_result(
            "calculate_ema_distance",
            {"is_overextended": True, "distance_atr_ratio": -7.5},
        )
        assert scorer.score([r]).tool_scores[0].score == 0.90

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("calculate_ema_distance", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreSupportResistance
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreSupportResistance:
    def _zone(self, bottom, top, strength):
        return {"bottom": bottom, "top": top, "strength": strength}

    def test_no_zones_returns_floor(self, scorer, make_result):
        r = make_result(
            "get_support_resistance_zones",
            {"zones": [], "current_price": 3200.0, "adaptive_metrics": {"atr_used": 10.0}},
        )
        assert scorer.score([r]).tool_scores[0].score == FLOOR_SCORE

    def test_zones_but_price_not_nearby_returns_0_4(self, scorer, make_result):
        r = make_result(
            "get_support_resistance_zones",
            {
                "zones": [self._zone(3000, 3010, "High")],
                "current_price": 3200.0,
                "adaptive_metrics": {"atr_used": 10.0},
            },
        )
        assert scorer.score([r]).tool_scores[0].score == 0.4

    @pytest.mark.parametrize("strength,expected_score", [
        ("Low", 0.6),
        ("Medium", 0.75),
        ("High", 0.9),
    ])
    def test_nearby_zone_strength_mapping(self, scorer, make_result, strength, expected_score):
        """Price is inside the zone boundary ± 1 ATR."""
        r = make_result(
            "get_support_resistance_zones",
            {
                # zone spans 3195–3205, price=3200, atr=10 → clearly nearby
                "zones": [self._zone(3195, 3205, strength)],
                "current_price": 3200.0,
                "adaptive_metrics": {"atr_used": 10.0},
            },
        )
        assert scorer.score([r]).tool_scores[0].score == expected_score

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("get_support_resistance_zones", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreHtfTrend
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreHtfTrend:
    def test_bullish_far_from_ema(self, scorer, make_result):
        r = make_result(
            "get_htf_trend",
            {"trend": "Bullish", "distance_from_ema_pct": 2.5},
        )
        assert scorer.score([r]).tool_scores[0].score == 0.75

    def test_bullish_near_ema(self, scorer, make_result):
        r = make_result(
            "get_htf_trend",
            {"trend": "Bullish", "distance_from_ema_pct": 0.8},
        )
        assert scorer.score([r]).tool_scores[0].score == 0.6

    def test_bearish_uses_abs_for_distance(self, scorer, make_result):
        """Bearish trend with negative distance — abs should give 2.0 → 0.75."""
        r = make_result(
            "get_htf_trend",
            {"trend": "Bearish", "distance_from_ema_pct": -2.0},
        )
        assert scorer.score([r]).tool_scores[0].score == 0.75

    def test_unclear_trend_returns_floor(self, scorer, make_result):
        r = make_result(
            "get_htf_trend",
            {"trend": "Sideways", "distance_from_ema_pct": 0.1},
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == FLOOR_SCORE
        assert "Sideways" in ts.reason

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("get_htf_trend", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreSpotThbAlignment
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreSpotThbAlignment:
    def test_strong_bullish_returns_0_85(self, scorer, make_result):
        r = make_result(
            "check_spot_thb_alignment",
            {
                "alignment": "Strong Bullish",
                "details": {"spot_pct_change": 0.5, "thb_pct_change": 0.3},
            },
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.85
        assert "Strong Bullish" in ts.reason

    def test_strong_bearish_returns_0_85(self, scorer, make_result):
        r = make_result(
            "check_spot_thb_alignment",
            {
                "alignment": "Strong Bearish",
                "details": {"spot_pct_change": -0.5, "thb_pct_change": -0.3},
            },
        )
        assert scorer.score([r]).tool_scores[0].score == 0.85

    def test_neutral_returns_0_3(self, scorer, make_result):
        r = make_result(
            "check_spot_thb_alignment",
            {"alignment": "Neutral (Spot Leading)"},
        )
        assert scorer.score([r]).tool_scores[0].score == 0.3

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("check_spot_thb_alignment", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreEconomicCalendar
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreEconomicCalendar:
    @pytest.mark.parametrize("risk_level,expected_score", [
        ("critical", 1.0),
        ("high", 0.8),
        ("medium", 0.5),
        ("low", FLOOR_SCORE),
        ("completely_unknown_level", FLOOR_SCORE),
    ])
    def test_score_by_risk_level(self, scorer, make_result, risk_level, expected_score):
        r = make_result(
            "check_upcoming_economic_calendar",
            {"status": "success", "risk_level": risk_level},
        )
        assert scorer.score([r]).tool_scores[0].score == expected_score

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("check_upcoming_economic_calendar", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreDeepNews
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreDeepNews:
    def test_zero_articles_returns_floor(self, scorer, make_result):
        r = make_result("get_deep_news_by_category", {"count": 0})
        assert scorer.score([r]).tool_scores[0].score == FLOOR_SCORE

    def test_count_1_no_relevance_returns_0_5(self, scorer, make_result):
        r = make_result("get_deep_news_by_category", {"count": 1})
        assert scorer.score([r]).tool_scores[0].score == 0.5

    @pytest.mark.parametrize("count,relevance_score,expected", [
        (3, 0.9, round(0.7 * 0.6 + 0.9 * 0.4, 4)),
        (6, 0.4, round(0.85 * 0.6 + 0.4 * 0.4, 4)),
        (6, 1.0, round(0.85 * 0.6 + 1.0 * 0.4, 4)),  # 0.91 — formula max; min() guard is safety-only
    ])
    def test_blended_score_with_relevance(self, scorer, make_result, count, relevance_score, expected):
        r = make_result("get_deep_news_by_category", {"count": count, "relevance_score": relevance_score})
        assert scorer.score([r]).tool_scores[0].score == expected

    def test_no_relevance_score_uses_count_fallback(self, scorer, make_result):
        """When relevance_score is None, fallback to count-only scoring."""
        r = make_result("get_deep_news_by_category", {"count": 5, "relevance_score": None})
        assert scorer.score([r]).tool_scores[0].score == 0.85

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("get_deep_news_by_category", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestScoreIntermarketCorrelation
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreIntermarketCorrelation:
    def test_two_warnings_returns_1_0(self, scorer, make_result):
        r = make_result(
            "get_intermarket_correlation",
            {
                "divergences": [
                    {"status": "bearish_warning", "pair": "gold_vs_DXY"},
                    {"status": "bullish_warning", "pair": "gold_vs_US10Y"},
                ]
            },
        )
        assert scorer.score([r]).tool_scores[0].score == 1.0

    def test_one_warning_returns_0_75(self, scorer, make_result):
        r = make_result(
            "get_intermarket_correlation",
            {
                "divergences": [
                    {"status": "bearish_warning", "pair": "gold_vs_DXY", "note": "Gold and DXY both up"},
                ]
            },
        )
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == 0.75
        assert "gold_vs_DXY" in ts.reason

    def test_all_flat_returns_floor(self, scorer, make_result):
        r = make_result(
            "get_intermarket_correlation",
            {
                "divergences": [
                    {"status": "flat", "pair": "gold_vs_DXY"},
                    {"status": "flat", "pair": "gold_vs_US10Y"},
                ]
            },
        )
        assert scorer.score([r]).tool_scores[0].score == FLOOR_SCORE

    def test_all_normal_returns_0_3(self, scorer, make_result):
        r = make_result(
            "get_intermarket_correlation",
            {
                "divergences": [
                    {"status": "normal", "pair": "gold_vs_DXY"},
                    {"status": "normal", "pair": "gold_vs_US10Y"},
                ]
            },
        )
        assert scorer.score([r]).tool_scores[0].score == 0.3

    def test_empty_divergences_returns_floor(self, scorer, make_result):
        r = make_result("get_intermarket_correlation", {"divergences": []})
        assert scorer.score([r]).tool_scores[0].score == FLOOR_SCORE

    def test_error_returns_zero(self, scorer, make_result, error_output):
        r = make_result("get_intermarket_correlation", error_output)
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestUnknownToolFallback
# ─────────────────────────────────────────────────────────────────────────────


class TestUnknownToolFallback:
    def test_unknown_tool_success_output_returns_floor(self, scorer, make_result):
        r = make_result("some_future_unregistered_tool", {"status": "success"})
        ts = scorer.score([r]).tool_scores[0]
        assert ts.score == FLOOR_SCORE
        assert "floor score" in ts.reason

    def test_unknown_tool_error_output_returns_zero(self, scorer, make_result):
        r = make_result(
            "some_future_unregistered_tool",
            {"status": "error", "message": "broken"},
        )
        assert scorer.score([r]).tool_scores[0].score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestBuildRecommendations
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildRecommendations:
    def test_low_score_generates_recommendation(self, scorer, make_result):
        """breakout not confirmed → score=FLOOR_SCORE → recommendations suggested."""
        r = make_result("detect_breakout_confirmation", {"is_confirmed_breakout": False})
        report = scorer.score([r])
        assert len(report.recommendations) > 0
        rec_tools = [rec.recommended_tool for rec in report.recommendations]
        assert any(t in rec_tools for t in ["get_support_resistance_zones", "check_bb_rsi_combo"])

    def test_no_recommendation_when_already_called(self, scorer, make_result):
        """If get_support_resistance_zones is already in results, it should NOT be recommended again."""
        r1 = make_result("detect_breakout_confirmation", {"is_confirmed_breakout": False})
        r2 = make_result(
            "get_support_resistance_zones",
            {"zones": [], "current_price": 3200.0, "adaptive_metrics": {"atr_used": 10.0}},
        )
        report = scorer.score([r1, r2])
        rec_tools = [rec.recommended_tool for rec in report.recommendations]
        assert "get_support_resistance_zones" not in rec_tools

    def test_deep_news_recommends_next_untried_category(self, scorer, make_result):
        """get_deep_news_by_category with category=gold_price (low score) → suggest next category."""
        r = make_result(
            "get_deep_news_by_category",
            {"count": 0},
            params={"category": "gold_price"},
        )
        report = scorer.score([r])
        assert len(report.recommendations) == 1
        rec = report.recommendations[0]
        assert rec.recommended_tool == "get_deep_news_by_category"
        assert rec.suggested_params["category"] != "gold_price"

    def test_deep_news_all_categories_exhausted_returns_no_recs(self, scorer, make_result):
        """When all 8 categories have been tried, no more recommendations."""
        all_categories = [
            "gold_price", "usd_thb", "fed_policy", "inflation",
            "geopolitics", "dollar_index", "thai_economy", "thai_gold_market",
        ]
        results = [
            make_result(
                "get_deep_news_by_category",
                {"count": 0},
                params={"category": cat},
            )
            for cat in all_categories
        ]
        report = scorer.score(results)
        assert report.recommendations == []

    def test_no_recommendations_when_should_proceed(self, scorer, make_result):
        """When avg ≥ 0.6 and no hard_block, recommendations list must be empty."""
        r = make_result("check_bb_rsi_combo", {"combo_detected": True})  # score=0.85
        report = scorer.score([r])
        assert report.should_proceed is True
        assert report.recommendations == []


# ─────────────────────────────────────────────────────────────────────────────
# TestBuildSummary
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildSummary:
    def test_summary_proceed(self, scorer, make_result):
        r = make_result("check_bb_rsi_combo", {"combo_detected": True})
        report = scorer.score([r])
        assert report.should_proceed is True
        assert "PROCEED" in report.summary

    def test_summary_hard_block(self, scorer, make_result):
        r = make_result(
            "check_upcoming_economic_calendar",
            {"is_safe_to_trade": False, "trade_action": "avoid", "trade_note": ""},
        )
        report = scorer.score([r])
        assert "HARD BLOCK" in report.summary

    def test_summary_need_more_tools(self, scorer, make_result):
        r = make_result("check_bb_rsi_combo", {"combo_detected": False})
        report = scorer.score([r])
        assert report.should_proceed is False
        assert report.hard_block is False
        assert "NEED MORE TOOLS" in report.summary

    def test_summary_contains_all_tool_names(self, scorer, make_result):
        r1 = make_result("check_bb_rsi_combo", {"combo_detected": True})
        r2 = make_result(
            "detect_rsi_divergence",
            {"divergence_detected": False, "logic": "co-moving"},
        )
        report = scorer.score([r1, r2])
        assert "check_bb_rsi_combo" in report.summary
        assert "detect_rsi_divergence" in report.summary

    def test_summary_contains_avg_score(self, scorer, make_result):
        r = make_result("check_bb_rsi_combo", {"combo_detected": True})
        report = scorer.score([r])
        assert "avg=" in report.summary
