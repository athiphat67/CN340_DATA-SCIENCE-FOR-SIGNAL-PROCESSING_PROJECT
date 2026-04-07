"""
test_risk.py — Pytest สำหรับทดสอบ RiskManager

Strategy: 100% Real (ไม่มี mock)
- RiskManager.evaluate() รับ 2 dicts (llm_decision, market_state) → คืน dict
- record_trade_result() รับ float + str → เปลี่ยน internal state
- ไม่มี I/O ใดๆ (ไม่มี API, DB, HTTP, file)

ครอบคลุม:
  1. Init & defaults
  2. Confidence filter — ต่ำกว่า threshold → reject
  3. Daily loss limit — สะสมขาดทุนถึง limit → หยุดเทรด
  4. BUY signal — position sizing, SL/TP, micro-port
  5. SELL signal — ต้องมี gold, ไม่มี → reject
  6. HOLD signal — pass-through ไม่แก้ไข
  7. Invalid signal — reject
  8. Missing market data — reject
  9. record_trade_result — reset วันใหม่
  10. _reject_signal — ไม่ mutate dict ต้นฉบับ
"""

import pytest

from agent_core.core.risk import RiskManager


# ══════════════════════════════════════════════════════════════════
# Helpers — สร้าง input dicts ที่ RiskManager.evaluate() คาดหวัง
# ══════════════════════════════════════════════════════════════════


def _decision(signal="BUY", confidence=0.8, rationale="Test rationale"):
    return {"signal": signal, "confidence": confidence, "rationale": rationale}


def _market(
    cash=5000.0,
    gold_grams=0.0,
    sell_price=72000.0,  # ร้านขายให้เรา (เราซื้อ)
    buy_price=71800.0,  # ร้านรับซื้อจากเรา (เราขาย)
    atr=150.0,
    atr_unit="THB",
    date="2026-04-06",
):
    """สร้าง market_state dict ตาม structure ที่ evaluate() ต้องการ"""
    return {
        "date": date,
        "portfolio": {
            "cash_balance": cash,
            "gold_grams": gold_grams,
        },
        "market_data": {
            "thai_gold_thb": {
                "sell_price_thb": sell_price,
                "buy_price_thb": buy_price,
                "spot_price_thb": sell_price,
            },
        },
        "technical_indicators": {
            "atr": {"value": atr, "unit": atr_unit},
        },
    }


# ══════════════════════════════════════════════════════════════════
# 1. Init & Defaults
# ══════════════════════════════════════════════════════════════════


class TestInit:
    def test_default_values(self):
        rm = RiskManager()
        assert rm.atr_multiplier == 2.0
        assert rm.rr_ratio == 1.5
        assert rm.min_confidence == 0.6
        assert rm.min_trade_thb == 1000.0
        assert rm.max_daily_loss_thb == 500.0
        assert rm.max_trade_risk_pct == 0.30

    def test_custom_values(self):
        rm = RiskManager(min_confidence=0.7, max_daily_loss_thb=300.0)
        assert rm.min_confidence == 0.7
        assert rm.max_daily_loss_thb == 300.0

    def test_daily_loss_starts_at_zero(self):
        rm = RiskManager()
        assert rm._daily_loss_accumulated == 0.0
        assert rm._daily_loss_date == ""


# ══════════════════════════════════════════════════════════════════
# 2. Confidence Filter
# ══════════════════════════════════════════════════════════════════


class TestConfidenceFilter:
    """ด่านที่ 1 — confidence < min_confidence → reject to HOLD"""

    def test_low_confidence_rejected(self):
        """confidence 0.3 < threshold 0.6 → reject"""
        rm = RiskManager(min_confidence=0.6)
        result = rm.evaluate(_decision(confidence=0.3), _market())
        assert result["signal"] == "HOLD"
        assert result["rejection_reason"] is not None
        assert "Confidence" in result["rejection_reason"]

    def test_exact_threshold_passes(self):
        """confidence = 0.6 = threshold → pass (ใช้ < ไม่ใช่ <=)"""
        rm = RiskManager(min_confidence=0.6)
        result = rm.evaluate(_decision(confidence=0.6), _market())
        assert result["signal"] == "BUY"
        assert result["rejection_reason"] is None

    def test_above_threshold_passes(self):
        """confidence 0.9 > threshold 0.6 → pass"""
        rm = RiskManager(min_confidence=0.6)
        result = rm.evaluate(_decision(confidence=0.9), _market())
        assert result["signal"] == "BUY"

    def test_hold_bypasses_confidence(self):
        """HOLD ไม่ถูก check confidence — ผ่านเสมอ"""
        rm = RiskManager(min_confidence=0.6)
        result = rm.evaluate(_decision(signal="HOLD", confidence=0.1), _market())
        assert result["signal"] == "HOLD"
        assert result["rejection_reason"] is None


