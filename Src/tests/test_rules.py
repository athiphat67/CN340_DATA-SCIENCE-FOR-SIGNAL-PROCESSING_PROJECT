"""
tests/test_rules.py
pytest suite — run with: pytest tests/test_rules.py -v
"""

import pytest
import math
from execution.risk_manager import RiskManager
from execution.router import TradeRouter


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture
def risk() -> RiskManager:
    return RiskManager(balance=100_000, max_pos_pct=0.10, gold_price=2_300)


@pytest.fixture
def router(risk) -> TradeRouter:
    return TradeRouter(risk_manager=risk)


# ============================================================
# RiskManager tests
# ============================================================
class TestRiskManager:
    def test_hold_always_passes(self, risk):
        ok, msg = risk.validate_trade({"action": "HOLD", "quantity": 0})
        assert ok

    def test_buy_within_limit(self, risk):
        # 4 lots × $2300 = $9200 < $10000 limit → should pass
        ok, msg = risk.validate_trade({"action": "BUY", "quantity": 4})
        assert ok, msg

    def test_buy_exceeds_limit(self, risk):
        # 5 lots × $2300 = $11500 > $10000 → should fail
        ok, msg = risk.validate_trade({"action": "BUY", "quantity": 5})
        assert not ok
        assert "risk limit" in msg.lower()

    def test_sell_within_limit(self, risk):
        ok, msg = risk.validate_trade({"action": "SELL", "quantity": 4})
        assert ok, msg

    def test_zero_quantity_rejected(self, risk):
        ok, msg = risk.validate_trade({"action": "BUY", "quantity": 0})
        assert not ok

    def test_negative_quantity_rejected(self, risk):
        ok, msg = risk.validate_trade({"action": "BUY", "quantity": -1})
        assert not ok

    def test_invalid_action_rejected(self, risk):
        ok, msg = risk.validate_trade({"action": "YOLO", "quantity": 1})
        assert not ok

    def test_dynamic_price_update(self, risk):
        # Raise gold price → same 4 lots now exceeds limit
        risk.update_gold_price(3_000)
        ok, msg = risk.validate_trade({"action": "BUY", "quantity": 4})
        assert not ok  # 4 × 3000 = 12000 > 10000

    def test_max_lots_calculation(self, risk):
        # max_lots = (100000 * 0.10) / 2300 ≈ 4.34
        assert abs(risk.max_lots() - (10_000 / 2_300)) < 0.01


# ============================================================
# TradeRouter tests
# ============================================================
class TestTradeRouter:
    def test_valid_buy_approved(self, router):
        result = router.route({"action": "BUY", "quantity": 2, "reasoning": "RSI oversold"})
        assert result["status"] == "APPROVED"

    def test_valid_sell_approved(self, router):
        result = router.route({"action": "SELL", "quantity": 1, "reasoning": "MACD cross"})
        assert result["status"] == "APPROVED"

    def test_hold_approved(self, router):
        result = router.route({"action": "HOLD", "quantity": 0, "reasoning": "Uncertain"})
        assert result["status"] == "APPROVED"

    def test_missing_quantity_rejected(self, router):
        result = router.route({"action": "BUY"})
        assert result["status"] == "REJECTED"

    def test_invalid_action_string_rejected(self, router):
        result = router.route({"action": "MOON", "quantity": 1})
        assert result["status"] == "REJECTED"

    def test_oversized_trade_rejected(self, router):
        result = router.route({"action": "BUY", "quantity": 100, "reasoning": "big bet"})
        assert result["status"] == "REJECTED"
        assert "risk" in result["reason"].lower()

    def test_none_input_rejected(self, router):
        result = router.route(None)  # type: ignore[arg-type]
        assert result["status"] == "REJECTED"

    def test_empty_dict_rejected(self, router):
        result = router.route({})
        assert result["status"] == "REJECTED"

    def test_lowercase_action_normalised(self, router):
        result = router.route({"action": "buy", "quantity": 1, "reasoning": "test"})
        assert result["status"] == "APPROVED"
        assert result["decision"]["action"] == "BUY"

