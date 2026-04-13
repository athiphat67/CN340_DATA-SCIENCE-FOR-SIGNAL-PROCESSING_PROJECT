import json   # [FIX N4] ย้าย import json ขึ้นมาบนสุดของไฟล์
import logging
import threading
from copy import deepcopy
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(
        self,
        atr_multiplier: float = 2.0,
        risk_reward_ratio: float = 1.5,
        min_confidence: float = 0.6,
        min_trade_thb: float = 1400.0,
        micro_port_threshold: float = 2000.0,
        max_daily_loss_thb: float = 500.0,
        max_trade_risk_pct: float = 0.30,
    ):
        self.atr_multiplier       = atr_multiplier
        self.rr_ratio             = risk_reward_ratio
        self.min_confidence       = min_confidence
        self.min_trade_thb        = min_trade_thb
        self.micro_port_threshold = micro_port_threshold
        self.max_daily_loss_thb   = max_daily_loss_thb
        self.max_trade_risk_pct   = max_trade_risk_pct

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
        
        # ═══════════════════════════════════════════
        # GATE-RM IN │ risk.py → ต้น evaluate()
        # ═══════════════════════════════════════════
        # import json
        # print("\n" + "="*60)
        # print("GATE-RM IN │ RISK MANAGER INPUT")
        # print(f"  llm_decision = {json.dumps(llm_decision, ensure_ascii=False, default=str)}")
        # print(f"  market_state = {json.dumps(market_state, indent=2, ensure_ascii=False, default=str)}")
        # print("="*60 + "\n") 
        
        # โครงสร้างผลลัพธ์เริ่มต้น
        final_decision = {
            "signal":            signal,
            "confidence":        confidence,
            # [FIX 2d] HOLD ให้ entry_price=None แทน 0
            "entry_price":       buy_price_thb if signal == "BUY" else (sell_price_thb if signal == "SELL" else None),
            "stop_loss":         None,   # [FIX 2d]
            "take_profit":       None,   # [FIX 2d]
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
        
        # ═══════════════════════════════════════════
        # GATE-RM G0 │ risk.py → Dead Zone check
        # ═══════════════════════════════════════════
        # print("\n" + "="*60)
        # print("GATE-RM G0 │ DEAD ZONE CHECK")
        # print(f"  current_time_str = {current_time_str!r}")
        # print(f"  current_minutes  = {current_minutes}")
        # print(f"  is_dead_zone     = {120 <= current_minutes <= 374}")
        # print("="*60 + "\n") 
        
        # เช็คช่วงเวลา Dead Zone (ห้ามเทรดเด็ดขาด ป้องกัน API Error)
        # ออม NOW ปิด 02:00–06:14 = 120–374 นาที (ตรงกับ session_manager._DEAD_END)
        if 120 <= current_minutes <= 374:
            return self._reject_signal(final_decision, f"Dead Zone ({current_time_str}) — ตลาดปิด/ห้ามเทรด")

        # ================================================================
        # Gate 0b — TP/SL Override (ถ้าถือทองอยู่)
        # ================================================================
        if gold_grams > 0:
            override_reason = None
            tp_price   = float(portfolio.get("take_profit_price", 0.0) or 0.0)
            sl_price   = float(portfolio.get("stop_loss_price",   0.0) or 0.0)
            check_price = sell_price_thb if sell_price_thb > 0 else buy_price_thb

            if tp_price > 0 and check_price >= tp_price:
                override_reason = f"TP hit: ฿{check_price:,.0f} >= TP ฿{tp_price:,.0f}"
            elif sl_price > 0 and check_price <= sl_price:
                override_reason = f"SL hit: ฿{check_price:,.0f} <= SL ฿{sl_price:,.0f}"

            if override_reason:
                logger.warning(f"🚨 HARD RULE OVERRIDE: {override_reason}")
                final_decision["signal"] = "SELL"
                final_decision["confidence"] = 1.0  # บังคับขายด้วยความมั่นใจเต็มที่
                final_decision["rationale"] = f"[SYSTEM OVERRIDE] {override_reason} (เดิม LLM สั่ง: {signal})"
                signal = "SELL" # อัปเดตตัวแปร signal เพื่อเข้า process SELL ปกติด้านล่าง
                
            # ═══════════════════════════════════════════
            # GATE-RM G0b │ risk.py → TP/SL override check (ใส่หลัง calc tp_price, sl_price)
            # ═══════════════════════════════════════════
            # print("\n" + "="*60)
            # print("GATE-RM G0b │ TP/SL OVERRIDE CHECK")
            # print(f"  gold_grams   = {gold_grams}")
            # print(f"  tp_price     = {tp_price}")
            # print(f"  sl_price     = {sl_price}")
            # print(f"  check_price  = {check_price}")
            # print(f"  override     = {override_reason!r}")
            # print("="*60 + "\n") 

        # ================================================================
        # Gate 1 — Confidence Filter
        # ================================================================
        if signal != "HOLD" and final_decision["confidence"] < self.min_confidence:
            
            # ═══════════════════════════════════════════
            # GATE-RM G1 │ risk.py → Confidence filter
            # ═══════════════════════════════════════════
            # print("\n" + "="*60)
            # print("GATE-RM G1 │ CONFIDENCE FILTER")
            # print(f"  signal      = {signal!r}")
            # print(f"  confidence  = {final_decision['confidence']}")
            # print(f"  min_conf    = {self.min_confidence}")
            # print(f"  verdict     = {'REJECT' if signal != 'HOLD' and final_decision['confidence'] < self.min_confidence else 'PASS'}")
            # print("="*60 + "\n") 
            
            return self._reject_signal(
                final_decision,
                f"Confidence ({final_decision['confidence']:.2f}) ต่ำกว่าเกณฑ์ {self.min_confidence}"
            )

        # ================================================================
        # Gate 2 — Daily Loss Limit
        # ================================================================
        if signal != "HOLD":
            
            # ═══════════════════════════════════════════
            # GATE-RM G2 │ risk.py → Daily Loss limit
            # ═══════════════════════════════════════════
            # print("\n" + "="*60)
            # print("GATE-RM G2 │ DAILY LOSS LIMIT")
            # print(f"  signal               = {signal!r}")
            # print(f"  daily_loss_accum     = {self._daily_loss_accumulated}")
            # print(f"  max_daily_loss_thb   = {self.max_daily_loss_thb}")
            # print(f"  verdict              = {'BLOCK BUY' if self._daily_loss_accumulated >= self.max_daily_loss_thb and signal == 'BUY' else 'PASS'}")
            # print("="*60 + "\n") 
            
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
            
            # ═══════════════════════════════════════════
            # GATE-RM OUT │ risk.py → ก่อน return final_decision
            # ═══════════════════════════════════════════
            # print("\n" + "="*60)
            # print("GATE-RM OUT │ FINAL DECISION")
            # print(json.dumps(final_decision, indent=2, ensure_ascii=False, default=str))
            # print("="*60 + "\n") 
            
            return final_decision

        elif signal == "SELL":
            if gold_grams <= 1e-4:
                return self._reject_signal(final_decision, "ไม่มีทองเพียงพอสำหรับการขาย")

            gold_value_thb = gold_grams * (sell_price_thb / 15.244)
            final_decision["entry_price"]       = sell_price_thb
            final_decision["position_size_thb"] = round(gold_value_thb, 2)

            if "[SYSTEM OVERRIDE]" not in final_decision["rationale"]:
                final_decision["rationale"] = f"{rationale} [RiskManager: ขาย {gold_grams:.4f}g ≈ {gold_value_thb:.2f} ฿]"

            logger.info(f"RiskManager Approved SELL: {gold_value_thb:.2f} THB")
            
            # ═══════════════════════════════════════════
            # GATE-RM OUT │ risk.py → ก่อน return final_decision
            # ═══════════════════════════════════════════
            # print("\n" + "="*60)
            # print("GATE-RM OUT │ FINAL DECISION")
            # print(json.dumps(final_decision, indent=2, ensure_ascii=False, default=str))
            # print("="*60 + "\n")
            
            return final_decision

        elif signal == "BUY":
            investment_thb = 1400.0

            if cash_balance < investment_thb:
                return self._reject_signal(final_decision, f"เงินสดไม่พอ ({cash_balance:.2f} < 1400)")

            sl_distance = atr_value * self.atr_multiplier
            tp_distance = sl_distance * self.rr_ratio

            final_decision["entry_price"]        = buy_price_thb
            final_decision["position_size_thb"]  = 1400.0
            final_decision["stop_loss"]          = round(buy_price_thb - sl_distance, 2)
            final_decision["take_profit"]        = round(buy_price_thb + tp_distance, 2)
            final_decision["rationale"] = f"{rationale} [RiskManager: อนุมัติซื้อ 1400 ฿]"
            
            # ═══════════════════════════════════════════
            # GATE-RM OUT │ risk.py → ก่อน return final_decision
            # ═══════════════════════════════════════════
            # print("\n" + "="*60)
            # print("GATE-RM OUT │ FINAL DECISION")
            # print(json.dumps(final_decision, indent=2, ensure_ascii=False, default=str))
            # print("="*60 + "\n")

            logger.info(
                "[RiskManager] → BUY entry=%.0f SL=%.0f TP=%.0f",
                buy_price_thb, final_decision["stop_loss"], final_decision["take_profit"]
            )
            return final_decision

        else:
            return self._reject_signal(final_decision, "Signal ไม่รู้จัก")

    def _reset_daily_loss_if_new_day(self, trade_date: str) -> None:
        if trade_date:
            with self._loss_lock:
                if trade_date and trade_date != self._daily_loss_date:
                    self._daily_loss_accumulated = 0.0
                    self._daily_loss_date = trade_date

    def _reject_signal(self, decision: dict, reason: str) -> dict:
        safe = deepcopy(decision)
        safe["signal"]            = "HOLD"
        safe["stop_loss"]         = None   # [FIX 2d]
        safe["take_profit"]       = None   # [FIX 2d]
        safe["entry_price"]       = None   # [FIX 2d]
        safe["position_size_thb"] = 0.0
        safe["rejection_reason"]  = reason
        safe["rationale"]         = f"REJECTED: {reason} | เดิม: {safe.get('rationale', '')}"
        logger.info("[RiskManager] REJECTED: %s", reason)
        return safe