# ══════════════════════════════════════════════════════════════════
# 3. Daily Loss Limit
# ══════════════════════════════════════════════════════════════════


class TestDailyLossLimit:
    """ด่านที่ 2 — สะสมขาดทุนถึง limit → หยุดเทรดวันนี้"""

    def test_loss_accumulates(self):
        rm = RiskManager(max_daily_loss_thb=500.0)
        rm.record_trade_result(-200.0, "2026-04-06")
        assert rm._daily_loss_accumulated == 200.0

        rm.record_trade_result(-150.0, "2026-04-06")
        assert rm._daily_loss_accumulated == 350.0

    def test_profit_does_not_accumulate(self):
        """กำไรไม่เพิ่ม daily loss"""
        rm = RiskManager()
        rm.record_trade_result(100.0, "2026-04-06")
        assert rm._daily_loss_accumulated == 0.0

    def test_loss_limit_rejects_trade(self):
        """สะสมขาดทุน >= 500 → reject trade ถัดไป"""
        rm = RiskManager(max_daily_loss_thb=500.0)
        rm.record_trade_result(-500.0, "2026-04-06")

        result = rm.evaluate(
            _decision(confidence=0.9),
            _market(date="2026-04-06"),
        )
        assert result["signal"] == "HOLD"
        assert "Daily loss limit" in result["rejection_reason"]

    def test_new_day_resets_loss(self):
        """วันใหม่ → reset daily loss → เทรดได้อีก"""
        rm = RiskManager(max_daily_loss_thb=500.0)
        rm.record_trade_result(-500.0, "2026-04-06")

        # วันถัดไป → reset
        result = rm.evaluate(
            _decision(confidence=0.9),
            _market(date="2026-04-07"),
        )
        assert result["signal"] == "BUY"

    def test_hold_bypasses_daily_limit(self):
        """HOLD ไม่ถูก check daily loss"""
        rm = RiskManager(max_daily_loss_thb=500.0)
        rm.record_trade_result(-600.0, "2026-04-06")

        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(date="2026-04-06"),
        )
        assert result["signal"] == "HOLD"
        assert result["rejection_reason"] is None


# ══════════════════════════════════════════════════════════════════
# 4. BUY Signal — Position Sizing & SL/TP
# ══════════════════════════════════════════════════════════════════


