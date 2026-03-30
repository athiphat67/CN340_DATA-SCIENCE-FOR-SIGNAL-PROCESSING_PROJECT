import logging

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(
        self, 
        atr_multiplier: float = 2.0, 
        risk_reward_ratio: float = 1.5,
        min_confidence: float = 0.7,      # ย้ายมาเป็นพารามิเตอร์
        min_trade_thb: float = 1000.0,    # ย้ายมาเป็นพารามิเตอร์
        micro_port_threshold: float = 2000.0
    ):
        self.atr_multiplier = atr_multiplier
        self.rr_ratio = risk_reward_ratio
        self.min_confidence = min_confidence
        self.min_trade_thb = min_trade_thb
        self.micro_port_threshold = micro_port_threshold

    def evaluate(self, llm_decision: dict, market_state: dict) -> dict:
        """
        รับการตัดสินใจจาก LLM มาตรวจสอบและคำนวณตัวเลขใหม่ทั้งหมด
        """
        # 1. ดึงข้อมูลตั้งต้น (ปลอดภัยด้วย .get())
        signal = llm_decision.get("signal", "HOLD").upper()
        confidence = float(llm_decision.get("confidence", 0.0))
        rationale = llm_decision.get("rationale", "")
        
        portfolio = market_state.get("portfolio", {})
        cash_balance = float(portfolio.get("cash_balance", 0.0))
        gold_grams = float(portfolio.get("gold_grams", 0.0))
        
        # ป้องกัน KeyError ด้วยการใช้ .get() แบบซ้อนกัน หรือ Try-Except
        try:
            current_price_thb = float(market_state["market_data"]["thai_gold_thb"]["spot_price_thb"])
            atr_value = float(market_state["technical_indicators"]["atr"]["value"])
        except KeyError as e:
            logger.error(f"Market state missing required key: {e}")
            # ส่งเป็น HOLD เพื่อความปลอดภัยกรณีดึงข้อมูลพลาด
            return self._reject_signal({"rationale": rationale}, f"ข้อมูลตลาดไม่ครบถ้วน: ขาด {e}")

        # โครงสร้างผลลัพธ์ที่จะส่งคืน
        final_decision = {
            "signal": signal,
            "confidence": confidence,
            "entry_price": current_price_thb,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "position_size_thb": 0.0,
            "rationale": rationale,
            "rejection_reason": None
        }

        # --- ด่านที่ 1: ตรวจสอบ Confidence ---
        if confidence <= self.min_confidence and signal != "HOLD":
            return self._reject_signal(final_decision, f"Confidence ({confidence}) ต่ำกว่า {self.min_confidence}")

        # --- ด่านที่ 2: จัดการแยกตาม Signal (BUY / SELL / HOLD) ---
        if signal == "HOLD":
            return final_decision

        elif signal == "SELL":
            # ตรวจสอบทองในพอร์ตด้วยระยะขอบทศนิยม (Margin) ป้องกันเศษทองตกค้าง
            if gold_grams <= 1e-4:
                return self._reject_signal(final_decision, "ไม่มีทองเพียงพอสำหรับการขาย (No Shorting)")
            
            # ปิดสถานะ (คำนวณมูลค่าทองคำที่มีอยู่ ณ ราคาปัจจุบัน)
            # หมายเหตุ: ลองเช็คกับ API ดูว่าต้องใช้ราคาเสนอซื้อ (Bid) แทน Spot ไหม
            current_gold_value = gold_grams * (current_price_thb / 15.244) # สมมติสูตร: กรัม * (ราคาบาททอง / 15.244 กรัม) หรือปรับตาม Logic ที่ใช้
            
            # หรือถ้า broker รับคำสั่งเป็นจำนวนกรัม ให้ตั้งตัวแปรมารองรับเพิ่มเติม
            final_decision["position_size_thb"] = round(current_gold_value, 2)
            final_decision["rationale"] = f"{rationale} [RiskManager: สั่งขายทองทั้งหมดในพอร์ตเพื่อปิดสถานะ]"
            return final_decision

        elif signal == "BUY":
            # --- ด่านที่ 3: คำนวณ Position Sizing (Micro-Portfolio Logic) ---
            if cash_balance < self.micro_port_threshold:
                investment_thb = cash_balance # All-in
            else:
                investment_thb = cash_balance * 0.5 * confidence # ซื้อสูงสุด 50% ตามความมั่นใจ

            # Fallback ขั้นต่ำของการเทรด
            if investment_thb < self.min_trade_thb:
                return self._reject_signal(final_decision, f"ขนาดไม้ที่คำนวณได้ ({investment_thb:.2f} THB) ต่ำกว่าขั้นต่ำ {self.min_trade_thb} THB")
            
            # บังคับไม่ให้ซื้อเกินเงินที่มี
            investment_thb = min(investment_thb, cash_balance)

            # --- ด่านที่ 4: คำนวณ SL / TP ด้วย ATR ---
            sl_distance = atr_value * self.atr_multiplier
            tp_distance = sl_distance * self.rr_ratio

            final_decision["position_size_thb"] = round(investment_thb, 2)
            final_decision["stop_loss"] = round(current_price_thb - sl_distance, 2)
            final_decision["take_profit"] = round(current_price_thb + tp_distance, 2)
            
            final_decision["rationale"] = f"{rationale} [RiskManager: อนุมัติซื้อ {investment_thb:.2f} ฿ | SL: {final_decision['stop_loss']} | TP: {final_decision['take_profit']}]"
            
            logger.info(f"RiskManager Approved BUY: {investment_thb:.2f} THB")
            return final_decision

    def _reject_signal(self, decision: dict, reason: str) -> dict:
        """Helper method สำหรับการเปลี่ยน Signal เป็น HOLD เมื่อผิดกฎ"""
        # สร้างสำเนาใหม่ หรืออัปเดต Dictionary ให้ปลอดภัยถ้ามีคีย์เก่าไม่ครบ
        decision["signal"] = "HOLD"
        decision["position_size_thb"] = 0.0
        decision["stop_loss"] = 0.0
        decision["take_profit"] = 0.0
        decision["rejection_reason"] = reason
        old_rationale = decision.get("rationale", "")
        decision["rationale"] = f"REJECTED: {reason} | Rationale เดิม: {old_rationale}"
        logger.info(f"RiskManager Rejected Signal: {reason}")
        return decision