"""
Src/tests/test_ui/test_ui_utils.py
══════════════════════════════════════════════════════════════════════
ทดสอบ pure functions ใน ui/core/utils.py

Strategy: 100% Real (ไม่มี mock, ไม่ต้อง launch Gradio)
- ทุก function รับ dict → คืน str หรือ dict
- ไม่มี I/O, ไม่มี API call

ครอบคลุม:
  1. calculate_weighted_vote() — weighted voting logic
  2. format_voting_summary()   — text formatting
  3. format_error_message()    — error formatting
  4. format_retry_status()     — retry message
  5. strength_indicator()      — confidence → label
  6. confidence_bar()          — ASCII bar
  7. signal_recommendation()   — signal + confidence → text
  8. calculate_portfolio_metrics() — portfolio math
  9. validate_portfolio_update()   — validation logic
══════════════════════════════════════════════════════════════════════
"""

import pytest
from ui.core.utils import (
    calculate_weighted_vote,
    format_voting_summary,
    format_error_message,
    format_retry_status,
    strength_indicator,
    confidence_bar,
    signal_recommendation,
    calculate_portfolio_metrics,
    validate_portfolio_update,
)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _interval_results(buy=None, sell=None, hold=None) -> dict:
    """สร้าง interval_results dict ง่ายๆ สำหรับ test"""
    results = {}
    if buy:
        results["1h"] = {"signal": "BUY", "confidence": buy}
    if sell:
        results["4h"] = {"signal": "SELL", "confidence": sell}
    if hold:
        results["1d"] = {"signal": "HOLD", "confidence": hold}
    return results


# ══════════════════════════════════════════════
# 1. calculate_weighted_vote
# ══════════════════════════════════════════════

class TestCalculateWeightedVote:
    """ทดสอบ weighted voting logic"""

    def test_empty_input_returns_hold(self):
        """input ว่าง → HOLD, confidence = 0"""
        result = calculate_weighted_vote({})
        assert result["final_signal"] == "HOLD"
        assert result["weighted_confidence"] == 0.0
        assert "error" in result

    def test_single_buy_signal(self):
        """1h BUY confidence สูง → final = BUY"""
        result = calculate_weighted_vote({"1h": {"signal": "BUY", "confidence": 0.9}})
        assert result["final_signal"] == "BUY"
        assert result["weighted_confidence"] > 0

    def test_single_sell_signal(self):
        """4h SELL confidence สูง → final = SELL"""
        result = calculate_weighted_vote({"4h": {"signal": "SELL", "confidence": 0.9}})
        assert result["final_signal"] == "SELL"

    def test_majority_buy_wins(self):
        """หลาย interval ส่วนใหญ่ BUY → final = BUY"""
        results = {
            "1h": {"signal": "BUY", "confidence": 0.85},
            "4h": {"signal": "BUY", "confidence": 0.90},
            "1d": {"signal": "SELL", "confidence": 0.6},
        }
        result = calculate_weighted_vote(results)
        assert result["final_signal"] == "BUY"

    def test_low_confidence_defaults_to_hold(self):
        """weighted score < 0.4 → final = HOLD"""
        results = {
            "1m": {"signal": "BUY", "confidence": 0.3},
        }
        result = calculate_weighted_vote(results)
        assert result["final_signal"] == "HOLD"

    def test_returns_required_keys(self):
        """ต้องมี keys ครบ: final_signal, weighted_confidence, voting_breakdown, interval_details"""
        result = calculate_weighted_vote({"1h": {"signal": "BUY", "confidence": 0.8}})
        assert "final_signal" in result
        assert "weighted_confidence" in result
        assert "voting_breakdown" in result
        assert "interval_details" in result

    def test_voting_breakdown_has_all_signals(self):
        """voting_breakdown ต้องมีครบ BUY, SELL, HOLD"""
        result = calculate_weighted_vote({"1h": {"signal": "BUY", "confidence": 0.8}})
        breakdown = result["voting_breakdown"]
        assert "BUY" in breakdown
        assert "SELL" in breakdown
        assert "HOLD" in breakdown

    def test_unknown_interval_skipped(self):
        """interval ที่ไม่รู้จักถูกข้ามไป ไม่ crash"""
        results = {
            "99h": {"signal": "BUY", "confidence": 0.9},
            "1h":  {"signal": "BUY", "confidence": 0.8},
        }
        result = calculate_weighted_vote(results)
        assert result["final_signal"] in {"BUY", "SELL", "HOLD"}

    def test_weighted_confidence_between_0_and_1(self):
        """weighted_confidence ต้องอยู่ระหว่าง 0–1"""
        results = {
            "1h": {"signal": "BUY", "confidence": 0.85},
            "4h": {"signal": "BUY", "confidence": 0.90},
        }
        result = calculate_weighted_vote(results)
        assert 0.0 <= result["weighted_confidence"] <= 1.0

    def test_interval_details_count_matches_valid_intervals(self):
        """interval_details ต้องมีจำนวนตรงกับ valid intervals ที่ส่งเข้ามา"""
        results = {
            "1h": {"signal": "BUY",  "confidence": 0.8},
            "4h": {"signal": "SELL", "confidence": 0.7},
        }
        result = calculate_weighted_vote(results)
        assert len(result["interval_details"]) == 2

    def test_buy_count_in_breakdown(self):
        """voting_breakdown['BUY']['count'] ต้องนับถูก"""
        results = {
            "1h": {"signal": "BUY", "confidence": 0.8},
            "4h": {"signal": "BUY", "confidence": 0.9},
            "1d": {"signal": "SELL", "confidence": 0.7},
        }
        result = calculate_weighted_vote(results)
        assert result["voting_breakdown"]["BUY"]["count"] == 2
        assert result["voting_breakdown"]["SELL"]["count"] == 1

    def test_only_unknown_intervals_returns_error(self):
        """ส่งแต่ interval ที่ไม่รู้จัก → total_weight = 0 → error"""
        result = calculate_weighted_vote({"99h": {"signal": "BUY", "confidence": 0.9}})
        assert result["final_signal"] == "HOLD"
        assert "error" in result