class TestBuySignal:
    """ด่านที่ 3-5 — BUY: position sizing, ATR-based SL/TP"""

    def test_buy_approved(self):
        """BUY ปกติ — ได้ position_size, SL, TP"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.8),
            _market(cash=5000.0, atr=150.0),
        )
        assert result["signal"] == "BUY"
        assert result["position_size_thb"] > 0
        assert result["stop_loss"] > 0
        assert result["take_profit"] > 0
        assert result["rejection_reason"] is None

    def test_buy_entry_is_sell_price(self):
        """entry_price ต้อง = sell_price_thb (ราคาที่ร้านขายให้เรา)"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.8),
            _market(sell_price=72000.0),
        )
        assert result["entry_price"] == 72000.0

    def test_sl_tp_based_on_atr(self):
        """SL = entry - ATR*2, TP = entry + ATR*2*1.5"""
        rm = RiskManager(atr_multiplier=2.0, risk_reward_ratio=1.5)
        atr = 100.0
        entry = 72000.0
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.8),
            _market(sell_price=entry, atr=atr),
        )
        expected_sl = entry - (atr * 2.0)  # 72000 - 200 = 71800
        expected_tp = entry + (atr * 2.0 * 1.5)  # 72000 + 300 = 72300
        assert result["stop_loss"] == expected_sl
        assert result["take_profit"] == expected_tp

    def test_normal_port_sizing(self):
        """พอร์ตปกติ (>= 2000): position = cash * 0.5 * confidence"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.8),
            _market(cash=5000.0),
        )
        # 5000 * 0.5 * 0.8 = 2000
        assert result["position_size_thb"] == 2000.0

    def test_micro_port_uses_fixed_min(self):
        """พอร์ตเล็ก (< 2000): ใช้ min_trade_thb คงที่"""
        rm = RiskManager(min_trade_thb=1000.0, micro_port_threshold=2000.0)
        result = rm.evaluate(
            _decision(confidence=0.9),
            _market(cash=1500.0),
        )
        assert result["position_size_thb"] == 1000.0

    def test_position_capped_at_cash(self):
        """position ต้องไม่เกิน cash ที่มี"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.99),
            _market(cash=3000.0),
        )
        # 3000 * 0.5 * 0.99 = 1485 → ไม่เกิน 3000 ✓
        assert result["position_size_thb"] <= 3000.0

    def test_too_small_position_rejected(self):
        """position คำนวณได้ < min_trade_thb → reject"""
        rm = RiskManager(min_trade_thb=1000.0)
        # cash=2500, 2500*0.5*0.6=750 < 1000 → reject
        result = rm.evaluate(
            _decision(confidence=0.6),
            _market(cash=2500.0),
        )
        assert result["signal"] == "HOLD"
        assert "ต่ำกว่าขั้นต่ำ" in result["rejection_reason"]

    def test_rationale_includes_risk_info(self):
        """rationale ต้องมี RiskManager annotation"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.8, rationale="Gold bullish"),
            _market(),
        )
        assert "RiskManager" in result["rationale"]
        assert "SL:" in result["rationale"]


# ══════════════════════════════════════════════════════════════════
# 5. SELL Signal
# ══════════════════════════════════════════════════════════════════


class TestSellSignal:
    """SELL: ต้องมีทอง, entry = buy_price_thb (ราคาที่ร้านรับซื้อ)"""

    def test_sell_with_gold(self):
        """มีทอง → SELL อนุมัติ"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="SELL", confidence=0.8),
            _market(gold_grams=1.0, buy_price=71800.0),
        )
        assert result["signal"] == "SELL"
        assert result["entry_price"] == 71800.0
        assert result["position_size_thb"] > 0

    def test_sell_position_based_on_gold_value(self):
        """position_size = gold_grams * (sell_price / 15.244)"""
        rm = RiskManager()
        gold = 0.5
        buy_price = 71800.0
        result = rm.evaluate(
            _decision(signal="SELL", confidence=0.8),
            _market(gold_grams=gold, buy_price=buy_price),
        )
        expected = round(gold * (buy_price / 15.244), 2)
        assert result["position_size_thb"] == expected

    def test_sell_no_gold_rejected(self):
        """ไม่มีทอง → reject (No Shorting)"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="SELL", confidence=0.9),
            _market(gold_grams=0.0),
        )
        assert result["signal"] == "HOLD"
        assert "ไม่มีทอง" in result["rejection_reason"]

    def test_sell_tiny_gold_rejected(self):
        """ทองน้อยมาก (< 0.0001) → ถือว่าไม่มี"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="SELL", confidence=0.9),
            _market(gold_grams=0.00001),
        )
        assert result["signal"] == "HOLD"


# ══════════════════════════════════════════════════════════════════
# 6. HOLD Signal
# ══════════════════════════════════════════════════════════════════


class TestHoldSignal:
    """HOLD → pass-through, ไม่คำนวณ SL/TP, ไม่ reject"""

    def test_hold_passthrough(self):
        rm = RiskManager()
        result = rm.evaluate(_decision(signal="HOLD"), _market())
        assert result["signal"] == "HOLD"
        assert result["rejection_reason"] is None
        assert result["position_size_thb"] == 0.0

    def test_hold_with_low_confidence(self):
        """HOLD + confidence ต่ำ → ยังผ่าน (ไม่ถูก confidence check)"""
        rm = RiskManager(min_confidence=0.9)
        result = rm.evaluate(
            _decision(signal="HOLD", confidence=0.1),
            _market(),
        )
        assert result["signal"] == "HOLD"
        assert result["rejection_reason"] is None


