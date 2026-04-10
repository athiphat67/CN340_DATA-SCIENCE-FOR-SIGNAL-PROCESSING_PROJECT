"""
test_risk.py — Pytest สำหรับทดสอบ RiskManager
══════════════════════════════════════════════════════════════════════
Strategy: 100% Real (ไม่มี mock)
- RiskManager.evaluate() รับ 2 dicts (llm_decision, market_state) → คืน dict
- record_trade_result() รับ float + str → เปลี่ยน internal state
- ไม่มี I/O ใดๆ (ไม่มี API, DB, HTTP, file)

ครอบคลุม:
  1.  Init & defaults
  2.  Confidence filter — ต่ำกว่า threshold → reject
  3.  Daily loss limit — สะสมขาดทุนถึง limit → หยุดเทรด
  4.  BUY signal — position sizing, SL/TP, micro-port
  5.  SELL signal — ต้องมี gold, ไม่มี → reject
  6.  HOLD signal — pass-through ไม่แก้ไข
  7.  Invalid signal — reject
  8.  Missing market data — reject
  9.  record_trade_result — reset วันใหม่
  10. _reject_signal — ไม่ mutate dict ต้นฉบับ
  --- Hard Rules (เพิ่มใหม่) ---
  11. Dead Zone (02:00–06:14) — reject ทุก signal
  12. Danger Zone (01:30–01:59) + gold > 0 — บังคับ SELL
  13. SL1: unrealized_pnl <= -150 — บังคับ SELL
  14. SL2: unrealized_pnl <= -80 + RSI < 35 — บังคับ SELL
  15. TP1: unrealized_pnl >= 300 — บังคับ SELL
  16. TP2: unrealized_pnl >= 150 + RSI > 65 — บังคับ SELL
  17. TP3: unrealized_pnl >= 100 + macd_hist < 0 — บังคับ SELL
  18. Hard Rule Override behavior
══════════════════════════════════════════════════════════════════════
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
    sell_price=72000.0,   # ร้านขายให้เรา (เราซื้อ)
    buy_price=71800.0,    # ร้านรับซื้อจากเรา (เราขาย)
    atr=150.0,
    atr_unit="THB",
    date="2026-04-06",
    time="12:00",
    unrealized_pnl=0.0,
    rsi=50.0,
    macd_hist=0.0,
):
    """สร้าง market_state dict ตาม structure ที่ evaluate() ต้องการ"""
    return {
        "time": time,
        "date": date,
        "portfolio": {
            "cash_balance": cash,
            "gold_grams": gold_grams,
            "unrealized_pnl": unrealized_pnl,
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
            "rsi": {"value": rsi},
            "macd": {"histogram": macd_hist},
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

    def test_daily_loss_does_not_block_sell(self):
        """Daily loss ถึง limit → ปิดแค่ BUY ไม่ปิด SELL"""
        rm = RiskManager(max_daily_loss_thb=100.0)
        rm.record_trade_result(-200.0, "2026-04-06")

        result = rm.evaluate(
            _decision(signal="SELL", confidence=0.9),
            _market(gold_grams=1.0, date="2026-04-06"),
        )
        # SELL ต้องไม่ถูก block เพราะ daily loss limit
        assert result["signal"] == "SELL"


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
        expected_sl = entry - (atr * 2.0)   # 72000 - 200 = 71800
        expected_tp = entry + (atr * 2.0 * 1.5)  # 72000 + 300 = 72300
        assert result["stop_loss"] == expected_sl
        assert result["take_profit"] == expected_tp

    def test_normal_port_sizing(self):
        """position size = 1000 THB fixed ตาม logic จริงของ risk.py"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.8),
            _market(cash=5000.0),
        )
        assert result["position_size_thb"] == 1000.0

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
        assert result["position_size_thb"] <= 3000.0

    def test_rationale_includes_risk_info(self):
        """rationale ต้องมี RiskManager annotation"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(confidence=0.8, rationale="Gold bullish"),
            _market(),
        )
        assert "RiskManager" in result["rationale"]


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


# ══════════════════════════════════════════════════════════════════
# 11. Dead Zone (02:00–06:14) — ห้ามเทรดเด็ดขาด
# ══════════════════════════════════════════════════════════════════


class TestDeadZone:
    """Dead Zone: ห้ามเทรดทุก signal ใน 02:00–06:14"""

    def test_dead_zone_rejects_buy(self):
        """02:30 → Dead zone → BUY ถูก reject"""
        rm = RiskManager()
        result = rm.evaluate(_decision(signal="BUY"), _market(time="02:30"))
        assert result["signal"] == "HOLD"
        assert result["rejection_reason"] is not None
        assert "Dead Zone" in result["rejection_reason"]

    def test_dead_zone_rejects_sell(self):
        """03:00 → Dead zone → SELL ก็ถูก reject"""
        rm = RiskManager()
        result = rm.evaluate(_decision(signal="SELL"), _market(time="03:00"))
        assert result["signal"] == "HOLD"

    def test_dead_zone_rejects_hold(self):
        """Dead zone → HOLD ก็ถูก reject (ห้ามเทรดทุกรูปแบบ)"""
        rm = RiskManager()
        result = rm.evaluate(_decision(signal="HOLD"), _market(time="04:00"))
        assert result["rejection_reason"] is not None

    def test_dead_zone_start_boundary_0200(self):
        """02:00 คือจุดเริ่ม Dead zone (inclusive) → reject"""
        rm = RiskManager()
        result = rm.evaluate(_decision(signal="BUY"), _market(time="02:00"))
        assert result["signal"] == "HOLD"

    def test_dead_zone_end_boundary_0614(self):
        """06:14 ยังอยู่ใน Dead zone → reject"""
        rm = RiskManager()
        result = rm.evaluate(_decision(signal="BUY"), _market(time="06:14"))
        assert result["signal"] == "HOLD"

    def test_just_before_dead_zone_0159_no_dead_reject(self):
        """01:59 ยังไม่เข้า Dead zone → ไม่โดน reject ด้วยเหตุ Dead Zone"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.9),
            _market(time="01:59", cash=5000.0),
        )
        if result["rejection_reason"]:
            assert "Dead Zone" not in result["rejection_reason"]

    def test_just_after_dead_zone_0615_no_dead_reject(self):
        """06:15 พ้น Dead zone → ไม่โดน reject ด้วยเหตุ Dead Zone"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.9),
            _market(time="06:15", cash=5000.0),
        )
        if result["rejection_reason"]:
            assert "Dead Zone" not in result["rejection_reason"]


# ══════════════════════════════════════════════════════════════════
# 12. Danger Zone (01:30–01:59) + gold > 0 — บังคับ SELL
# ══════════════════════════════════════════════════════════════════


class TestDangerZone:
    """Danger Zone: 01:30–01:59 + ถือทองอยู่ → บังคับ SELL เคลียร์พอร์ต"""

    def test_danger_zone_forces_sell_when_holding_gold(self):
        """01:45 + gold > 0 → override เป็น SELL"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.9),
            _market(time="01:45", gold_grams=1.0, cash=5000.0),
        )
        assert result["signal"] == "SELL"
        assert (
            "SL3" in result["rationale"]
            or "Danger Zone" in result["rationale"]
            or "danger" in result["rationale"].lower()
        )

    def test_danger_zone_no_gold_no_override(self):
        """01:45 + ไม่มีทอง → ไม่ override"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.9),
            _market(time="01:45", gold_grams=0.0, cash=5000.0),
        )
        assert "Danger Zone" not in (result.get("rationale") or "")

    def test_danger_zone_boundary_0130(self):
        """01:30 คือจุดเริ่ม Danger Zone + มีทอง → บังคับ SELL"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(time="01:30", gold_grams=1.0),
        )
        assert result["signal"] == "SELL"

    def test_danger_zone_boundary_0159(self):
        """01:59 ยังอยู่ใน Danger Zone + มีทอง → บังคับ SELL"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(time="01:59", gold_grams=1.0),
        )
        assert result["signal"] == "SELL"

    def test_override_sets_confidence_to_one(self):
        """Hard Rule override ต้อง set confidence = 1.0"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.7),
            _market(time="01:45", gold_grams=1.0),
        )
        assert result["signal"] == "SELL"
        assert result["confidence"] == 1.0