# ============================================================
# SAMPLING VALIDATION TESTS (with confidence)
# ============================================================
class TestSamplingValidation:
    """ทดสอบการ validate sampling parameters"""

    def test_temperature_scaling_low_tau(self, router):
        """τ → 0: Temperature scaling increases confidence (greedy)"""
        confidence = 0.75
        tau = 0.1
        
        scaled = router._apply_temperature(confidence, tau)
        assert scaled > confidence  # Should increase confidence

    def test_temperature_scaling_high_tau(self, router):
        """τ = 2.0: Higher temperature reduces confidence (exploratory)"""
        confidence = 0.75
        tau = 2.0
        
        scaled = router._apply_temperature(confidence, tau)
        assert scaled < confidence  # Should reduce confidence

    def test_temperature_scaling_unity(self, router):
        """τ = 1.0: Standard softmax (no change)"""
        confidence = 0.75
        tau = 1.0
        
        scaled = router._apply_temperature(confidence, tau)
        assert scaled == confidence  # Should remain unchanged

    def test_nucleus_sampling_rejection_very_low(self, router):
        """Reject very low confidence signals (outside top-p nucleus)"""
        very_low_confidence = 0.05
        top_p = 0.1  # threshold = 1 - 0.1 = 0.9
        
        should_reject = router._should_reject_by_nucleus(very_low_confidence, top_p)
        assert should_reject  # Below threshold

    def test_nucleus_sampling_acceptance_high(self, router):
        """Accept high confidence signals (inside top-p nucleus)"""
        high_confidence = 0.95
        top_p = 0.1  # threshold = 0.9
        
        should_reject = router._should_reject_by_nucleus(high_confidence, top_p)
        assert not should_reject  # Above threshold

    def test_nucleus_sampling_threshold_boundary(self, router):
        """Test boundary condition at nucleus threshold"""
        confidence_at_threshold = 0.9
        top_p = 0.1  # threshold = 1 - 0.1 = 0.9
        
        should_reject = router._should_reject_by_nucleus(confidence_at_threshold, top_p)
        assert not should_reject  # At threshold should pass

    def test_high_volatility_loose_threshold(self, router):
        """High volatility (p=0.5) → loose threshold"""
        confidence = 0.60
        top_p = 0.5  # threshold = 0.5
        
        should_reject = router._should_reject_by_nucleus(confidence, top_p)
        assert not should_reject  # 0.60 > 0.5 → PASS

    def test_low_volatility_strict_threshold(self, router):
        """Low volatility (p=0.1) → strict threshold"""
        confidence = 0.70
        top_p = 0.1  # threshold = 0.9
        
        should_reject = router._should_reject_by_nucleus(confidence, top_p)
        assert should_reject  # 0.70 < 0.9 → REJECT


# ============================================================
# SKIP SAMPLING TESTS (without confidence)
# ============================================================
class TestSkipSampling:
    """ทดสอบการข้าม sampling validation เมื่อไม่มี confidence"""

    def test_skip_sampling_no_confidence(self, router):
        """ถ้าไม่มี confidence → ข้าม sampling → ไป risk check"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Signal",
            # ❌ ไม่มี confidence
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        # confidence = None → ข้าม sampling → ผ่าน risk check
        assert result["status"] == "APPROVED"

    def test_skip_sampling_no_sampling_params(self, router):
        """ถ้าไม่มี sampling_params → ข้าม sampling → ไป risk check"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Signal",
            "confidence": 0.95
            # ❌ ไม่มี sampling_params
        }
        result = router.route(decision)
        # sampling_params = {} → ข้าม sampling → ผ่าน risk check
        assert result["status"] == "APPROVED"

    def test_skip_sampling_empty_sampling_params(self, router):
        """ถ้า sampling_params = {} → ข้าม sampling"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Signal",
            "confidence": 0.5,
            "sampling_params": {}  # Empty dict
        }
        result = router.route(decision)
        # sampling_params empty → ข้าม sampling
        assert result["status"] == "APPROVED"

    def test_no_sampling_no_risk_issue(self, router):
        """ไม่มี confidence แต่ quantity ต่ำ → ผ่าน risk check ได้"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Conservative"
            # ไม่มี confidence หรือ sampling_params
        }
        result = router.route(decision)
        # ข้าม sampling → ไปตรง risk check → APPROVED
        assert result["status"] == "APPROVED"


