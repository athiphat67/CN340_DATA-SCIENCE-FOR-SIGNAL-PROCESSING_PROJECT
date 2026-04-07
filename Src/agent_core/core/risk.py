import logging
from copy import deepcopy
from datetime import datetime

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(
        self,
        atr_multiplier: float = 2.0,
        risk_reward_ratio: float = 1.5,
        min_confidence: float = 0.6,
        min_trade_thb: float = 1000.0,
        micro_port_threshold: float = 2000.0,
        max_daily_loss_thb: float = 500.0,
        max_trade_risk_pct: float = 0.30,
    ):
        self.atr_multiplier = atr_multiplier
        self.rr_ratio = risk_reward_ratio
        self.min_confidence = min_confidence
        self.min_trade_thb = min_trade_thb
        self.micro_port_threshold = micro_port_threshold
        self.max_daily_loss_thb = max_daily_loss_thb
        self.max_trade_risk_pct = max_trade_risk_pct

        self._daily_loss_accumulated: float = 0.0
        self._daily_loss_date: str = ""

    def record_trade_result(self, pnl_thb: float, trade_date: str) -> None:
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
        
        # สมมติว่ามี timestamp ส่งมาใน format "HH:MM" หรือมี datetime object
        current_time_str = market_state.get("time", "12:00") 
        trade_date = market_state.get("date", "")

        portfolio     = market_state.get("portfolio", {})
        cash_balance  = float(portfolio.get("cash_balance", 0.0))
        gold_grams    = float(portfolio.get("gold_grams", 0.0))
        
        # ดึงค่า Unrealized PnL (ถ้าไม่ได้ส่งมา ต้องคำนวณจาก avg_cost vs current_price)
        unrealized_pnl = float(portfolio.get("unrealized_pnl", 0.0))

        try:
            thai_gold = market_state["market_data"]["thai_gold_thb"]
            buy_price_thb = float(thai_gold.get("sell_price_thb") or thai_gold.get("spot_price_thb") or 0)
            sell_price_thb = float(thai_gold.get("buy_price_thb") or thai_gold.get("spot_price_thb") or 0)

            if buy_price_thb <= 0 or sell_price_thb <= 0:
                raise ValueError("ราคาทองเป็น 0 หรือติดลบ")
            
            # ดึงค่า Indicator สำหรับเงื่อนไขออก
            tech_inds = market_state.get("technical_indicators", {})
            rsi_value = float(tech_inds.get("rsi", {}).get("value", 50.0))
            macd_hist = float(tech_inds.get("macd", {}).get("histogram", 0.0))
            
            atr_raw   = tech_inds.get("atr", {})
            atr_value = float(atr_raw.get("value", 0))

        except (KeyError, ValueError) as e:
            logger.error(f"Market state error: {e}")
            return self._reject_signal({"rationale": rationale}, f"ข้อมูลตลาดไม่ครบถ้วน: {e}")

        # โครงสร้างผลลัพธ์เริ่มต้น
        final_decision = {
            "signal":            signal,
            "confidence":        confidence,
            "entry_price":       buy_price_thb if signal == "BUY" else sell_price_thb,
            "stop_loss":         0.0,
            "take_profit":       0.0,
            "position_size_thb": 0.0,
            "rationale":         rationale,
            "rejection_reason":  None,
        }

        # ================================================================
        # ด่านที่ 0 — HARD RULES ENFORCEMENT (ไม้เรียวคุมวินัย)
        # ================================================================
        
        # 1. เช็คช่วงเวลา Dead Zone (ห้ามเทรดเด็ดขาด)
        if "02:00" <= current_time_str <= "06:14":
            return self._reject_signal(final_decision, f"Dead Zone ({current_time_str}) — ตลาดปิด/ห้ามเทรด")

        # 2. เช็คเงื่อนไข TP / SL / Danger Zone ถือของอยู่ต้องโดนบังคับขาย
        if gold_grams > 0:
            override_reason = None
            
            # Time Rule
            if "01:30" <= current_time_str <= "01:59":
                override_reason = f"SL3: Danger Zone ({current_time_str}) บังคับเคลียร์พอร์ตกดขายก่อนตลาดปิด"
            
            # Stop Loss Rules
            elif unrealized_pnl <= -150:
                override_reason = f"SL1: ขาดทุนถึงขีดจำกัด ({unrealized_pnl:.2f} THB) ตัดขาดทุนทันที"
            elif unrealized_pnl <= -80 and rsi_value < 35:
                override_reason = f"SL2: ขาดทุน ({unrealized_pnl:.2f} THB) + RSI Breakdown ({rsi_value:.1f})"
                
            # Take Profit Rules
            elif unrealized_pnl >= 300:
                override_reason = f"TP1: กำไรถึงเป้าหมายสูงสุด (+{unrealized_pnl:.2f} THB)"
            elif unrealized_pnl >= 150 and rsi_value > 65:
                override_reason = f"TP2: กำไร (+{unrealized_pnl:.2f} THB) + Overbought RSI ({rsi_value:.1f})"
            elif unrealized_pnl >= 100 and macd_hist < 0:
                override_reason = f"TP3: กำไร (+{unrealized_pnl:.2f} THB) + MACD หมดรอบเทรนด์"

            # ถ้าโดน Override ให้ยึดอำนาจ LLM ทันที
            if override_reason:
                logger.warning(f"🚨 HARD RULE OVERRIDE: {override_reason}")
                final_decision["signal"] = "SELL"
                final_decision["confidence"] = 1.0  # บังคับขายด้วยความมั่นใจเต็มที่
                final_decision["rationale"] = f"[SYSTEM OVERRIDE] {override_reason} (เดิม LLM สั่ง: {signal})"
                signal = "SELL" # อัปเดตตัวแปร signal เพื่อเข้า process SELL ปกติด้านล่าง

        # ================================================================
        # ด่านที่ 1 — Confidence Filter
        # ================================================================
        # ถ้าเป็น Hard Rule บังคับขาย (confidence = 1.0) จะผ่านด่านนี้ไปได้สบายๆ
        if signal != "HOLD" and final_decision["confidence"] < self.min_confidence:
            return self._reject_signal(
                final_decision,
                f"Confidence ({final_decision['confidence']:.2f}) ต่ำกว่าเกณฑ์ขั้นต่ำ {self.min_confidence}"
            )

        # ================================================================
        # ด่านที่ 2 — Daily Loss Limit 
        # ================================================================
        if signal != "HOLD":
            self._reset_daily_loss_if_new_day(trade_date)
            if self._daily_loss_accumulated >= self.max_daily_loss_thb and signal == "BUY":
                # บังคับหยุดเทรดเฉพาะฝั่ง BUY ปล่อยให้ฝั่ง SELL ทำงานได้ถ้าต้องการหนีตาย
                return self._reject_signal(
                    final_decision,
                    f"Daily loss limit ถึงเกณฑ์แล้ว ({self._daily_loss_accumulated:.2f}) — หยุดซื้อวันนี้"
                )

        # ================================================================
        # ด่านที่ 3 — จัดการแยกตาม Signal
        # ================================================================
        if signal == "HOLD":
            return final_decision

        elif signal == "SELL":
            if gold_grams <= 1e-4:
                return self._reject_signal(final_decision, "ไม่มีทองเพียงพอสำหรับการขาย")

            gold_value_thb = gold_grams * (sell_price_thb / 15.244)
            final_decision["entry_price"] = sell_price_thb
            final_decision["position_size_thb"] = round(gold_value_thb, 2)
            
            # ถ้าเป็น LLM สั่งเอง ให้ต่อท้าย rationale เดิม
            if "[SYSTEM OVERRIDE]" not in final_decision["rationale"]:
                final_decision["rationale"] = f"{rationale} [RiskManager: ขาย {gold_grams:.4f}g ≈ {gold_value_thb:.2f} ฿]"

            logger.info(f"RiskManager Approved SELL: {gold_value_thb:.2f} THB")
            return final_decision

        elif signal == "BUY":
            # (ตรรกะ BUY / Position Sizing / ATR SL TP เดิมของคุณคงไว้ตามปกติ)
            investment_thb = 1000.0 # Fix ตามเป้าหมาย Aom NOW
            
            if cash_balance < investment_thb:
                 return self._reject_signal(final_decision, f"เงินสดไม่พอ ({cash_balance:.2f} < 1000)")

            sl_distance = atr_value * self.atr_multiplier
            tp_distance = sl_distance * self.rr_ratio

            final_decision["entry_price"]        = buy_price_thb
            final_decision["position_size_thb"]  = 1000.0
            final_decision["stop_loss"]          = round(buy_price_thb - sl_distance, 2)
            final_decision["take_profit"]        = round(buy_price_thb + tp_distance, 2)
            final_decision["rationale"] = f"{rationale} [RiskManager: อนุมัติซื้อ 1000 ฿]"

            return final_decision

        else:
            return self._reject_signal(final_decision, "Signal ไม่รู้จัก")

    def _reset_daily_loss_if_new_day(self, trade_date: str) -> None:
        if trade_date and trade_date != self._daily_loss_date:
            self._daily_loss_accumulated = 0.0
            self._daily_loss_date = trade_date

    def _reject_signal(self, decision: dict, reason: str) -> dict:
        safe = deepcopy(decision)
        safe["signal"]            = "HOLD"
        safe["position_size_thb"] = 0.0
        safe["rejection_reason"]  = reason
        safe["rationale"]         = f"REJECTED: {reason} | Rationale เดิม: {safe.get('rationale', '')}"
        return safe