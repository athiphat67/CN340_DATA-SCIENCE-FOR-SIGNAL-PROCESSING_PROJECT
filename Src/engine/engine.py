"""
engine/engine.py  — The Watcher Engine (v2.0)
Event-driven market watcher that triggers AI analysis on signal.

Changes v2.0 (Full Priority Fix):
  [P0] TriggerState: ใส่ threading.Lock() ป้องกัน race condition
  [P0] _execute_emergency_sell: เรียก db.record_emergency_sell_atomic() จริง (atomic transaction)
  [P1] Defensive price reading: ไม่ใช้ silent default fallback 72000.0 อีกต่อไป
  [P1] trailing_stop_level ถูก persist ลง DB ผ่าน save_portfolio ไม่หายหลัง restart
  [P2] GOLD_BAHT_TO_GRAM เป็น module-level constant
  [P2] WatcherConfig Pydantic model — fail fast ถ้า config ขาด key
  [P3] AI decision ถูกส่งต่อ: Telegram/Discord notify + broker hook stub
"""

import threading
import time
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ─── [P2] Module-level constant (ป้องกัน magic number กระจาย) ──────────────
GOLD_BAHT_TO_GRAM: float = 15.244   # 1 บาทน้ำหนัก = 15.244 กรัม


# ─── [P2] WatcherConfig — Pydantic validation (fail fast) ──────────────────
class WatcherConfig(BaseModel):
    """
    Config สำหรับ WatcherEngine — validate ตอน init ทันที
    ถ้า key ขาดหรือผิด type จะ raise ValidationError ก่อน thread ขึ้น
    """
    provider:        str   = Field(default="gemini",     description="LLM provider")
    period:          str   = Field(default="1d",         description="Data period")
    interval:        str   = Field(default="5m",         description="Candle interval")
    cooldown_minutes: int  = Field(default=5,   ge=1,    description="Min minutes between AI triggers")
    min_price_step:  float = Field(default=1.5, gt=0.0,  description="Min THB/gram move to re-trigger")
    rsi_oversold:    float = Field(default=30.0, ge=0,   le=50, description="RSI oversold threshold")
    rsi_overbought:  float = Field(default=70.0, ge=50,  le=100, description="RSI overbought threshold")
    trailing_stop_profit_trigger: float = Field(default=20.0, gt=0, description="Profit/gram ที่ขยับ SL")
    trailing_stop_lock_in:        float = Field(default=5.0,  gt=0, description="SL lock-in เหนือ cost")
    hard_stop_loss_per_gram:      float = Field(default=15.0, gt=0, description="Max loss/gram ก่อน cut")
    loop_sleep_seconds: int = Field(default=30, gt=0, description="วินาทีในการพักของ Watcher loop")

    @field_validator("provider")
    @classmethod
    def provider_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("provider must not be empty")
        return v.strip()

    @field_validator("period")
    @classmethod
    def valid_period(cls, v: str) -> str:
        allowed = {"1d", "3d", "5d", "7d", "14d", "1mo", "2mo", "3mo"}
        if v not in allowed:
            raise ValueError(f"period must be one of {allowed}, got '{v}'")
        return v


# ─── 1. State Manager (คุม Cooldown & Price Step) ──────────────────────────
class TriggerState:
    def __init__(self, cooldown_minutes: int = 5, min_price_step_thb: float = 1.5):
        self.cooldown_seconds = cooldown_minutes * 60
        self.min_price_step   = min_price_step_thb  # THB/gram
        self.last_trigger_time  = 0.0
        self.last_trigger_price = 0.0
        # [P0] Lock ป้องกัน race condition: _watcher_loop + is_ready() อ่านพร้อมกัน
        self._lock = threading.Lock()

    def is_ready(self, current_price_per_gram: float) -> tuple[bool, str]:
        with self._lock:
            current_time = time.time()

            # 1. Cooldown Lock
            time_elapsed = current_time - self.last_trigger_time
            if time_elapsed < self.cooldown_seconds:
                remaining = self.cooldown_seconds - time_elapsed
                return False, f"Cooldown: {remaining:.0f}s left"

            # 2. Dynamic Price Step
            if self.last_trigger_price > 0:
                price_diff = abs(current_price_per_gram - self.last_trigger_price)
                if price_diff < self.min_price_step:
                    return False, (
                        f"Price Step: Moved only {price_diff:.2f} ฿/g "
                        f"(Need {self.min_price_step})"
                    )

            return True, "Ready"

    def update_trigger(self, current_price_per_gram: float) -> None:
        with self._lock:
            self.last_trigger_time  = time.time()
            self.last_trigger_price = current_price_per_gram


