"""
tests/test_position_sizer.py
Unit tests for execution/position_sizer.py

Run:
    pytest tests/test_position_sizer.py -v
"""

import pytest
from execution.position_sizer import PositionSizer, EVResult, KellyResult

# ---------------------------------------------------------------------------
# Fixture — exact Phase 2 output from the JSON you shared
# ---------------------------------------------------------------------------
PHASE2_DECISION = {
    "signal":       "BUY",
    "confidence":   0.8,
    "entry_price":  2305.8,
    "stop_loss":    2300.0,
    "take_profit":  2318.0,
    "rationale":    (
        "Overwhelming bullish macroeconomic factors (potential Fed rate cuts, "
        "rising geopolitical tensions, weakening dollar) are expected to drive "
        "XAU/USD higher."
    ),
}


@pytest.fixture
def sizer():
    return PositionSizer(balance=100_000, hard_cap_pct=0.10, half_kelly=True)


# ---------------------------------------------------------------------------
# Slide 1 — Expected Value
# ---------------------------------------------------------------------------
class TestExpectedValue:
    def test_ev_positive(self, sizer):
        result = sizer.process(PHASE2_DECISION)
        assert result is not None
        assert result.ev.is_positive_ev

    def test_ev_formula(self, sizer):
        # 𝔼[V] = (0.8 × 12.2) − (0.2 × 5.8) = 9.76 − 1.16 = 8.60
        result = sizer.process(PHASE2_DECISION)
        assert abs(result.ev.expected_value - 8.60) < 0.01

    def test_rr_ratio(self, sizer):
        # R_W / R_L = 12.2 / 5.8 ≈ 2.103
        result = sizer.process(PHASE2_DECISION)
        assert abs(result.ev.risk_reward_ratio - 2.103) < 0.01

    def test_negative_ev_returns_none(self, sizer):
        bad_decision = {**PHASE2_DECISION, "confidence": 0.1}  # very low W
        result = sizer.process(bad_decision)
        assert result is None


# ---------------------------------------------------------------------------
# Slide 2 — Kelly Criterion
# ---------------------------------------------------------------------------
class TestKellyCriterion:
    def test_full_kelly(self, sizer):
        # f* = 0.8 − (0.2 / 2.103) ≈ 0.7049
        result = sizer.process(PHASE2_DECISION)
        assert abs(result.kelly.full_kelly_fraction - 0.7049) < 0.01

    def test_half_kelly(self, sizer):
        # f*/2 ≈ 0.3524
        result = sizer.process(PHASE2_DECISION)
        assert abs(result.kelly.half_kelly_fraction - 0.3524) < 0.01

    def test_hard_cap_applied(self, sizer):
        # half-kelly (35%) > hard_cap (10%) → capped at 0.10
        result = sizer.process(PHASE2_DECISION)
        assert result.kelly.capped_fraction == pytest.approx(0.10, rel=1e-3)

    def test_lots_within_cap(self, sizer):
        # capital = 100_000 × 0.10 = $10,000 → lots = 10_000 / 2305.8 ≈ 4.34
        result = sizer.process(PHASE2_DECISION)
        assert abs(result.kelly.recommended_lots - 4.34) < 0.05

    def test_full_kelly_no_cap(self):
        # Without hard cap to verify pure Kelly math
        sizer_no_cap = PositionSizer(balance=100_000, hard_cap_pct=1.0)
        result = sizer_no_cap.process(PHASE2_DECISION)
        assert result.kelly.capped_fraction == pytest.approx(
            result.kelly.half_kelly_fraction, rel=1e-3
        )


# ---------------------------------------------------------------------------
# Router integration
# ---------------------------------------------------------------------------
class TestRouterOutput:
    def test_to_router_dict_keys(self, sizer):
        result = sizer.process(PHASE2_DECISION)
        d = sizer.to_router_dict(result)
        assert set(d.keys()) == {"action", "quantity", "reasoning"}

    def test_action_matches_signal(self, sizer):
        result = sizer.process(PHASE2_DECISION)
        d = sizer.to_router_dict(result)
        assert d["action"] == "BUY"

    def test_quantity_positive(self, sizer):
        result = sizer.process(PHASE2_DECISION)
        d = sizer.to_router_dict(result)
        assert d["quantity"] > 0

    def test_hold_passthrough(self, sizer):
        hold = {**PHASE2_DECISION, "signal": "HOLD", "confidence": 0.5}
        result = sizer.process(hold)
        # HOLD still has positive EV with W=0.5, should pass through
        assert result is not None
        assert result.action == "HOLD"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_stop_loss_equals_entry_returns_none(self, sizer):
        bad = {**PHASE2_DECISION, "stop_loss": 2305.8}  # R_L = 0
        result = sizer.process(bad)
        assert result is None

    def test_zero_confidence_returns_none(self, sizer):
        bad = {**PHASE2_DECISION, "confidence": 0.0}
        result = sizer.process(bad)
        assert result is None
