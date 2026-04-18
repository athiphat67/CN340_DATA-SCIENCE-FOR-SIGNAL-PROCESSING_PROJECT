"""
agent_core/core/risk.py  — Scalping Edition (V5 WinRate Focus)
Changes from V4:
  - atr_multiplier:      1.5  → 2.5   (ให้ trade หายใจได้มากขึ้น ลด SL โดนก่อน TP)
  - risk_reward_ratio:   2.0  → 1.5   (TP ใกล้ขึ้น hit ง่ายขึ้น → win rate เพิ่ม)
  - max_trade_risk_pct:  0.30 → 0.20  (ลด exposure ต่อ trade)
  - Trailing Stop:       เริ่มทันที → เริ่มหลังราคาขึ้น 1.0x ATR จาก entry
                         (ไม่ตัดกำไรก่อนที่ trade จะได้ "วิ่ง")
"""

import logging
import threading
from copy import deepcopy

logger = logging.getLogger(__name__)

GRAMS_PER_BAHT_WEIGHT: float = 15.244

# ── Trailing Stop Activation Threshold ────────────────────────────────────────
# trailing stop จะเริ่ม "ขยับ" ก็ต่อเมื่อราคาขึ้นไปแล้ว >= N * ATR จาก entry
# ถ้า = 0.0 หมายความว่าเริ่มทันที (พฤติกรรมเดิม V4)
# ถ้า = 1.0 หมายความว่ารอให้กำไรเท่า 1 ATR ก่อน ค่อยล็อก SL
TRAILING_ACTIVATION_ATR_MULTIPLE: float = 1.0