# ─── 2. The Watcher Engine ──────────────────────────────────────────────────
class WatcherEngine:
    def __init__(
        self,
        analysis_service,
        data_orchestrator,
        watcher_config: dict,
    ):
        self.analysis_service  = analysis_service
        self.data_orchestrator = data_orchestrator

        # [P2] Validate config ทันที — ถ้า key ขาดหรือผิด type raise ก่อน thread ขึ้น
        self.config = WatcherConfig(**watcher_config)

        self.is_running = False
        self.lock       = threading.Lock()
        self.logs: list[str] = []

        # [P0] TriggerState มี lock ในตัวเองแล้ว
        self.trigger_state = TriggerState(
            cooldown_minutes  = self.config.cooldown_minutes,
            min_price_step_thb= self.config.min_price_step,
        )

        # [P1] Trailing stop level — โหลดจาก DB ตอน init เพื่อไม่ให้หายหลัง restart
        self._active_trailing_sl_per_gram: Optional[float] = None
        self._load_trailing_stop_from_portfolio()

    # ── Logging ──────────────────────────────────────────────────────────────

    def log(self, msg: str, level: str = "INFO") -> None:
        with self.lock:
            time_str = datetime.now().strftime("%H:%M:%S")
            log_msg  = f"[{time_str}] {msg}"
            self.logs.append(log_msg)
            if len(self.logs) > 50:
                self.logs.pop(0)
            if level == "ERROR":
                logger.error(log_msg)
            else:
                logger.info(log_msg)

    def get_logs(self) -> list[str]:
        """Thread-safe log snapshot สำหรับ Gradio UI"""
        with self.lock:
            return list(self.logs)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._watcher_loop, daemon=True)
            self.thread.start()
            self.log("🚀 Watcher Engine Started")

    def stop(self) -> None:
        self.is_running = False
        self.log("🛑 Watcher Engine Stopped")

    # ── Main Loop ─────────────────────────────────────────────────────────────

    def _watcher_loop(self) -> None:
        while self.is_running:
            try:
                # 1. Snapshot ข้อมูลตลาด
                market_state = self.data_orchestrator.run(
                    history_days=1,
                    interval=self.config.interval,
                )

                # [P1] Defensive price reading — ไม่ใช้ silent fallback 72000.0
                current_price_per_gram = self._extract_price(market_state)
                if current_price_per_gram is None:
                    self.log("⚠️ Cannot read gold price — skipping cycle", "ERROR")
                    time.sleep(3)
                    continue

                # 🛡️ LAYER 4: Trailing Stop (Real-time)
                self._manage_trailing_stop(current_price_per_gram)

                # LAYER 3: Rule-based trigger (RSI filter)
                ti  = market_state.get("technical_indicators", {})
                rsi = ti.get("rsi", {}).get("value")

                if rsi is None:
                    self.log("⚠️ RSI not available in market data — skipping trigger check")
                    time.sleep(3)
                    continue

                is_math_triggered = (
                    rsi < self.config.rsi_oversold or
                    rsi > self.config.rsi_overbought
                )

                if is_math_triggered:
                    ready, reason = self.trigger_state.is_ready(current_price_per_gram)
                    if ready:
                        self.log(
                            f"🔥 Signal Confirmed (RSI={rsi:.1f}, "
                            f"Price={current_price_per_gram:.2f} ฿/g). Waking up AI!"
                        )
                        self.trigger_state.update_trigger(current_price_per_gram)
                        self._trigger_analysis()
                    else:
                        self.log(f"🔒 Trigger blocked — {reason}")

            except Exception as e:
                self.log(f"❌ Watcher Error: {e}", "ERROR")

            time.sleep(self.config.loop_sleep_seconds)

    # ── [P1] Defensive price extraction ──────────────────────────────────────

    def _extract_price(self, market_state: dict) -> Optional[float]:
        """
        อ่านราคาทองจาก market_state อย่าง defensive
        คืน None ถ้าข้อมูลไม่ครบ — caller ต้องจัดการ ไม่ใช้ silent fallback
        """
        raw_price = (
            market_state
            .get("market_data", {})
            .get("thai_gold_thb", {})
            .get("sell_price_thb")
        )
        if raw_price is None:
            return None
        try:
            # [P2] ใช้ module constant ไม่ใช่ magic number
            return float(raw_price) / GOLD_BAHT_TO_GRAM
        except (TypeError, ValueError) as e:
            self.log(f"⚠️ Price parse error: {e}", "ERROR")
            return None

    # ── [P1] Trailing Stop (persist state) ───────────────────────────────────

    def _load_trailing_stop_from_portfolio(self) -> None:
        """
        โหลด trailing_stop_level จาก DB ตอน init
        เพื่อให้ SL ไม่หายหลัง Watcher restart
        """
        try:
            portfolio = self.analysis_service.persistence.get_portfolio()
            sl = portfolio.get("trailing_stop_level_thb")
            if sl:
                self._active_trailing_sl_per_gram = float(sl)
                self.log(
                    f"📂 Trailing SL restored from DB: "
                    f"{self._active_trailing_sl_per_gram:.2f} ฿/g"
                )
        except Exception as e:
            self.log(f"⚠️ Could not load trailing SL from DB: {e}", "ERROR")

    def _manage_trailing_stop(self, current_price_per_gram: float) -> None:
        """เช็คกำไร/ขาดทุนจากตาราง Portfolio (Average Cost)"""
        try:
            portfolio        = self.analysis_service.persistence.get_portfolio()
            gold_grams       = float(portfolio.get("gold_grams", 0.0))
            cost_basis       = float(portfolio.get("cost_basis_thb", 0.0))
        except Exception as e:
            self.log(f"❌ Cannot read portfolio for trailing stop: {e}", "ERROR")
            return

        if gold_grams <= 0:
            # ไม่มีของในมือ — reset trailing SL
            if self._active_trailing_sl_per_gram is not None:
                self._active_trailing_sl_per_gram = None
            return

        profit_per_gram = current_price_per_gram - cost_basis

        # กฎ 1: เลื่อน SL บังทุน (กำไร ≥ trigger → SL = cost + lock_in)
        if profit_per_gram >= self.config.trailing_stop_profit_trigger:
            new_sl = cost_basis + self.config.trailing_stop_lock_in

            # [P1] ถ้า SL ใหม่สูงกว่าเดิม (หรือยังไม่มี) → update และ persist
            if (
                self._active_trailing_sl_per_gram is None or
                new_sl > self._active_trailing_sl_per_gram
            ):
                self._active_trailing_sl_per_gram = new_sl
                self._persist_trailing_stop(new_sl)
                self.log(
                    f"🔼 Trailing SL raised to {new_sl:.2f} ฿/g "
                    f"(profit={profit_per_gram:.2f} ฿/g)"
                )

            if current_price_per_gram <= self._active_trailing_sl_per_gram:
                self.log(
                    f"🚨 [TRAILING STOP] Hit SL "
                    f"{self._active_trailing_sl_per_gram:.2f} ฿/g! Emergency Sell."
                )
                self._execute_emergency_sell(
                    gold_grams,
                    current_price_per_gram,
                    f"Trailing Stop Break-even hit @ {self._active_trailing_sl_per_gram:.2f}",
                )

        # กฎ 2: Hard Stop Loss (ขาดทุนเกิน threshold)
        elif profit_per_gram <= -self.config.hard_stop_loss_per_gram:
            self.log(
                f"💥 [HARD SL] Max loss limit reached! "
                f"Cutting at {current_price_per_gram:.2f} ฿/g "
                f"(loss={profit_per_gram:.2f} ฿/g)"
            )
            self._execute_emergency_sell(
                gold_grams,
                current_price_per_gram,
                f"Global Hard Stop Loss hit (loss={profit_per_gram:.2f} ฿/g)",
            )

    def _persist_trailing_stop(self, new_sl_per_gram: float) -> None:
        """บันทึก trailing_stop_level_thb ลง portfolio row"""
        try:
            portfolio = self.analysis_service.persistence.get_portfolio()
            portfolio["trailing_stop_level_thb"] = round(new_sl_per_gram, 4)
            self.analysis_service.persistence.save_portfolio(portfolio)
        except Exception as e:
            self.log(f"⚠️ Could not persist trailing SL to DB: {e}", "ERROR")

    # ── [P0] Emergency Sell — Atomic Transaction ──────────────────────────────

    def _execute_emergency_sell(
        self,
        grams_to_sell: float,
        price_thb_per_gram: float,
        reason: str,
    ) -> None:
        """
        ส่งคำสั่งขาย + บันทึก DB แบบ Atomic Transaction
        เรียก db.record_emergency_sell_atomic() ซึ่ง wrap trade_log + portfolio update
        ในลูป transaction เดียว — ป้องกัน Phantom Gold

        NOTE: เปิด broker_api.sell() เมื่อเชื่อมต่อ broker จริงแล้ว
        """
        self.log(
            f"🛒 Emergency SELL: {grams_to_sell:.4f}g "
            f"@ {price_thb_per_gram:.2f} ฿/g | Reason: {reason}"
        )

        try:
            # ── [BROKER STUB] ─────────────────────────────────────────
            # broker_api.sell(grams_to_sell, price_thb_per_gram)
            # ─────────────────────────────────────────────────────────

            # [P0] Atomic: trade_log INSERT + portfolio UPDATE ใน transaction เดียว
            self.analysis_service.persistence.record_emergency_sell_atomic(
                grams          = grams_to_sell,
                price_per_gram = price_thb_per_gram,
                reason         = reason,
            )
            # Reset trailing SL หลังขายออกหมด
            self._active_trailing_sl_per_gram = None
            self.log("✅ Emergency sell recorded atomically in DB")

        except Exception as e:
            # CRITICAL: ถ้า DB fail — อย่า silent fail, log ด้วย level ERROR
            self.log(
                f"🔥 CRITICAL: Emergency sell DB write failed: {e} "
                f"— Manual reconciliation required!",
                "ERROR",
            )

    # ── [P3] Trigger Analysis → pass result downstream ───────────────────────

    def _trigger_analysis(self) -> None:
        """
        ปลุก AI ผ่าน AnalysisService
        [P3] result ถูกส่งต่อไปยัง: notification + broker hook
        """
        try:
            result = self.analysis_service.run_analysis(
                provider  = self.config.provider,
                period    = self.config.period,
                intervals = [self.config.interval],
                bypass_session_gate=False,
            )

            if result.get("status") != "success":
                self.log(
                    f"⚠️ AI analysis returned error: "
                    f"{result.get('error', 'unknown')}",
                    "ERROR",
                )
                return

            voting   = result.get("voting_result", {})
            decision = voting.get("final_signal", "UNKNOWN")
            conf     = voting.get("weighted_confidence", 0.0)
            run_id   = result.get("run_id")

            self.log(
                f"🎯 AI Decision: {decision} "
                f"({conf:.0%} confidence) | run_id={run_id}"
            )

            # [P3] Notification — AnalysisService จัดการ Discord/Telegram แล้ว
            # (services.py step 2g/2h) ดังนั้นไม่ต้อง notify ซ้ำที่นี่

            # [P3] Broker action hook — implement เมื่อพร้อม execute จริง
            self._on_ai_decision(decision, conf, result)

        except Exception as e:
            self.log(f"❌ AI Analysis Failed: {e}", "ERROR")

    def _on_ai_decision(
        self,
        decision: str,
        confidence: float,
        full_result: dict,
    ) -> None:
        """
        Hook สำหรับ action หลังจากที่ AI ตัดสินแล้ว
        [P3] ขยายที่นี่เมื่อพร้อม auto-execute order

        ตัวอย่าง:
            if decision == "BUY" and confidence >= 0.75:
                broker_api.place_order("BUY", grams=0.5)
        """
        # ตอนนี้ log ไว้ก่อน — uncomment/implement เมื่อพร้อม
        self.log(
            f"📬 _on_ai_decision: {decision} ({confidence:.0%}) "
            f"— broker hook not yet implemented"
        )
