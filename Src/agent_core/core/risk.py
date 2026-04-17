"""
agent_core/core/risk.py  — Scalping Edition
══════════════════════════════════════════════════════════════════════
[PATCH v4.1 — Database Integration for State Loss Fix]
  - เพิ่ม db_service เข้ามาใน __init__
  - Gate 2 จะอ่าน PnL ของวันนี้จากตาราง trade_log แทนการจำในตัวแปร
    ช่วยแก้ปัญหา RiskManager ถูกเคลียร์ค่าทุกๆ 15 นาที
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
        db_service = None,                  # [NEW] รับ Database เข้ามาเพื่อแก้ปัญหา State Loss
        atr_multiplier: float = 0.7,        
        risk_reward_ratio: float = 1.5,     
        min_confidence: float = 0.57,       # BUY minimum
        min_sell_confidence: float = 0.55,  # SELL minimum — sync กับ roles.json
        min_trade_thb: float = 1250.0,
        micro_port_threshold: float = 2000.0,
        max_daily_loss_thb: float = 500.0,
        max_trade_risk_pct: float = 0.30,
        session_end_force_sell_minutes: int = 30,  
    ):
        self.db_service                     = db_service # [NEW] 
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
                logger.info(f"Daily loss accumulated (Memory fallback): {self._daily_loss_accumulated:.2f} THB")

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

        summary = market_state.get("portfolio_summary", {})

        capital_mode = summary.get("mode", "normal")
        can_trade = summary.get("can_trade", True)
        holding = summary.get("holding", gold_grams > 0)
        profiting = summary.get("profit", unrealized_pnl > 0)

        try:
            thai_gold      = market_state["market_data"]["thai_gold_thb"]
            buy_price_thb  = float(thai_gold["sell_price_thb"])   
            sell_price_thb = float(thai_gold["buy_price_thb"])     

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
        if 120 <= current_minutes <= 374:
            return self._reject_signal(final_decision, f"Dead Zone ({current_time_str}) — ตลาดปิด/ห้ามเทรด")

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
        # Gate 0c — Session End Force Sell [NEW — Scalping]
        # ================================================================
        # ถ้าถือทองและเหลือเวลาใน session น้อย → บังคับขาย
        # ป้องกัน position ค้างข้าม session และทำให้โควตาไม่ครบ
        if gold_grams > 0 and signal != "SELL":
            session_gate = market_state.get("session_gate", {})
            mins_left    = session_gate.get("minutes_to_session_end")

            # [FIX] อ่านค่าตรงๆ แทนการตรวจผ่าน str() ซึ่ง match ผิดพลาดได้
            directive    = market_state.get("backtest_directive", "")
            quota_urgent = session_gate.get("quota_urgent", False) or "QUOTA URGENT" in directive

            force_sell_reason = None

            if mins_left is not None and 0 < mins_left <= self.session_end_force_sell_minutes:
                force_sell_reason = (
                    f"Session ending in {mins_left} min — scalping force SELL "
                    f"(threshold={self.session_end_force_sell_minutes} min)"
                )
            elif quota_urgent:
                force_sell_reason = "Quota urgent — force SELL to free capital for next trade"

            if force_sell_reason:
                logger.warning(f"⏰ SESSION FORCE SELL: {force_sell_reason}")
                final_decision["signal"]     = "SELL"
                final_decision["confidence"] = 0.85
                final_decision["rationale"]  = f"[SESSION FORCE SELL] {force_sell_reason}"
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
        
        # Gate 1.5 — Portfolio Capital Protection
        # ================================================================
        if signal == "BUY":
            if not can_trade:
                return self._reject_signal(
                    final_decision,
                    f"Remaining capital is below the minimum threshold — Should not open a new BUY"
                )

            if capital_mode == "critical" and confidence < 0.70:
                return self._reject_signal(
                    final_decision,
                    f"Capital is in critical mode, BUY confidence must be >= 0.70"
                )

            if capital_mode == "defensive" and confidence < 0.64:
                return self._reject_signal(
                    final_decision,
                    f"Capital is in defensive mode, BUY confidence must be >= 0.64"
                )
            
            if holding and profiting and confidence < 0.68:
                return self._reject_signal(
                    final_decision,
                    f"Already holding a profitable position — Adding BUY requires confidence >= 0.68"
                )

            if holding and not profiting and confidence < 0.74:
                return self._reject_signal(
                    final_decision,
                    f"Already holding a losing position — Do not add BUY if confidence is not high enough"
                )

        # ================================================================
        # Gate 2 — Daily Loss Limit [FIXED: State Loss via Database]
        # ================================================================
        if signal != "HOLD":
            current_loss = 0.0

            if self.db_service is not None:
                try:
                    # ดึง PnL แบบ Real-time จาก DB ของวันนี้
                    today_pnl = self.db_service.get_today_realized_pnl()
                    if today_pnl < 0:
                        current_loss = abs(today_pnl)
                except Exception as e:
                    logger.error(f"[RiskManager] DB fetch error, falling back to memory: {e}")
                    self._reset_daily_loss_if_new_day(trade_date)
                    with self._loss_lock:
                        current_loss = self._daily_loss_accumulated
            else:
                # Fallback: ถ้ายังไม่ได้ต่อ DB ให้ใช้ระบบเดิมไปก่อน
                self._reset_daily_loss_if_new_day(trade_date)
                with self._loss_lock:
                    current_loss = self._daily_loss_accumulated

            logger.debug("[RiskManager] daily_loss=%.2f max=%.2f signal=%s", current_loss, self.max_daily_loss_thb, signal)
            
            if current_loss >= self.max_daily_loss_thb and signal == "BUY":
                return self._reject_signal(
                    final_decision,
                    f"Daily loss limit ถึงเกณฑ์แล้ว (ขาดทุนวันนี้ {current_loss:.2f} บาท) — ระงับการเปิด BUY ใหม่"
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
            llm_suggested_size = float(llm_decision.get("position_size_thb") or 0.0)
            investment_thb = llm_suggested_size if llm_suggested_size > 0 else self.min_trade_thb

            if investment_thb < self.min_trade_thb:
                return self._reject_signal(
                    final_decision,
                    f"Position size ตาม confidence ต่ำเกินไป ({investment_thb:.2f} THB < min {self.min_trade_thb:.0f} THB)"
                )

            if cash_balance < investment_thb:
                return self._reject_signal(final_decision, f"เงินสดไม่พอ ({cash_balance:.2f} < {investment_thb:.2f})")

            _usd_thb = float(market_state.get("market_data", {}).get("forex", {}).get("usd_thb", 34.0))
            if atr_value <= 0:
                atr_value = buy_price_thb * 0.003
                logger.warning(f"[RiskManager] ATR=0 → fallback atr={atr_value:.0f} (0.3% of price)")

            sl_distance = atr_value * self.atr_multiplier   
            tp_distance = sl_distance * self.rr_ratio        

            min_move = buy_price_thb * 0.0007   
            sl_distance = max(sl_distance, min_move)
            tp_distance = max(tp_distance, sl_distance * self.rr_ratio) 

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

    def _reset_daily_loss_if_new_day(self, trade_date: str) -> None:
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