class RiskManager:
    def __init__(
        self,
        atr_multiplier: float = 2.5,            # [V5] 1.5 → 2.5
        risk_reward_ratio: float = 1.5,          # [V5] 2.0 → 1.5
        min_confidence: float = 0.75,
        min_sell_confidence: float = 0.60,
        min_trade_thb: float = 1000.0,
        micro_port_threshold: float = 2000.0,
        max_daily_loss_thb: float = 500.0,
        max_trade_risk_pct: float = 0.20,        # [V5] 0.30 → 0.20
        session_end_force_sell_minutes: int = 30,
        enable_trailing_stop: bool = True,
    ):
        self.atr_multiplier                 = atr_multiplier
        self.rr_ratio                       = risk_reward_ratio
        self.min_confidence                 = min_confidence
        self.min_sell_confidence            = min_sell_confidence
        self.min_trade_thb                  = min_trade_thb
        self.micro_port_threshold           = micro_port_threshold
        self.max_daily_loss_thb             = max_daily_loss_thb
        self.max_trade_risk_pct             = max_trade_risk_pct
        self.session_end_force_sell_minutes = session_end_force_sell_minutes
        self.enable_trailing_stop           = enable_trailing_stop

        self._daily_loss_accumulated: float = 0.0
        self._loss_lock = threading.Lock()
        self._daily_loss_date: str = ""

        # ── Trailing Stop State ───────────────────────────────────────────────
        self._active_trailing_sl: float = 0.0
        # [V5] เก็บ entry price เพื่อคำนวณว่าราคาขึ้นพอยัง ก่อนเริ่ม trailing
        self._entry_price_thb: float = 0.0
        self._entry_atr: float = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def record_trade_result(self, pnl_thb: float, trade_date: str) -> None:
        with self._loss_lock:
            if trade_date != self._daily_loss_date:
                self._daily_loss_accumulated = 0.0
                self._daily_loss_date = trade_date
            if pnl_thb < 0:
                self._daily_loss_accumulated += abs(pnl_thb)

    def evaluate(self, llm_decision: dict, market_state: dict) -> dict:
        signal         = llm_decision.get("signal", "HOLD").upper()
        confidence     = float(llm_decision.get("confidence", 0.0))
        market_context = llm_decision.get("market_context", "")

        trade_date   = market_state.get("date", "")
        portfolio    = market_state.get("portfolio", {})
        cash_balance = float(portfolio.get("cash_balance", 0.0))
        gold_grams   = float(portfolio.get("gold_grams", 0.0))

        try:
            thai_gold      = market_state["market_data"]["thai_gold_thb"]
            buy_price_thb  = float(thai_gold["sell_price_thb"])
            sell_price_thb = float(thai_gold["buy_price_thb"])
            atr_value      = float(
                market_state.get("technical_indicators", {})
                            .get("atr", {})
                            .get("value", 0)
            )
        except (KeyError, ValueError):
            return self._reject_signal({"rationale": market_context}, "Data Error")

        final_decision = {
            "signal": signal,
            "confidence": confidence,
            "entry_price": buy_price_thb if signal == "BUY" else (
                sell_price_thb if signal == "SELL" else None
            ),
            "position_size_thb": 0.0,
            "rationale": market_context,
            "rejection_reason": None,
        }

        # ================================================================
        # Gate 0a — Session Guard
        # ================================================================
        session_gate = market_state.get("session_gate", {})
        if session_gate.get("is_dead_zone") and signal == "BUY":
            return self._reject_signal(final_decision, "Dead Zone")

        # ================================================================
        # Gate 0b — Trailing Stop & TP/SL Hard Override [V5]
        # ================================================================
        if gold_grams <= 0:
            # ไม่มีทองถืออยู่ → reset สถานะ trailing ทั้งหมด
            self._reset_trailing_state()
        else:
            tp_price    = float(portfolio.get("take_profit_price", 0.0) or 0.0)
            base_sl     = float(portfolio.get("stop_loss_price",   0.0) or 0.0)
            check_price = sell_price_thb if sell_price_thb > 0 else buy_price_thb

            # ── ครั้งแรกที่เห็น position: init trailing SL จาก base_sl ──
            if self._active_trailing_sl == 0.0:
                self._active_trailing_sl = base_sl

            # ── [V5 KEY CHANGE] Trailing Stop แบบ Delayed Activation ──────
            # ขยับ SL ก็ต่อเมื่อราคาขึ้นเกิน entry + N * ATR แล้วเท่านั้น
            # ป้องกันการตัดกำไรก่อนที่ trade จะมีโอกาส "วิ่ง"
            if self.enable_trailing_stop and atr_value > 0 and self._entry_price_thb > 0:
                activation_price = (
                    self._entry_price_thb
                    + (self._entry_atr * TRAILING_ACTIVATION_ATR_MULTIPLE)
                )
                if check_price >= activation_price:
                    sl_distance  = max(
                        atr_value * self.atr_multiplier,
                        check_price * 0.0007,
                    )
                    potential_sl = check_price - sl_distance
                    if potential_sl > self._active_trailing_sl:
                        self._active_trailing_sl = potential_sl
                        final_decision["stop_loss"] = round(self._active_trailing_sl, 2)
                        logger.debug(
                            f"[TrailingSL] Activated & moved to ฿{self._active_trailing_sl:,.2f} "
                            f"(check={check_price:,.0f}, activation={activation_price:,.0f})"
                        )
                else:
                    logger.debug(
                        f"[TrailingSL] Waiting: price ฿{check_price:,.0f} "
                        f"< activation ฿{activation_price:,.0f} (entry+{TRAILING_ACTIVATION_ATR_MULTIPLE}xATR)"
                    )

            # ── TP / Trailing SL Hard Override ──────────────────────────────
            override_reason = None
            if tp_price > 0 and check_price >= tp_price:
                override_reason = f"TP hit: ฿{check_price:,.0f}"
            elif self._active_trailing_sl > 0 and check_price <= self._active_trailing_sl:
                override_reason = f"Trailing SL hit: ฿{check_price:,.0f} (SL=฿{self._active_trailing_sl:,.0f})"

            if override_reason:
                final_decision["signal"]     = "SELL"
                final_decision["confidence"] = 1.0
                final_decision["rationale"]  = f"[SYSTEM OVERRIDE] {override_reason}"
                signal = "SELL"
                self._reset_trailing_state()

        # ================================================================
        # Gate 1 — Minimum Confidence Filter (SELL Only)
        # ================================================================
        if signal == "SELL" and confidence < self.min_sell_confidence:
            return self._reject_signal(final_decision, f"Low Conf ({confidence})")

        # ================================================================
        # Gate 2 — Daily Loss Limit
        # ================================================================
        if signal != "HOLD":
            self._reset_daily_loss_if_new_day(trade_date)
            if self._daily_loss_accumulated >= self.max_daily_loss_thb and signal == "BUY":
                return self._reject_signal(final_decision, "Loss limit")

        # ================================================================
        # Gate 3 — Signal Processing & Dynamic Sizing
        # ================================================================
        if signal == "BUY":
            if cash_balance < self.min_trade_thb:
                return self._reject_signal(final_decision, "Low Cash")

            near_end    = session_gate.get("near_session_end", False)
            trades_done = session_gate.get("trades_this_session", 0)
            is_forced   = near_end and (trades_done < 2)

            if is_forced:
                # Throwaway trade — ใช้ขนาดเล็กที่สุด
                investment_thb = self.min_trade_thb
                logger.warning("Forced Trade for quota - using min size.")
            else:
                if confidence < self.min_confidence:
                    return self._reject_signal(final_decision, f"Low Conf ({confidence})")
                # [V5] max_trade_risk_pct = 0.20
                investment_thb = min(
                    cash_balance,
                    (cash_balance * self.max_trade_risk_pct) * confidence,
                )

            if atr_value <= 0:
                atr_value = buy_price_thb * 0.003

            sl_distance = max(atr_value * self.atr_multiplier, buy_price_thb * 0.0007)
            tp_distance = max(sl_distance * self.rr_ratio,      buy_price_thb * 0.0007)

            final_decision["position_size_thb"] = round(investment_thb, 2)
            final_decision["stop_loss"]          = round(buy_price_thb - sl_distance, 2)
            final_decision["take_profit"]        = round(buy_price_thb + tp_distance, 2)

            # [V5] บันทึก entry state สำหรับ trailing stop activation
            self._active_trailing_sl = 0.0
            self._entry_price_thb    = buy_price_thb
            self._entry_atr          = atr_value
            return final_decision

        elif signal == "SELL":
            if gold_grams <= 0:
                return self._reject_signal(final_decision, "No Gold")
            final_decision["position_size_thb"] = round(
                gold_grams * (sell_price_thb / GRAMS_PER_BAHT_WEIGHT), 2
            )
            return final_decision

        return final_decision

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _reset_trailing_state(self) -> None:
        self._active_trailing_sl = 0.0
        self._entry_price_thb    = 0.0
        self._entry_atr          = 0.0

    def _reset_daily_loss_if_new_day(self, trade_date: str) -> None:
        with self._loss_lock:
            if trade_date and trade_date != self._daily_loss_date:
                self._daily_loss_accumulated = 0.0
                self._daily_loss_date = trade_date

    def _reject_signal(self, d: dict, r: str) -> dict:
        s = deepcopy(d)
        s["signal"]           = "HOLD"
        s["rejection_reason"] = r
        return s