# ══════════════════════════════════════════════
# 2. format_voting_summary
# ══════════════════════════════════════════════

class TestFormatVotingSummary:
    """ทดสอบ format_voting_summary() output text"""

    def _get_voting_result(self, signal="BUY", confidence=0.85):
        return {
            "final_signal": signal,
            "weighted_confidence": confidence,
            "voting_breakdown": {
                "BUY":  {"count": 2, "avg_conf": 0.85, "total_weight": 0.52, "weighted_score": 0.44, "intervals": ["1h", "4h"]},
                "SELL": {"count": 0, "avg_conf": 0.0,  "total_weight": 0.0,  "weighted_score": 0.0,  "intervals": []},
                "HOLD": {"count": 0, "avg_conf": 0.0,  "total_weight": 0.0,  "weighted_score": 0.0,  "intervals": []},
            },
            "interval_details": [
                {"interval": "1h", "signal": "BUY", "confidence": 0.85, "weight": 0.22},
                {"interval": "4h", "signal": "BUY", "confidence": 0.90, "weight": 0.30},
            ]
        }

    def test_returns_string(self):
        """ต้องคืน string"""
        result = format_voting_summary(self._get_voting_result())
        assert isinstance(result, str)

    def test_contains_final_signal(self):
        """ต้องมี final signal อยู่ใน output"""
        result = format_voting_summary(self._get_voting_result("BUY"))
        assert "BUY" in result

    def test_contains_weighted_confidence(self):
        """ต้องมี confidence อยู่ใน output"""
        result = format_voting_summary(self._get_voting_result(confidence=0.85))
        assert "85%" in result or "0.85" in result or "85" in result

    def test_contains_interval_details(self):
        """ต้องแสดง interval details"""
        result = format_voting_summary(self._get_voting_result())
        assert "1h" in result
        assert "4h" in result

    def test_contains_vote_tally_header(self):
        """ต้องมี Vote Tally section"""
        result = format_voting_summary(self._get_voting_result())
        assert "Vote Tally" in result or "VOTING" in result.upper()

    def test_sell_signal_in_output(self):
        """SELL signal ต้องปรากฏใน output"""
        voting = self._get_voting_result("SELL", 0.75)
        voting["voting_breakdown"]["SELL"] = {
            "count": 1, "avg_conf": 0.75, "total_weight": 0.30,
            "weighted_score": 0.75, "intervals": ["4h"]
        }
        result = format_voting_summary(voting)
        assert "SELL" in result

    def test_empty_breakdown_no_crash(self):
        """voting_breakdown ว่าง → ไม่ crash"""
        result = format_voting_summary({
            "final_signal": "HOLD",
            "weighted_confidence": 0.0,
            "voting_breakdown": {},
            "interval_details": [],
        })
        assert isinstance(result, str)


