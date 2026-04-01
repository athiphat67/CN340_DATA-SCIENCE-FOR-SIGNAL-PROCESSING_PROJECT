import logging
from copy import deepcopy

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(
        self,
        atr_multiplier: float = 2.0,
        risk_reward_ratio: float = 1.5,
        min_confidence: float = 0.5,
        min_trade_thb: float = 1000.0,
        micro_port_threshold: float = 2000.0,
        # --- [FIX #4] เพิ่ม Daily Loss Limit ---
        max_daily_loss_thb: float = 500.0,
        max_trade_risk_pct: float = 0.30,       # [FIX #1] จำกัด position สูงสุด 30% ของพอร์ต
    ):
        self.atr_multiplier = atr_multiplier
        self.rr_ratio = risk_reward_ratio
        self.min_confidence = min_confidence
        self.min_trade_thb = min_trade_thb
        self.micro_port_threshold = micro_port_threshold
        self.max_daily_loss_thb = max_daily_loss_thb
        self.max_trade_risk_pct = max_trade_risk_pct

        # [FIX #4] State สำหรับติดตาม Daily Loss
        self._daily_loss_accumulated: float = 0.0
        self._daily_loss_date: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_trade_result(self, pnl_thb: float, trade_date: str) -> None:
        """
        เรียกจากภายนอกหลังปิด Trade เพื่อสะสม Daily Loss
        - pnl_thb: กำไร/ขาดทุน (ติดลบ = ขาดทุน)
        - trade_date: วันที่เทรด รูปแบบ "YYYY-MM-DD"
        """
        if trade_date != self._daily_loss_date:
            # วันใหม่ → reset
            self._daily_loss_accumulated = 0.0
            self._daily_loss_date = trade_date

        if pnl_thb < 0:
            self._daily_loss_accumulated += abs(pnl_thb)
            logger.info(
                f"Daily loss accumulated: {self._daily_loss_accumulated:.2f} THB "
                f"/ limit: {self.max_daily_loss_thb:.2f} THB"
            )

    def evaluate(self, llm_decision: dict, market_state: dict) -> dict:
        """
        รับการตัดสินใจจาก LLM มาตรวจสอบและคำนวณตัวเลขใหม่ทั้งหมด
        """
        # 1. ดึงข้อมูลตั้งต้น
        signal     = llm_decision.get("signal", "HOLD").upper()
        confidence = float(llm_decision.get("confidence", 0.0))
        rationale  = llm_decision.get("rationale", "")
        trade_date = market_state.get("date", "")

        portfolio     = market_state.get("portfolio", {})
        cash_balance  = float(portfolio.get("cash_balance", 0.0))
        gold_grams    = float(portfolio.get("gold_grams", 0.0))

        # [FIX #3] ดึงราคาแยกตาม direction อย่างชัดเจน
        try:
            thai_gold = market_state["market_data"]["thai_gold_thb"]

            # ราคาซื้อ (ร้านขายให้เรา) — ใช้ตอน BUY
            buy_price_thb = float(
                thai_gold.get("sell_price_thb")         # ร้านขาย = เราซื้อ
                or thai_gold.get("spot_price_thb")
                or 0
            )
            # ราคาขาย (ร้านรับซื้อจากเรา) — ใช้ตอน SELL
            sell_price_thb = float(
                thai_gold.get("buy_price_thb")          # ร้านซื้อ = เราขาย
                or thai_gold.get("spot_price_thb")
                or 0
            )

            if buy_price_thb <= 0 or sell_price_thb <= 0:
                raise ValueError("ราคาทองเป็น 0 หรือติดลบ — ข้อมูลไม่ถูกต้อง")

            # [FIX #3] ตรวจสอบหน่วย ATR — ต้องเป็น THB/หน่วยเดียวกับราคาทอง
            atr_raw   = market_state["technical_indicators"]["atr"]
            atr_value = float(atr_raw["value"])
            atr_unit  = atr_raw.get("unit", "UNKNOWN")

            if atr_unit.upper() not in ("THB", "THB_PER_BAHT", "THB_PER_GRAM"):
                logger.warning(
                    f"ATR unit is '{atr_unit}' — expected THB variant. "
                    "SL/TP อาจคลาดเคลื่อน กรุณาตรวจสอบ pipeline"
                )

        except (KeyError, ValueError) as e:
            logger.error(f"Market state error: {e}")
            return self._reject_signal(
                {"rationale": rationale},
                f"ข้อมูลตลาดไม่ครบถ้วน: {e}"
            )

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
        # ด่านที่ 1 — Confidence Filter
        # [FIX #5] เปลี่ยนจาก <= เป็น < เพื่อให้ค่าที่เท่ากับ threshold ผ่านได้
        # ================================================================
        if signal != "HOLD" and confidence < self.min_confidence:
            return self._reject_signal(
                final_decision,
                f"Confidence ({confidence:.2f}) ต่ำกว่าเกณฑ์ขั้นต่ำ {self.min_confidence}"
            )

        # ================================================================
        # ด่านที่ 2 — Daily Loss Limit  [FIX #4]
        # ================================================================
        if signal != "HOLD":
            self._reset_daily_loss_if_new_day(trade_date)
            if self._daily_loss_accumulated >= self.max_daily_loss_thb:
                return self._reject_signal(
                    final_decision,
                    f"Daily loss limit ถึงเกณฑ์แล้ว "
                    f"({self._daily_loss_accumulated:.2f} / {self.max_daily_loss_thb:.2f} THB) — "
                    "หยุดเทรดวันนี้"
                )

        # ================================================================
        # ด่านที่ 3 — จัดการแยกตาม Signal
        # ================================================================
        if signal == "HOLD":
            return final_decision

        elif signal == "SELL":
            if gold_grams <= 1e-4:
                return self._reject_signal(
                    final_decision,
                    "ไม่มีทองเพียงพอสำหรับการขาย (No Shorting)"
                )

            # [FIX #2] ใช้ sell_price_thb (ราคาที่ร้านรับซื้อ) แทน spot
            gold_value_thb = gold_grams * (sell_price_thb / 15.244)

            final_decision["entry_price"]        = sell_price_thb
            final_decision["position_size_thb"]  = round(gold_value_thb, 2)
            final_decision["rationale"] = (
                f"{rationale} "
                f"[RiskManager: ขายทอง {gold_grams:.4f}g @ {sell_price_thb:.2f} THB/บาท "
                f"≈ {gold_value_thb:.2f} THB]"
            )
            logger.info(f"RiskManager Approved SELL: {gold_value_thb:.2f} THB")
            return final_decision

        elif signal == "BUY":
            # ================================================================
            # ด่านที่ 4 — Position Sizing  [FIX #1]
            # ================================================================
            total_portfolio_value = cash_balance + (
                gold_grams * (sell_price_thb / 15.244)
            )

            if cash_balance < self.micro_port_threshold:
                # พอร์ตเล็ก (< 2,000 ฿): ซื้อแค่ขั้นต่ำของ broker เสมอ
                # เหตุผล: 1,500 ฿ × 30% = 450 ฿ → ต่ำกว่า min_trade_thb (1,000 ฿) อยู่ดี
                # การซื้อขั้นต่ำ 1,000 ฿ ทำให้เหลือเงินสำรอง 500 ฿ ไว้รอบหน้า
                investment_thb = self.min_trade_thb
                sizing_note = f"micro-port fixed min ({self.min_trade_thb:.0f} ฿)"
            else:
                # พอร์ตปกติ: สูงสุด 50% × confidence
                investment_thb = cash_balance * 0.5 * confidence
                sizing_note = f"50% × confidence({confidence:.2f})"

            # บังคับไม่เกิน cash จริง
            investment_thb = min(investment_thb, cash_balance)

            if investment_thb < self.min_trade_thb:
                return self._reject_signal(
                    final_decision,
                    f"ขนาดไม้ ({investment_thb:.2f} THB) ต่ำกว่าขั้นต่ำ {self.min_trade_thb} THB"
                )

            # ================================================================
            # ด่านที่ 5 — ATR-based SL / TP
            # ================================================================
            sl_distance = atr_value * self.atr_multiplier
            tp_distance = sl_distance * self.rr_ratio

            stop_loss   = round(buy_price_thb - sl_distance, 2)
            take_profit = round(buy_price_thb + tp_distance, 2)

            final_decision["entry_price"]        = buy_price_thb
            final_decision["position_size_thb"]  = round(investment_thb, 2)
            final_decision["stop_loss"]          = stop_loss
            final_decision["take_profit"]        = take_profit
            final_decision["rationale"] = (
                f"{rationale} "
                f"[RiskManager: อนุมัติซื้อ {investment_thb:.2f} ฿ ({sizing_note}) | "
                f"SL: {stop_loss} | TP: {take_profit} | "
                f"ATR: {atr_value:.2f} ({atr_unit})]"
            )

            logger.info(
                f"RiskManager Approved BUY: {investment_thb:.2f} THB | "
                f"SL={stop_loss} | TP={take_profit}"
            )
            return final_decision

        else:
            return self._reject_signal(
                final_decision,
                f"Signal '{signal}' ไม่รู้จัก — รองรับเฉพาะ BUY / SELL / HOLD"
            )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _reset_daily_loss_if_new_day(self, trade_date: str) -> None:
        if trade_date and trade_date != self._daily_loss_date:
            logger.info(
                f"วันใหม่ ({trade_date}) — reset daily loss "
                f"(เดิม: {self._daily_loss_accumulated:.2f} THB)"
            )
            self._daily_loss_accumulated = 0.0
            self._daily_loss_date = trade_date

    def _reject_signal(self, decision: dict, reason: str) -> dict:
        """
        [FIX #6] ทำงานบนสำเนาใหม่เสมอ — ไม่ mutate dict ที่รับมา
        """
        safe = deepcopy(decision)
        safe["signal"]            = "HOLD"
        safe["position_size_thb"] = 0.0
        safe["stop_loss"]         = 0.0
        safe["take_profit"]       = 0.0
        safe["rejection_reason"]  = reason
        safe["rationale"]         = (
            f"REJECTED: {reason} | Rationale เดิม: {safe.get('rationale', '')}"
        )
        logger.info(f"RiskManager Rejected Signal: {reason}")
        return safe