# ============================================================
# RISK CHECK TESTS (with sampling)
# ============================================================
class TestRiskCheckWithSampling:
    """ทดสอบ risk check หลังจาก pass sampling"""

    def test_pass_sampling_fail_risk_oversized(self, router):
        """Pass sampling แต่ fail risk (oversized position)"""
        decision = {
            "action": "BUY",
            "quantity": 100,  # ❌ Too large
            "reasoning": "Big bet",
            "confidence": 0.95,  # ✅ High confidence
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        # ✅ Pass sampling (0.95 > 0.9)
        # ❌ Fail risk (100 lots > limit)
        assert result["status"] == "REJECTED"
        assert "risk" in result["reason"].lower()

    def test_pass_sampling_pass_risk(self, router):
        """Pass sampling AND pass risk → APPROVED"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Good signal",
            "confidence": 0.95,  # ✅ High confidence
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        # ✅ Pass sampling (0.95 > 0.9)
        # ✅ Pass risk (2 lots < limit)
        assert result["status"] == "APPROVED"

    def test_pass_sampling_fail_risk_zero_quantity(self, router):
        """Pass sampling but quantity = 0 → fail risk"""
        decision = {
            "action": "BUY",
            "quantity": 0,  # ❌ Zero quantity
            "reasoning": "Test",
            "confidence": 0.95,
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        assert result["status"] == "REJECTED"

    def test_pass_sampling_fail_risk_negative_quantity(self, router):
        """Pass sampling but quantity < 0 → fail risk"""
        decision = {
            "action": "BUY",
            "quantity": -5,  # ❌ Negative
            "reasoning": "Test",
            "confidence": 0.95,
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        assert result["status"] == "REJECTED"


# ============================================================
# COMBINED FLOW TESTS
# ============================================================
class TestCombinedFlows:
    """ทดสอบการรวมกันของ sampling + risk check"""

    def test_fail_sampling_skip_risk(self, router):
        """Fail sampling (low confidence) → REJECTED (don't reach risk check)"""
        decision = {
            "action": "BUY",
            "quantity": 2,  # ✅ Within risk limit
            "reasoning": "Weak signal",
            "confidence": 0.05,  # ❌ Very low
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        # ❌ Fail sampling (0.05 < 0.9)
        assert result["status"] == "REJECTED"
        assert "nucleus threshold" in result["reason"].lower()

    def test_high_volatility_loose_sampling(self, router):
        """High volatility (p=0.5) → loose sampling → lower confidence acceptable"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Volatile market",
            "confidence": 0.60,  # ✅ Medium confidence OK with high p
            "sampling_params": {"temperature": 1.8, "top_p": 0.5}  # Loose
        }
        result = router.route(decision)
        # threshold = 1 - 0.5 = 0.5
        # 0.60 > 0.5 ✅ PASS sampling
        # 2 lots within risk ✅ PASS risk
        assert result["status"] == "APPROVED"

    def test_low_volatility_strict_sampling(self, router):
        """Low volatility (p=0.1) → strict sampling → high confidence required"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Stable market",
            "confidence": 0.70,  # ❌ Not high enough for strict sampling
            "sampling_params": {"temperature": 0.5, "top_p": 0.1}  # Strict
        }
        result = router.route(decision)
        # threshold = 1 - 0.1 = 0.9
        # 0.70 < 0.9 ❌ FAIL sampling
        assert result["status"] == "REJECTED"

    def test_sell_with_high_confidence_and_sampling(self, router):
        """SELL action with high confidence + sampling"""
        decision = {
            "action": "SELL",
            "quantity": 1,
            "reasoning": "Take profit",
            "confidence": 0.92,  # ✅ High
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        # ✅ Pass sampling (0.92 > 0.9)
        # ✅ Pass risk (1 lot within limit)
        assert result["status"] == "APPROVED"

    def test_hold_always_passes_sampling(self, router):
        """HOLD action always passes both sampling and risk"""
        decision = {
            "action": "HOLD",
            "quantity": 0,
            "reasoning": "Waiting",
            "confidence": 0.3,  # Even low confidence is OK
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        # HOLD with quantity=0 always passes risk
        assert result["status"] == "APPROVED"

    def test_extreme_volatility_high_temperature(self, router):
        """Extreme volatility → high temperature → lower scaled confidence"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Extreme volatility",
            "confidence": 0.80,
            "sampling_params": {"temperature": 2.0, "top_p": 0.5}  # Very high τ
        }
        result = router.route(decision)
        # With high τ=2.0, confidence gets scaled down
        # But threshold is loose (0.5), so should pass
        # 0.80 > 0.5 (threshold) → should be ok
        assert result["status"] == "APPROVED"

    def test_sampling_info_in_rejection(self, router):
        """Rejection by sampling includes sampling_info"""
        decision = {
            "action": "BUY",
            "quantity": 2,
            "reasoning": "Test",
            "confidence": 0.05,
            "sampling_params": {"temperature": 0.8, "top_p": 0.1}
        }
        result = router.route(decision)
        assert result["status"] == "REJECTED"
        assert "sampling_info" in result  # ✅ Contains sampling details
        assert result["sampling_info"]["temperature"] == 0.8
        assert result["sampling_info"]["top_p"] == 0.1