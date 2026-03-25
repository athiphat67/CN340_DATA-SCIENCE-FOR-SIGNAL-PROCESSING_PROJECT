"""
tests/test_rules.py
pytest suite — run with: pytest tests/test_rules.py -v
"""

import pytest
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