# ══════════════════════════════════════════════════════════════════
# 7. Invalid / Unknown Signal
# ══════════════════════════════════════════════════════════════════


class TestInvalidSignal:
    def test_unknown_signal_rejected(self):
        """signal ที่ไม่รู้จัก → reject"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="YOLO", confidence=0.9),
            _market(),
        )
        assert result["signal"] == "HOLD"
        assert "ไม่รู้จัก" in result["rejection_reason"]


# ══════════════════════════════════════════════════════════════════
# 8. Missing / Bad Market Data
# ══════════════════════════════════════════════════════════════════


class TestBadMarketData:
    """market_state ไม่ครบ → reject อย่างปลอดภัย"""

    def test_missing_market_data_key(self):
        """ไม่มี market_data → reject"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.9),
            {
                "date": "2026-04-06",
                "portfolio": {"cash_balance": 5000, "gold_grams": 0},
                "technical_indicators": {"atr": {"value": 100, "unit": "THB"}},
            },
        )
        assert result["signal"] == "HOLD"
        assert result["rejection_reason"] is not None

    def test_missing_atr(self):
        """ไม่มี technical_indicators.atr → reject"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.9),
            {
                "date": "2026-04-06",
                "portfolio": {"cash_balance": 5000, "gold_grams": 0},
                "market_data": {
                    "thai_gold_thb": {"sell_price_thb": 72000, "buy_price_thb": 71800}
                },
            },
        )
        assert result["signal"] == "HOLD"

    def test_zero_price_rejected(self):
        """ราคาทอง = 0 → reject"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.9),
            _market(sell_price=0.0),
        )
        assert result["signal"] == "HOLD"
        assert "ข้อมูลตลาด" in result["rejection_reason"]


# ══════════════════════════════════════════════════════════════════
# 9. record_trade_result — Daily Loss Tracking
# ══════════════════════════════════════════════════════════════════


class TestRecordTradeResult:
    def test_accumulates_losses(self):
        rm = RiskManager()
        rm.record_trade_result(-100, "2026-04-06")
        rm.record_trade_result(-200, "2026-04-06")
        assert rm._daily_loss_accumulated == 300.0

    def test_ignores_profits(self):
        rm = RiskManager()
        rm.record_trade_result(-100, "2026-04-06")
        rm.record_trade_result(500, "2026-04-06")  # กำไร → ไม่เปลี่ยน
        assert rm._daily_loss_accumulated == 100.0

    def test_resets_on_new_day(self):
        rm = RiskManager()
        rm.record_trade_result(-400, "2026-04-06")
        assert rm._daily_loss_accumulated == 400.0

        rm.record_trade_result(-50, "2026-04-07")  # วันใหม่
        assert rm._daily_loss_accumulated == 50.0
        assert rm._daily_loss_date == "2026-04-07"


# ══════════════════════════════════════════════════════════════════
# 10. _reject_signal — ไม่ mutate dict ต้นฉบับ
# ══════════════════════════════════════════════════════════════════


class TestRejectSignalSafety:
    """_reject_signal ต้องคืน copy ใหม่ ไม่แก้ dict เดิม"""

    def test_does_not_mutate_input(self):
        rm = RiskManager()
        original = {
            "signal": "BUY",
            "confidence": 0.9,
            "rationale": "Original",
            "position_size_thb": 1000.0,
            "stop_loss": 71000.0,
            "take_profit": 73000.0,
            "rejection_reason": None,
        }
        rejected = rm._reject_signal(original, "Test reason")

        # original ต้องไม่ถูกแก้ไข
        assert original["signal"] == "BUY"
        assert original["position_size_thb"] == 1000.0
        assert original["rejection_reason"] is None

        # rejected ต้องถูกแก้
        assert rejected["signal"] == "HOLD"
        assert rejected["position_size_thb"] == 0.0
        assert rejected["rejection_reason"] == "Test reason"