# ══════════════════════════════════════════════
# 3. format_error_message
# ══════════════════════════════════════════════

class TestFormatErrorMessage:
    """ทดสอบ format_error_message()"""

    def test_validation_error_format(self):
        """error_type=validation → ขึ้นต้นด้วย Validation Error"""
        result = format_error_message({
            "status": "error",
            "error": "Invalid provider",
            "error_type": "validation",
        })
        assert "Validation" in result
        assert "Invalid provider" in result

    def test_api_failure_format(self):
        """error_type=api_failure → แสดง attempt number"""
        result = format_error_message({
            "status": "error",
            "error": "Timeout",
            "error_type": "api_failure",
            "attempt": 2,
        })
        assert "API" in result or "Attempt" in result
        assert "Timeout" in result

    def test_general_error_format(self):
        """error_type ทั่วไป → ขึ้นต้นด้วย Error"""
        result = format_error_message({
            "status": "error",
            "error": "Something broke",
            "error_type": "general",
        })
        assert "Error" in result
        assert "Something broke" in result

    def test_missing_error_type_defaults_to_general(self):
        """ไม่มี error_type → ใช้ general format"""
        result = format_error_message({"error": "Unknown issue"})
        assert isinstance(result, str)
        assert "Unknown issue" in result

    def test_returns_string(self):
        """ต้องคืน string เสมอ"""
        result = format_error_message({})
        assert isinstance(result, str)


# ══════════════════════════════════════════════
# 4. format_retry_status
# ══════════════════════════════════════════════

class TestFormatRetryStatus:
    """ทดสอบ format_retry_status()"""

    def test_retrying_message(self):
        """attempt < max_retries → แสดง Retrying"""
        result = format_retry_status(attempt=1, max_retries=3, error="Timeout")
        assert "Retrying" in result or "Attempt" in result

    def test_failed_message(self):
        """attempt = max_retries → แสดง Failed"""
        result = format_retry_status(attempt=3, max_retries=3, error="Timeout")
        assert "Failed" in result or "failed" in result

    def test_error_in_output(self):
        """error message ต้องอยู่ใน output"""
        result = format_retry_status(attempt=1, max_retries=3, error="Connection refused")
        assert "Connection refused" in result

    def test_returns_string(self):
        """ต้องคืน string"""
        result = format_retry_status(1, 3, "error")
        assert isinstance(result, str)


# ══════════════════════════════════════════════
# 5. strength_indicator
# ══════════════════════════════════════════════

class TestStrengthIndicator:
    """ทดสอบ strength_indicator() confidence → label"""

    def test_very_strong_at_0_9(self):
        """confidence >= 0.9 → Very Strong"""
        assert "Very Strong" in strength_indicator(0.9)
        assert "Very Strong" in strength_indicator(1.0)

    def test_strong_at_0_75(self):
        """0.75 <= confidence < 0.9 → Strong"""
        result = strength_indicator(0.75)
        assert "Strong" in result

    def test_moderate_at_0_6(self):
        """0.6 <= confidence < 0.75 → Moderate"""
        result = strength_indicator(0.6)
        assert "Moderate" in result

    def test_weak_at_0_4(self):
        """0.4 <= confidence < 0.6 → Weak"""
        result = strength_indicator(0.4)
        assert "Weak" in result

    def test_very_weak_below_0_4(self):
        """confidence < 0.4 → Very Weak"""
        result = strength_indicator(0.3)
        assert "Very Weak" in result or "Weak" in result

    def test_returns_string(self):
        """ต้องคืน string เสมอ"""
        assert isinstance(strength_indicator(0.5), str)