# ══════════════════════════════════════════════════════════════════
# 13. SL1: unrealized_pnl <= -150 — บังคับ SELL
# ══════════════════════════════════════════════════════════════════


class TestStopLoss1:
    """SL1: ขาดทุน >= 150 บาท → บังคับ SELL ทันที"""

    def test_sl1_triggers_at_minus_150(self):
        """unrealized_pnl = -150 → SL1"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY"),
            _market(gold_grams=1.0, unrealized_pnl=-150),
        )
        assert result["signal"] == "SELL"
        assert "SL1" in result["rationale"]

    def test_sl1_triggers_well_below_limit(self):
        """unrealized_pnl = -300 → SL1"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=-300),
        )
        assert result["signal"] == "SELL"

    def test_sl1_does_not_trigger_at_minus_149(self):
        """unrealized_pnl = -149 → ยังไม่ถึง SL1"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=-149),
        )
        assert "SL1" not in (result.get("rationale") or "")

    def test_sl1_no_gold_no_trigger(self):
        """ไม่มีทอง → SL1 ไม่ trigger"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY"),
            _market(gold_grams=0.0, unrealized_pnl=-200, cash=5000.0),
        )
        assert "SL1" not in (result.get("rationale") or "")

    def test_sl1_override_confidence_is_one(self):
        """SL1 override → confidence = 1.0"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.6),
            _market(gold_grams=1.0, unrealized_pnl=-200),
        )
        assert result["confidence"] == 1.0


# ══════════════════════════════════════════════════════════════════
# 14. SL2: unrealized_pnl <= -80 + RSI < 35
# ══════════════════════════════════════════════════════════════════


class TestStopLoss2:
    """SL2: ขาดทุน >= 80 + RSI < 35 → บังคับ SELL"""

    def test_sl2_triggers_with_both_conditions(self):
        """unrealized_pnl = -80 + RSI = 30 → SL2"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY"),
            _market(gold_grams=1.0, unrealized_pnl=-80, rsi=30),
        )
        assert result["signal"] == "SELL"
        assert "SL2" in result["rationale"]

    def test_sl2_no_trigger_pnl_not_enough(self):
        """unrealized_pnl = -50 (ยังไม่ถึง -80) → ไม่ trigger SL2"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=-50, rsi=30),
        )
        assert "SL2" not in (result.get("rationale") or "")

    def test_sl2_no_trigger_rsi_not_low_enough(self):
        """unrealized_pnl = -80 + RSI = 36 (ไม่ต่ำพอ) → ไม่ trigger SL2"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=-80, rsi=36),
        )
        assert "SL2" not in (result.get("rationale") or "")


