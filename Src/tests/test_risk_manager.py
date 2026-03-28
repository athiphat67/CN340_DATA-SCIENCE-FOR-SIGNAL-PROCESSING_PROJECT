"""
test_risk_manager.py — Unit tests for RiskManager.validate_and_adjust()
Covers: BUY cash constraints, SL/TP validation, SELL constraints, HOLD, invalid signals.
"""

import pytest
from agent_core.core.risk_manager import RiskManager, RiskConfig


# ─── Helpers ────────────────────────────────────────────────────────────────

def _portfolio(cash: float = 1500.0, gold_grams: float = 0.0) -> dict:
    return {"cash_balance": cash, "gold_grams": gold_grams}


def _decision(signal: str = "BUY", **kwargs) -> dict:
    d = {"signal": signal, "confidence": 0.8, "rationale": "test"}
    d.update(kwargs)
    return d


# ─── BUY — Cash Constraints ─────────────────────────────────────────────────

class TestBuyCashConstraints:

    def test_buy_sufficient_cash_passes(self):
        """cash=1500 >= 1000 → BUY passes, amount_thb set to 1500."""
        rm = RiskManager()
        result = rm.validate_and_adjust(_decision("BUY"), _portfolio(cash=1500.0), current_price=2300.0)
        assert result["signal"] == "BUY"
        assert result["amount_thb"] == 1500.0

    def test_buy_insufficient_cash_rejected_to_hold(self):
        """cash=500 < 1000 → rejected to HOLD."""
        rm = RiskManager()
        result = rm.validate_and_adjust(_decision("BUY"), _portfolio(cash=500.0), current_price=2300.0)
        assert result["signal"] == "HOLD"
        assert result["risk_adjusted"] is True

    def test_buy_amount_capped_at_max_position_size(self):
        """cash=1500, amount_thb=9999, max_position_size_pct=0.8 → capped to 1200."""
        config = RiskConfig(max_position_size_pct=0.8)
        rm = RiskManager(config)
        result = rm.validate_and_adjust(
            _decision("BUY", amount_thb=9999.0),
            _portfolio(cash=1500.0),
            current_price=2300.0,
        )
        assert result["signal"] == "BUY"
        assert result["amount_thb"] == 1200.0
        assert result["risk_adjusted"] is True


# ─── BUY — Stop Loss / Take Profit Validation ────────────────────────────────

class TestBuySLTP:

    def test_buy_sl_above_entry_removed(self):
        """SL=2400 >= entry=2300 → SL removed."""
        rm = RiskManager()
        result = rm.validate_and_adjust(
            _decision("BUY", entry_price=2300.0, stop_loss=2400.0),
            _portfolio(cash=1500.0),
            current_price=2300.0,
        )
        assert result["signal"] == "BUY"
        assert result["stop_loss"] is None
        assert result["risk_adjusted"] is True

    def test_buy_sl_risk_too_high_adjusted(self):
        """entry=2300, SL=2100 → risk=8.7% > 5% → SL adjusted to 2185."""
        rm = RiskManager()
        result = rm.validate_and_adjust(
            _decision("BUY", entry_price=2300.0, stop_loss=2100.0),
            _portfolio(cash=1500.0),
            current_price=2300.0,
        )
        assert result["signal"] == "BUY"
        assert result["risk_adjusted"] is True
        expected_sl = 2300.0 * (1 - 0.05)
        assert abs(result["stop_loss"] - expected_sl) < 0.01

    def test_buy_tp_below_entry_removed(self):
        """TP=2200 <= entry=2300 → TP removed."""
        rm = RiskManager()
        result = rm.validate_and_adjust(
            _decision("BUY", entry_price=2300.0, take_profit=2200.0),
            _portfolio(cash=1500.0),
            current_price=2300.0,
        )
        assert result["signal"] == "BUY"
        assert result["take_profit"] is None
        assert result["risk_adjusted"] is True


# ─── SELL ────────────────────────────────────────────────────────────────────

class TestSell:

    def test_sell_no_gold_rejected_to_hold(self):
        """gold_grams=0 → no gold to sell → HOLD."""
        rm = RiskManager()
        result = rm.validate_and_adjust(_decision("SELL"), _portfolio(gold_grams=0.0), current_price=2300.0)
        assert result["signal"] == "HOLD"
        assert result["risk_adjusted"] is True

    def test_sell_grams_capped_at_available(self):
        """grams=2.0 > gold_grams=0.5 → capped to 0.5."""
        rm = RiskManager()
        result = rm.validate_and_adjust(
            _decision("SELL", grams=2.0),
            _portfolio(gold_grams=0.5),
            current_price=2300.0,
        )
        assert result["signal"] == "SELL"
        assert result["grams"] == 0.5
        assert result["risk_adjusted"] is True


# ─── HOLD ────────────────────────────────────────────────────────────────────

class TestHold:

    def test_hold_passes_through_unchanged(self):
        """HOLD signal should pass through with risk_adjusted=False."""
        rm = RiskManager()
        result = rm.validate_and_adjust(_decision("HOLD"), _portfolio(), current_price=2300.0)
        assert result["signal"] == "HOLD"
        assert result["risk_adjusted"] is False
        assert result["risk_notes"] == []


# ─── Signal Validation ───────────────────────────────────────────────────────

class TestSignalValidation:

    def test_invalid_signal_converted_to_hold(self):
        """Unknown signal "MAYBE" → normalized to HOLD."""
        rm = RiskManager()
        result = rm.validate_and_adjust(_decision("MAYBE"), _portfolio(), current_price=2300.0)
        assert result["signal"] == "HOLD"