# ══════════════════════════════════════════════
# 6. confidence_bar
# ══════════════════════════════════════════════

class TestConfidenceBar:
    """ทดสอบ confidence_bar() ASCII visualization"""

    def test_returns_string(self):
        """ต้องคืน string"""
        assert isinstance(confidence_bar(0.7), str)

    def test_contains_percentage(self):
        """ต้องแสดง percentage"""
        result = confidence_bar(0.7)
        assert "70%" in result

    def test_full_bar_at_1_0(self):
        """confidence = 1.0 → bar เต็ม"""
        result = confidence_bar(1.0, width=10)
        assert "100%" in result

    def test_empty_bar_at_0(self):
        """confidence = 0 → bar ว่าง"""
        result = confidence_bar(0.0, width=10)
        assert "0%" in result

    def test_custom_width(self):
        """width กำหนดเองได้"""
        result = confidence_bar(0.5, width=20)
        assert isinstance(result, str)

    def test_contains_bar_characters(self):
        """ต้องมี bar characters (█ หรือ ░)"""
        result = confidence_bar(0.5)
        assert "█" in result or "░" in result or "[" in result


# ══════════════════════════════════════════════
# 7. signal_recommendation
# ══════════════════════════════════════════════

class TestSignalRecommendation:
    """ทดสอบ signal_recommendation()"""

    def test_strong_buy_recommendation(self):
        """BUY + confidence >= 0.8 → Strong BUY"""
        result = signal_recommendation("BUY", 0.85)
        assert "BUY" in result
        assert "Strong" in result

    def test_weak_buy_recommendation(self):
        """BUY + confidence < 0.6 → weak BUY"""
        result = signal_recommendation("BUY", 0.5)
        assert "BUY" in result

    def test_strong_sell_recommendation(self):
        """SELL + confidence >= 0.8 → Strong SELL"""
        result = signal_recommendation("SELL", 0.85)
        assert "SELL" in result
        assert "Strong" in result

    def test_hold_recommendation(self):
        """HOLD → HOLD message"""
        result = signal_recommendation("HOLD", 0.6)
        assert "HOLD" in result

    def test_returns_string(self):
        """ต้องคืน string เสมอ"""
        assert isinstance(signal_recommendation("BUY", 0.7), str)


# ══════════════════════════════════════════════
# 8. calculate_portfolio_metrics
# ══════════════════════════════════════════════