# ══════════════════════════════════════════════════════════════════
# 15. TP1: unrealized_pnl >= 300 — บังคับ SELL ทำกำไร
# ══════════════════════════════════════════════════════════════════


class TestTakeProfit1:
    """TP1: กำไร >= 300 บาท → บังคับ SELL"""

    def test_tp1_triggers_at_300(self):
        """unrealized_pnl = 300 → TP1"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=300),
        )
        assert result["signal"] == "SELL"
        assert "TP1" in result["rationale"]

    def test_tp1_triggers_above_300(self):
        """unrealized_pnl = 500 → TP1"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY"),
            _market(gold_grams=1.0, unrealized_pnl=500),
        )
        assert result["signal"] == "SELL"

    def test_tp1_no_trigger_at_299(self):
        """unrealized_pnl = 299 → ยังไม่ถึง TP1"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=299),
        )
        assert "TP1" not in (result.get("rationale") or "")

    def test_tp1_override_confidence_is_one(self):
        """TP1 override → confidence = 1.0"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY", confidence=0.5),
            _market(gold_grams=1.0, unrealized_pnl=300),
        )
        assert result["confidence"] == 1.0


# ══════════════════════════════════════════════════════════════════
# 16. TP2: unrealized_pnl >= 150 + RSI > 65
# ══════════════════════════════════════════════════════════════════


