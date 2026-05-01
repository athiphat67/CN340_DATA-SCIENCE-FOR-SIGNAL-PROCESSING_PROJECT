"""
agent_core/core/risk.py  — Scalping Edition (V5 WinRate Focus)
"""

import logging
import threading
from copy import deepcopy

logger = logging.getLogger(__name__)

GRAMS_PER_BAHT_WEIGHT: float = 15.244
TRAILING_ACTIVATION_ATR_MULTIPLE: float = 1.0


class RiskManager:
    def __init__(
        self, atr_multiplier: float = 0.5, risk_reward_ratio: float = 1.0,
        min_confidence: float = 0.6, min_sell_confidence: float = 0.6,
        min_trade_thb: float = 1000.0, micro_port_threshold: float = 2000.0,
        max_daily_loss_thb: float = 500.0, max_trade_risk_pct: float = 0.20,
        session_end_force_sell_minutes: int = 30, enable_trailing_stop: bool = True,
    ):
        self.atr_multiplier = atr_multiplier
        self.rr_ratio = risk_reward_ratio
        self.min_confidence = min_confidence
        self.min_sell_confidence = min_sell_confidence
        self.min_trade_thb = min_trade_thb
        self.micro_port_threshold = micro_port_threshold
        self.max_daily_loss_thb = max_daily_loss_thb
        self.max_trade_risk_pct = max_trade_risk_pct
        self.session_end_force_sell_minutes = session_end_force_sell_minutes
        self.enable_trailing_stop = enable_trailing_stop

        self._daily_loss_accumulated: float = 0.0
        self._loss_lock = threading.Lock()
        self._daily_loss_date: str = ""

        self._active_trailing_sl: float = 0.0
        self._entry_price_thb: float = 0.0
        self._entry_atr: float = 0.0

    def record_trade_result(self, pnl_thb: float, trade_date: str) -> None:
        with self._loss_lock:
            if trade_date != self._daily_loss_date:
                self._daily_loss_accumulated = 0.0
                self._daily_loss_date = trade_date
            if pnl_thb < 0:
                self._daily_loss_accumulated += abs(pnl_thb)

    def evaluate(self, llm_decision: dict, market_state: dict) -> dict:
        signal = llm_decision.get("signal", "HOLD").upper()
        confidence = float(llm_decision.get("confidence", 0.0))
        market_context = llm_decision.get("market_context", "")

        portfolio = market_state.get("portfolio", {})
        cash_balance = float(portfolio.get("cash_balance", 0.0))
        gold_grams = float(portfolio.get("gold_grams", 0.0))
        unrealized_pnl = float(portfolio.get("unrealized_pnl", 0.0))
        trades_today = int(portfolio.get("trades_today", 0) or 0)

        summary = market_state.get("portfolio_summary", {})
        capital_mode = summary.get("mode", "normal")
        can_trade = summary.get("can_trade", True)
        holding = summary.get("holding", gold_grams > 0)
        profiting = summary.get("profit", unrealized_pnl > 0)

        # 🟢 [NEW] ดึง Flag จาก run_main_backtest.py
        is_golden_setup = market_state.get("is_golden_setup", False)

        try:
            thai_gold = market_state["market_data"]["thai_gold_thb"]
            buy_price_thb = float(thai_gold["sell_price_thb"])
            sell_price_thb = float(thai_gold["buy_price_thb"])
            atr_value = float(market_state.get("technical_indicators", {}).get("atr", {}).get("value", 0))
        except (KeyError, ValueError):
            return self._reject_signal({"rationale": market_context}, "Data Error")

        final_decision = {
            "signal": signal, "confidence": confidence,
            "entry_price": buy_price_thb if signal == "BUY" else (sell_price_thb if signal == "SELL" else None),
            "position_size_thb": 0.0, "rationale": market_context, "rejection_reason": None,
        }

        session_gate = market_state.get("session_gate", {})
        if session_gate.get("is_dead_zone") and signal == "BUY":
            return self._reject_signal(final_decision, "Dead Zone")

        if gold_grams <= 0:
            self._reset_trailing_state()
        else:
            tp_price = float(portfolio.get("take_profit_price", 0.0) or 0.0)
            base_sl = float(portfolio.get("stop_loss_price", 0.0) or 0.0)
            check_price = sell_price_thb if sell_price_thb > 0 else buy_price_thb

            if self._active_trailing_sl == 0.0:
                self._active_trailing_sl = base_sl

            if self.enable_trailing_stop and atr_value > 0 and self._entry_price_thb > 0:
                activation_price = self._entry_price_thb + (self._entry_atr * TRAILING_ACTIVATION_ATR_MULTIPLE)
                if check_price >= activation_price:
                    sl_distance = max(atr_value * self.atr_multiplier, check_price * 0.0007)
                    potential_sl = check_price - sl_distance
                    if potential_sl > self._active_trailing_sl:
                        self._active_trailing_sl = potential_sl
                        final_decision["stop_loss"] = round(self._active_trailing_sl, 2)

            override_reason = None
            if tp_price > 0 and check_price >= tp_price:
                override_reason = f"TP hit: ฿{check_price:,.0f}"
            elif self._active_trailing_sl > 0 and check_price <= self._active_trailing_sl:
                override_reason = f"Trailing SL hit: ฿{check_price:,.0f} (SL=฿{self._active_trailing_sl:,.0f})"

            if override_reason:
                final_decision["signal"] = "SELL"
                final_decision["confidence"] = 1.0
                final_decision["rationale"] = f"[SYSTEM OVERRIDE] {override_reason}"
                signal = "SELL"
                self._reset_trailing_state()

        if signal == "BUY" and final_decision["confidence"] < self.min_confidence:
            return self._reject_signal(final_decision, f"BUY confidence ({final_decision['confidence']:.2f}) < minimum {self.min_confidence}")
        if signal == "SELL" and final_decision["confidence"] < self.min_sell_confidence:
            return self._reject_signal(final_decision, f"SELL confidence ({final_decision['confidence']:.2f}) < minimum {self.min_sell_confidence}")
        
        if signal == "BUY":
            if trades_today >= 6:
                return self._reject_signal(final_decision, f"ครบโควต้าซื้อรายวันแล้ว ({trades_today}/6)")

            quota = market_state.get("execution_quota", {}) or {}
            min_entries_by_now = int(quota.get("min_entries_by_now", 0) or 0)
            required_conf_next = float(quota.get("required_confidence_for_next_buy", self.min_confidence) or self.min_confidence)

            # 🟢 [FIX] Golden Setup ข้ามเงื่อนไข Force-buy Scheduler
            if not is_golden_setup:
                if trades_today < min_entries_by_now and confidence < required_conf_next:
                    return self._reject_signal(final_decision, f"ตาม scheduler ยังไม่ทัน (done={trades_today}, expected>={min_entries_by_now}) และ confidence ({confidence:.2f}) < required {required_conf_next:.2f}")

            execution_check = llm_decision.get("execution_check", {}) or {}
            if execution_check.get("is_spread_covered") is False:
                return self._reject_signal(final_decision, "LLM execution_check ระบุว่ายังไม่ครอบคลุม spread")

            # 🟢 [FIX] Golden Setup ซื้อตอน Dip → HTF ย่อม bearish -> ข้าม
            if not is_golden_setup:
                htf = market_state.get("pre_fetched_tools", {}).get("get_htf_trend", {})
                htf_trend = str(htf.get("trend", "")).lower() if isinstance(htf, dict) else ""
                if "bear" in htf_trend and confidence < 0.75:
                    return self._reject_signal(final_decision, f"HTF trend เป็น bearish ({htf.get('trend')}) — BUY ต้อง confidence สูงกว่า 0.75")

            spread_thb = max(0.0, buy_price_thb - sell_price_thb)
            market_data = market_state.get("market_data", {})
            spread_cov = market_data.get("spread_coverage", {}) if isinstance(market_data, dict) else {}
            expected_move_thb = float(spread_cov.get("expected_move_thb", 0.0) or 0.0)
            effective_spread = float(spread_cov.get("effective_spread", spread_thb) or spread_thb)
            edge_score = float(spread_cov.get("edge_score", 0.0) or 0.0)

            if effective_spread > 0 and expected_move_thb <= 0:
                trend_pct = abs(float((market_data.get("price_trend", {}) or {}).get("change_pct", 0.0) or 0.0))
                expected_move_thb = buy_price_thb * (trend_pct / 100.0)
                edge_score = expected_move_thb / effective_spread if effective_spread > 0 else 0.0

            # 🟢 [FIX] Golden Setup ใช้ edge threshold ต่ำกว่า
            edge_threshold = 0.5 if is_golden_setup else 1.0
            if effective_spread > 0 and edge_score < edge_threshold:
                return self._reject_signal(final_decision, f"Edge ไม่พอชนะ spread (edge={edge_score:.2f}, move={expected_move_thb:.2f}, effective_spread={effective_spread:.2f})")

            if not can_trade:
                return self._reject_signal(final_decision, f"เงินคงเหลือต่ำกว่าเกณฑ์ขั้นต่ำ — ไม่ควรเปิด BUY ใหม่")

            # 🟢 [FIX] Golden Setup ลดความเข้มงวด Capital Mode ลงเล็กน้อย
            if capital_mode == "critical" and confidence < (0.72 if is_golden_setup else 0.76):
                return self._reject_signal(final_decision, f"ทุนอยู่โหมด critical ต้อง BUY confidence >= {0.72 if is_golden_setup else 0.76}")

            if capital_mode == "defensive" and confidence < (0.64 if is_golden_setup else 0.68):
                return self._reject_signal(final_decision, f"ทุนอยู่โหมด defensive ต้อง BUY confidence >= {0.64 if is_golden_setup else 0.68}")
            
            # 🟢 [FIX] Golden Setup ข้ามเงื่อนไข "ห้าม DCA ตอนมีของติดลบ"
            if not is_golden_setup:
                if holding and profiting and confidence < 0.74:
                    return self._reject_signal(final_decision, f"มี position กำไรอยู่แล้ว — BUY เพิ่มต้อง confidence >= 0.74")
                if holding and not profiting and confidence < 0.80:
                    return self._reject_signal(final_decision, f"มี position ขาดทุนอยู่แล้ว — ไม่เพิ่ม BUY หาก confidence ยังไม่สูงพอ")

        trade_date = market_state.get("date", "")
        if signal != "HOLD":
            self._reset_daily_loss_if_new_day(trade_date)
            if self._daily_loss_accumulated >= self.max_daily_loss_thb and signal == "BUY":
                return self._reject_signal(final_decision, "Loss limit")

        if signal == "BUY":
            if cash_balance < self.min_trade_thb:
                return self._reject_signal(final_decision, "Low Cash")

            near_end = session_gate.get("near_session_end", False)
            trades_done = session_gate.get("trades_this_session", 0)
            is_forced = near_end and (trades_done < 2)

            if is_forced:
                investment_thb = self.min_trade_thb
            else:
                if confidence < self.min_confidence:
                    return self._reject_signal(final_decision, f"Low Conf ({confidence})")
                investment_thb = min(cash_balance, (cash_balance * self.max_trade_risk_pct) * confidence)

            if atr_value <= 0: atr_value = buy_price_thb * 0.003

            sl_distance = max(atr_value * self.atr_multiplier, buy_price_thb * 0.0007)
            tp_distance = max(sl_distance * self.rr_ratio, buy_price_thb * 0.0007)

            final_decision["position_size_thb"] = round(investment_thb, 2)
            final_decision["stop_loss"] = round(buy_price_thb - sl_distance, 2)
            final_decision["take_profit"] = round(buy_price_thb + tp_distance, 2)

            self._active_trailing_sl = 0.0
            self._entry_price_thb = buy_price_thb
            self._entry_atr = atr_value
            return final_decision

        elif signal == "SELL":
            if gold_grams <= 1e-4:
                return self._reject_signal(final_decision, "ไม่มีทองเพียงพอสำหรับการขาย")
            
            MIN_PROFIT_FILTER = 10.0 
            is_override = any(msg in final_decision["rationale"] for msg in ["[SYSTEM OVERRIDE]", "[SESSION FORCE SELL]"])
            
            if not is_override:
                if unrealized_pnl > 0 and unrealized_pnl < MIN_PROFIT_FILTER:
                    return self._reject_signal(final_decision, f"กำไร {unrealized_pnl:.2f} THB ยังไม่ถึงเกณฑ์ขั้นต่ำ {MIN_PROFIT_FILTER} THB (ไม่คุ้ม Spread)")

            gold_value_thb = gold_grams * (sell_price_thb / GRAMS_PER_BAHT_WEIGHT)
            final_decision["entry_price"] = sell_price_thb
            final_decision["position_size_thb"] = round(gold_value_thb, 2)

            if "[SYSTEM OVERRIDE]" not in final_decision["rationale"] and "[SESSION FORCE SELL]" not in final_decision["rationale"]:
                final_decision["rationale"] = f"{final_decision['rationale']} [RiskManager: ขาย {gold_grams:.4f}g ≈ {gold_value_thb:.2f} ฿]"
            return final_decision

        return final_decision

    def _reset_trailing_state(self) -> None:
        self._active_trailing_sl = 0.0
        self._entry_price_thb = 0.0
        self._entry_atr = 0.0

    def _reset_daily_loss_if_new_day(self, trade_date: str) -> None:
        with self._loss_lock:
            if trade_date and trade_date != self._daily_loss_date:
                self._daily_loss_accumulated = 0.0
                self._daily_loss_date = trade_date

    def _reject_signal(self, decision: dict, reason: str) -> dict:
        safe = deepcopy(decision)
        safe["signal"] = "HOLD"
        safe["stop_loss"] = None
        safe["take_profit"] = None
        safe["entry_price"] = None
        safe["position_size_thb"] = 0.0
        safe["rejection_reason"] = reason
        safe["rationale"] = f"REJECTED: {reason} | เดิม: {safe.get('rationale', '')}"
        logger.info("[RiskManager] REJECTED: %s", reason)
        return safe