class TestCalculatePortfolioMetrics:
    """ทดสอบ calculate_portfolio_metrics()"""

    def _portfolio(self, cash=5000, gold_g=1.0, cost=4500, cur_val=4800, pnl=300):
        return {
            "cash_balance": cash,
            "gold_grams": gold_g,
            "cost_basis_thb": cost,
            "current_value_thb": cur_val,
            "unrealized_pnl": pnl,
        }

    def test_returns_required_keys(self):
        """ต้องมี keys ครบ"""
        result = calculate_portfolio_metrics(self._portfolio())
        required = {"total_value", "cash_percentage", "gold_percentage", "roi", "can_buy", "can_sell"}
        assert required.issubset(result.keys())

    def test_total_value_is_cash_plus_gold(self):
        """total_value = cash + current_value"""
        result = calculate_portfolio_metrics(self._portfolio(cash=5000, cur_val=4800))
        assert result["total_value"] == 9800.0

    def test_can_buy_true_when_cash_sufficient(self):
        """cash >= 1000 → can_buy = True"""
        result = calculate_portfolio_metrics(self._portfolio(cash=2000))
        assert result["can_buy"] is True

    def test_can_buy_false_when_cash_insufficient(self):
        """cash < 1000 → can_buy = False"""
        result = calculate_portfolio_metrics(self._portfolio(cash=500))
        assert result["can_buy"] is False

    def test_can_sell_true_when_gold_exists(self):
        """gold_grams > 0 → can_sell = True"""
        result = calculate_portfolio_metrics(self._portfolio(gold_g=1.0))
        assert result["can_sell"] is True

    def test_can_sell_false_when_no_gold(self):
        """gold_grams = 0 → can_sell = False"""
        result = calculate_portfolio_metrics(self._portfolio(gold_g=0.0))
        assert result["can_sell"] is False

    def test_roi_calculation(self):
        """ROI = (cur_val - cost) / cost * 100"""
        result = calculate_portfolio_metrics(self._portfolio(cost=4000, cur_val=4800))
        assert result["roi"] == pytest.approx(20.0, abs=0.1)

    def test_cash_percentage_range(self):
        """cash_percentage ต้องอยู่ระหว่าง 0–100"""
        result = calculate_portfolio_metrics(self._portfolio())
        assert 0 <= result["cash_percentage"] <= 100

    def test_zero_total_value_no_crash(self):
        """total_value = 0 → ไม่ crash"""
        result = calculate_portfolio_metrics(self._portfolio(cash=0, cur_val=0))
        assert result["cash_percentage"] == 0
        assert result["gold_percentage"] == 0


# ══════════════════════════════════════════════
# 9. validate_portfolio_update
# ══════════════════════════════════════════════

class TestValidatePortfolioUpdate:
    """ทดสอบ validate_portfolio_update()"""

    def _valid_portfolio(self):
        return {
            "cash_balance": 5000.0,
            "gold_grams": 1.0,
            "cost_basis_thb": 4500.0,
            "current_value_thb": 4800.0,
            "unrealized_pnl": 300.0,
        }

    def test_valid_portfolio_passes(self):
        """portfolio ถูกต้อง → (True, '')"""
        is_valid, msg = validate_portfolio_update({}, self._valid_portfolio())
        assert is_valid is True
        assert msg == ""

    def test_negative_cash_fails(self):
        """cash < 0 → (False, error message)"""
        bad = {**self._valid_portfolio(), "cash_balance": -100.0}
        is_valid, msg = validate_portfolio_update({}, bad)
        assert is_valid is False
        assert "cash" in msg.lower() or "Cash" in msg

    def test_negative_gold_fails(self):
        """gold_grams < 0 → False"""
        bad = {**self._valid_portfolio(), "gold_grams": -1.0}
        is_valid, msg = validate_portfolio_update({}, bad)
        assert is_valid is False

    def test_negative_cost_fails(self):
        """cost_basis_thb < 0 → False"""
        bad = {**self._valid_portfolio(), "cost_basis_thb": -500.0}
        is_valid, msg = validate_portfolio_update({}, bad)
        assert is_valid is False

    def test_negative_current_value_fails(self):
        """current_value_thb < 0 → False"""
        bad = {**self._valid_portfolio(), "current_value_thb": -100.0}
        is_valid, msg = validate_portfolio_update({}, bad)
        assert is_valid is False

    def test_none_value_fails(self):
        """ค่า None → False"""
        bad = {**self._valid_portfolio(), "cash_balance": None}
        is_valid, msg = validate_portfolio_update({}, bad)
        assert is_valid is False

    def test_negative_pnl_allowed(self):
        """unrealized_pnl ลบได้ (ขาดทุนปกติ)"""
        ok = {**self._valid_portfolio(), "unrealized_pnl": -500.0}
        is_valid, msg = validate_portfolio_update({}, ok)
        assert is_valid is True

    def test_returns_tuple(self):
        """ต้องคืน tuple (bool, str)"""
        result = validate_portfolio_update({}, self._valid_portfolio())
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)