class TestTakeProfit2:
    """TP2: กำไร >= 150 + RSI > 65 → บังคับ SELL"""

    def test_tp2_triggers_with_both_conditions(self):
        """unrealized_pnl = 150 + RSI = 70 → TP2"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=150, rsi=70),
        )
        assert result["signal"] == "SELL"
        assert "TP2" in result["rationale"]

    def test_tp2_no_trigger_rsi_at_boundary(self):
        """unrealized_pnl = 150 + RSI = 65 (ไม่ > 65, เท่ากัน) → ไม่ trigger"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=150, rsi=65),
        )
        assert "TP2" not in (result.get("rationale") or "")

    def test_tp2_no_trigger_pnl_too_low(self):
        """unrealized_pnl = 149 + RSI สูง → ไม่ trigger TP2"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=149, rsi=80),
        )
        assert "TP2" not in (result.get("rationale") or "")


# ══════════════════════════════════════════════════════════════════
# 17. TP3: unrealized_pnl >= 100 + macd_hist < 0
# ══════════════════════════════════════════════════════════════════


class TestTakeProfit3:
    """TP3: กำไร >= 100 + MACD histogram < 0 → บังคับ SELL"""

    def test_tp3_triggers_with_both_conditions(self):
        """unrealized_pnl = 100 + macd_hist = -10 → TP3"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=100, macd_hist=-10),
        )
        assert result["signal"] == "SELL"
        assert "TP3" in result["rationale"]

    def test_tp3_no_trigger_macd_positive(self):
        """unrealized_pnl = 100 + macd_hist = 5 → ไม่ trigger TP3"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=100, macd_hist=5),
        )
        assert "TP3" not in (result.get("rationale") or "")

    def test_tp3_no_trigger_pnl_too_low(self):
        """unrealized_pnl = 99 + macd_hist ลบ → ไม่ trigger TP3"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=99, macd_hist=-5),
        )
        assert "TP3" not in (result.get("rationale") or "")


# ══════════════════════════════════════════════════════════════════
# 18. Hard Rule Override Behavior
# ══════════════════════════════════════════════════════════════════


class TestHardRuleOverrideBehavior:
    """ทดสอบ behavior ทั่วไปของ Hard Rule Override"""

    def test_override_marks_rationale_as_system(self):
        """rationale ต้องบ่งบอกว่าเป็น SYSTEM OVERRIDE"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="HOLD"),
            _market(gold_grams=1.0, unrealized_pnl=300),
        )
        assert "SYSTEM OVERRIDE" in result["rationale"] or "OVERRIDE" in result["rationale"].upper()

    def test_override_mentions_original_llm_signal(self):
        """rationale ต้องบอกว่า LLM เดิมสั่งอะไร"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY"),
            _market(gold_grams=1.0, unrealized_pnl=-200),
        )
        assert "BUY" in result["rationale"] or "SYSTEM OVERRIDE" in result["rationale"]

    def test_override_passes_sell_process_with_position_size(self):
        """หลัง override เป็น SELL → position_size_thb > 0"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY"),
            _market(gold_grams=2.0, unrealized_pnl=-200),
        )
        assert result["signal"] == "SELL"
        assert result["position_size_thb"] > 0

    def test_sl1_takes_priority_over_tp(self):
        """pnl = -150 (ติดลบ) → SL1 trigger ไม่ใช่ TP"""
        rm = RiskManager()
        result = rm.evaluate(
            _decision(signal="BUY"),
            _market(gold_grams=1.0, unrealized_pnl=-150, rsi=70),
        )
        assert result["signal"] == "SELL"
        assert "SL1" in result["rationale"]