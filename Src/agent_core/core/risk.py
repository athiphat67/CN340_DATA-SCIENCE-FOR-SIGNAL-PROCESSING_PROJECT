"""
agent_core/core/risk.py  — Scalping Edition
══════════════════════════════════════════════════════════════════════
[PATCH v4.1 — Profit Filter & Scope Fix]
  - ย้ายตัวแปร Profit Filter เข้ามาอยู่ใน block SELL ให้ถูกต้อง
  - ใช้ unrealized_pnl ที่ประกาศไว้ที่หัวฟังก์ชัน ไม่ต้องดึงซ้ำ
  - ปรับปรุง Logic Override ไม่ให้ข้ามการขายเมื่อชน SL/TP
══════════════════════════════════════════════════════════════════════
"""

import json
import logging
import threading
from copy import deepcopy
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(
        self,
        atr_multiplier: float = 0.5,        
        risk_reward_ratio: float = 1.0,     
        min_confidence: float = 0.6,       # BUY minimum
        min_sell_confidence: float = 0.6,  # SELL minimum — sync กับ roles.json
        min_trade_thb: float = 1000.0,
        micro_port_threshold: float = 2000.0,
        max_daily_loss_thb: float = 500.0,
        max_trade_risk_pct: float = 0.30,
        session_end_force_sell_minutes: int = 30,  # [NEW] บังคับขายก่อนปิด session
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

        self._daily_loss_accumulated: float = 0.0
        self._loss_lock   = threading.Lock()
        self._daily_loss_date: str = ""

    def record_trade_result(self, pnl_thb: float, trade_date: str) -> None:
        with self._loss_lock:
            if trade_date != self._daily_loss_date:
                self._daily_loss_accumulated = 0.0
                self._daily_loss_date = trade_date
            if pnl_thb < 0:
                self._daily_loss_accumulated += abs(pnl_thb)
                logger.info(f"Daily loss accumulated: {self._daily_loss_accumulated:.2f} THB")

    def evaluate(self, llm_decision: dict, market_state: dict) -> dict:
        signal     = llm_decision.get("signal", "HOLD").upper()
        confidence = float(llm_decision.get("confidence", 0.0))
        rationale  = llm_decision.get("rationale", "")

        current_time_str = market_state.get("time", "12:00")
        trade_date       = market_state.get("date", "")

        portfolio      = market_state.get("portfolio", {})
        cash_balance   = float(portfolio.get("cash_balance", 0.0))
        gold_grams     = float(portfolio.get("gold_grams", 0.0))
        unrealized_pnl = float(portfolio.get("unrealized_pnl", 0.0))
        trades_today   = int(portfolio.get("trades_today", 0) or 0)

        summary = market_state.get("portfolio_summary", {})

        capital_mode = summary.get("mode", "normal")
        can_trade = summary.get("can_trade", True)
        holding = summary.get("holding", gold_grams > 0)
        profiting = summary.get("profit", unrealized_pnl > 0)

        try:
            thai_gold      = market_state["market_data"]["thai_gold_thb"]
            buy_price_thb  = float(thai_gold["sell_price_thb"])   # เราซื้อในราคา sell ของร้าน
            sell_price_thb = float(thai_gold["buy_price_thb"])     # เราขายในราคา buy ของร้าน

            if buy_price_thb <= 0 or sell_price_thb <= 0:
                raise ValueError("ราคาทองเป็น 0 หรือติดลบ")

            tech_inds  = market_state.get("technical_indicators", {})
            rsi_value  = float(tech_inds.get("rsi",  {}).get("value", 50.0))
            macd_hist  = float(tech_inds.get("macd", {}).get("histogram", 0.0))
            atr_raw    = tech_inds.get("atr", {})
            atr_value  = float(atr_raw.get("value", 0))

        except (KeyError, ValueError) as e:
            logger.error(f"Market state error: {e}")
            return self._reject_signal({"rationale": rationale}, f"ข้อมูลตลาดไม่ครบถ้วน: {e}")

        # โครงสร้างผลลัพธ์เริ่มต้น
        final_decision = {
            "signal":            signal,
            "confidence":        confidence,
            "entry_price":       buy_price_thb if signal == "BUY" else (sell_price_thb if signal == "SELL" else None),
            "stop_loss":         None,
            "take_profit":       None,
            "position_size_thb": 0.0,
            "rationale":         rationale,
            "rejection_reason":  None,
        }

        # ── แปลงเวลา ──────────────────────────────────────────────────────────
        current_minutes = 0
        try:
            h, m = map(int, current_time_str.split(":"))
            current_minutes = h * 60 + m
        except (ValueError, AttributeError):
            logger.error(f"Time format error: {current_time_str}")
            return self._reject_signal(final_decision, f"ระบบขัดข้อง: อ่านเวลาไม่ได้ ({current_time_str})")

        # ================================================================
        # Gate 0 — Dead Zone (02:00–06:14 BKK)
        # ================================================================
        # if 120 <= current_minutes <= 374:
        #     return self._reject_signal(final_decision, f"Dead Zone ({current_time_str}) — ตลาดปิด/ห้ามเทรด")

        # ================================================================
        # Gate 0b — TP/SL Hard Override (ถ้าถือทองอยู่)
        # ================================================================
        if gold_grams > 0:
            override_reason = None
            tp_price    = float(portfolio.get("take_profit_price", 0.0) or 0.0)
            sl_price    = float(portfolio.get("stop_loss_price",   0.0) or 0.0)
            check_price = sell_price_thb if sell_price_thb > 0 else buy_price_thb

            if tp_price > 0 and check_price >= tp_price:
                override_reason = f"TP hit: ฿{check_price:,.0f} >= TP ฿{tp_price:,.0f}"
            elif sl_price > 0 and check_price <= sl_price:
                override_reason = f"SL hit: ฿{check_price:,.0f} <= SL ฿{sl_price:,.0f}"

            if override_reason:
                logger.warning(f"🚨 HARD RULE OVERRIDE: {override_reason}")
                final_decision["signal"]     = "SELL"
                final_decision["confidence"] = 1.0
                final_decision["rationale"]  = f"[SYSTEM OVERRIDE] {override_reason} (เดิม LLM สั่ง: {signal})"
                signal = "SELL"

        # ================================================================
        # Gate 1 — Confidence Filter
        # ================================================================
        if signal == "BUY" and final_decision["confidence"] < self.min_confidence:
            return self._reject_signal(
                final_decision,
                f"BUY confidence ({final_decision['confidence']:.2f}) < minimum {self.min_confidence}"
            )
        if signal == "SELL" and final_decision["confidence"] < self.min_sell_confidence:
            return self._reject_signal(
                final_decision,
                f"SELL confidence ({final_decision['confidence']:.2f}) < minimum {self.min_sell_confidence}"
            )
        
        # ================================================================
        # Gate 1.5 — Portfolio Capital Protection
        # ================================================================
        if signal == "BUY":
            # Daily quota guard: ครบ 6 entries แล้วหยุดเปิด BUY เพิ่ม
            if trades_today >= 6:
                return self._reject_signal(
                    final_decision,
                    f"ครบโควต้าซื้อรายวันแล้ว ({trades_today}/6)"
                )

            quota = market_state.get("execution_quota", {}) or {}
            min_entries_by_now = int(quota.get("min_entries_by_now", 0) or 0)
            required_conf_next = float(quota.get("required_confidence_for_next_buy", self.min_confidence) or self.min_confidence)
            recommended_size = float(quota.get("recommended_next_position_thb", self.min_trade_thb) or self.min_trade_thb)

            # ถ้ายังตามโควต้าไม่ทัน ให้เข้มเรื่อง edge แต่ยืดหยุ่น confidence ตาม scheduler
            if trades_today < min_entries_by_now and confidence < required_conf_next:
                return self._reject_signal(
                    final_decision,
                    f"ตาม scheduler ยังไม่ทัน (done={trades_today}, expected>={min_entries_by_now}) และ confidence ({confidence:.2f}) < required {required_conf_next:.2f}"
                )

            execution_check = llm_decision.get("execution_check", {}) or {}
            if execution_check.get("is_spread_covered") is False:
                return self._reject_signal(
                    final_decision,
                    "LLM execution_check ระบุว่ายังไม่ครอบคลุม spread"
                )

            # HTF precedence: ถ้า 1h/4h เป็น bearish ให้หลีกเลี่ยง BUY
            htf = market_state.get("pre_fetched_tools", {}).get("get_htf_trend", {})
            htf_trend = str(htf.get("trend", "")).lower() if isinstance(htf, dict) else ""
            if "bear" in htf_trend and confidence < 0.75:
                return self._reject_signal(
                    final_decision,
                    f"HTF trend เป็น bearish ({htf.get('trend')}) — BUY ต้อง confidence สูงกว่า 0.75"
                )

            # ต้องมี edge มากพอชนะ spread ก่อนเปิด BUY
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

            if effective_spread > 0 and edge_score < 1.0:
                return self._reject_signal(
                    final_decision,
                    f"Edge ไม่พอชนะ spread (edge={edge_score:.2f}, move={expected_move_thb:.2f}, effective_spread={effective_spread:.2f})"
                )

            # เงินต่ำกว่า threshold = ห้ามซื้อ
            if not can_trade:
                return self._reject_signal(
                    final_decision,
                    f"เงินคงเหลือต่ำกว่าเกณฑ์ขั้นต่ำ — ไม่ควรเปิด BUY ใหม่"
                )

            # เงินใกล้หมด ต้องการความมั่นใจสูงขึ้น
            if capital_mode == "critical" and confidence < 0.76:
                return self._reject_signal(
                    final_decision,
                    f"ทุนอยู่โหมด critical ต้อง BUY confidence >= 0.76"
                )

            if capital_mode == "defensive" and confidence < 0.68:
                return self._reject_signal(
                    final_decision,
                    f"ทุนอยู่โหมด defensive ต้อง BUY confidence >= 0.68"
                )
            
            # มีกำไรอยู่แล้ว จะ BUY เพิ่ม ต้องเป็น setup แข็งจริง
            if holding and profiting and confidence < 0.74:
                return self._reject_signal(
                    final_decision,
                    f"มี position กำไรอยู่แล้ว — BUY เพิ่มต้อง confidence >= 0.74"
                )

            # มีของติดลบอยู่แล้ว ห้ามถัวเฉลี่ยมั่ว
            if holding and not profiting and confidence < 0.80:
                return self._reject_signal(
                    final_decision,
                    f"มี position ขาดทุนอยู่แล้ว — ไม่เพิ่ม BUY หาก confidence ยังไม่สูงพอ"
                )

        # ================================================================
        # Gate 2 — Daily Loss Limit
        # ================================================================
        if signal != "HOLD":
            self._reset_daily_loss_if_new_day(trade_date)
            with self._loss_lock:
                current_loss = self._daily_loss_accumulated
            logger.debug("[RiskManager] daily_loss=%.2f max=%.2f signal=%s", current_loss, self.max_daily_loss_thb, signal)
            if current_loss >= self.max_daily_loss_thb and signal == "BUY":
                return self._reject_signal(
                    final_decision,
                    f"Daily loss limit ถึงเกณฑ์แล้ว ({current_loss:.2f}) — หยุดซื้อวันนี้"
                )

        # ================================================================
        # Gate 3 — Signal Processing
        # ================================================================
        if signal == "HOLD":
            return final_decision

        elif signal == "SELL":
            if holding and profiting:
                logger.info("[RiskManager] SELL while profitable position → prioritize profit protection")

            if gold_grams <= 1e-4:
                return self._reject_signal(final_decision, "ไม่มีทองเพียงพอสำหรับการขาย")
            
            # --- [NEW] ฟิลเตอร์กำไรขั้นต่ำ (Profit Filter) ---
            MIN_PROFIT_FILTER = 10.0 
            
            # เช็คว่าเป็นกรณีบังคับขายหรือไม่ (TP/SL/Session End)
            is_override = any(msg in rationale for msg in ["[SYSTEM OVERRIDE]", "[SESSION FORCE SELL]"])
            
            # ถ้าเป็นกำไร แต่กำไรน้อยกว่าเกณฑ์ ให้ HOLD (ไม่ใช้กับกรณี Override)
            if not is_override:
                if unrealized_pnl > 0 and unrealized_pnl < MIN_PROFIT_FILTER:
                    return self._reject_signal(
                        final_decision, 
                        f"กำไร {unrealized_pnl:.2f} THB ยังไม่ถึงเกณฑ์ขั้นต่ำ {MIN_PROFIT_FILTER} THB (ไม่คุ้ม Spread)"
                    )
            # ------------------------------------------------

            gold_value_thb = gold_grams * (sell_price_thb / 15.244)
            
            final_decision["entry_price"]       = sell_price_thb
            final_decision["position_size_thb"] = round(gold_value_thb, 2)

            if "[SYSTEM OVERRIDE]" not in final_decision["rationale"] and \
               "[SESSION FORCE SELL]" not in final_decision["rationale"]:
                final_decision["rationale"] = (
                    f"{rationale} [RiskManager: ขาย {gold_grams:.4f}g ≈ {gold_value_thb:.2f} ฿]"
                )

            logger.info(f"RiskManager Approved SELL: {gold_value_thb:.2f} THB")
            return final_decision

        elif signal == "BUY":
            # [FIX] เปลี่ยนจากการคำนวณ % พอร์ต เป็นการดึงค่าจาก LLM โดยตรง
            llm_suggested_size = float(llm_decision.get("position_size_thb") or 0.0)
            quota = market_state.get("execution_quota", {}) or {}
            recommended_size = float(quota.get("recommended_next_position_thb", self.min_trade_thb) or self.min_trade_thb)
            
            # ถ้า LLM ไม่ส่งขนาดมาให้ใช้ scheduler size เป็นค่าเริ่มต้น
            investment_thb = llm_suggested_size if llm_suggested_size > 0 else recommended_size

            if investment_thb < self.min_trade_thb:
                return self._reject_signal(
                    final_decision,
                    f"Position size ตาม confidence ต่ำเกินไป ({investment_thb:.2f} THB < min {self.min_trade_thb:.0f} THB)"
                )

            if cash_balance < investment_thb:
                return self._reject_signal(final_decision, f"เงินสดไม่พอ ({cash_balance:.2f} < {investment_thb:.2f})")

            # [PATCH v3.0] Scalping TP/SL — แคบลงเพื่อออก position เร็ว
            # ATR fallback: ถ้า atr=0 ใช้ 0.3% ของราคาแทน (กัน division by zero)
            _usd_thb = float(market_state.get("market_data", {}).get("forex", {}).get("usd_thb", 34.0))
            if atr_value <= 0:
                atr_value = buy_price_thb * 0.003
                logger.warning(f"[RiskManager] ATR=0 → fallback atr={atr_value:.0f} (0.3% of price)")

            sl_distance = atr_value * self.atr_multiplier   # 1.2× ATR
            tp_distance = sl_distance * self.rr_ratio        # 2.0× SL

            # ป้องกัน TP/SL น้อยเกินไป (minimum 50 THB/บาทน้ำหนัก)
            min_move = buy_price_thb * 0.0007   # ~0.07% ≈ 50 THB ที่ราคา 71,000
            sl_distance = max(sl_distance, min_move)
            tp_distance = max(tp_distance, sl_distance * self.rr_ratio)  # [FIX] ใช้ rr_ratio แทน hardcode 1.2

            final_decision["entry_price"]        = buy_price_thb
            final_decision["position_size_thb"]  = investment_thb
            final_decision["stop_loss"]          = round(buy_price_thb - sl_distance, 2)
            final_decision["take_profit"]        = round(buy_price_thb + tp_distance, 2)
            final_decision["rationale"]          = (
                f"{rationale} [RiskManager: ซื้อ {investment_thb:.0f}฿ "
                f"SL={final_decision['stop_loss']:,.0f} TP={final_decision['take_profit']:,.0f}]"
            )

            logger.info(
                "[RiskManager] → BUY entry=%.0f SL=%.0f TP=%.0f (ATR×%.1f / RR×%.1f)",
                buy_price_thb, final_decision["stop_loss"], final_decision["take_profit"],
                self.atr_multiplier, self.rr_ratio,
            )
            return final_decision

        else:
            return self._reject_signal(final_decision, "Signal ไม่รู้จัก")

    # ── Helpers ─────────────────────────────────────────────────────────

    def _reset_daily_loss_if_new_day(self, trade_date: str) -> None:
        # [FIX] ตรวจ trade_date ครั้งเดียว ภายใต้ lock
        with self._loss_lock:
            if trade_date and trade_date != self._daily_loss_date:
                self._daily_loss_accumulated = 0.0
                self._daily_loss_date = trade_date

    def _reject_signal(self, decision: dict, reason: str) -> dict:
        safe = deepcopy(decision)
        safe["signal"]            = "HOLD"
        safe["stop_loss"]         = None
        safe["take_profit"]       = None
        safe["entry_price"]       = None
        safe["position_size_thb"] = 0.0
        safe["rejection_reason"]  = reason
        safe["rationale"]         = f"REJECTED: {reason} | เดิม: {safe.get('rationale', '')}"
        logger.info("[RiskManager] REJECTED: %s", reason)
        return safe
