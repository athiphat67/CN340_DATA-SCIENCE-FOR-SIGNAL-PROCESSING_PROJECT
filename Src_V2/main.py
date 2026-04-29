"""
main.py — นักขุดทอง v2 (XGBoost-based) Orchestration Loop
==========================================================

จุดเริ่มต้นของระบบ — ทำหน้าที่เป็น delegator ที่:
    1. Build runtime (orchestrator, signal engine, core, notifiers, db)
    2. ดึง market_state ผ่าน data_engine.GoldTradingOrchestrator
    3. แปลงเป็น 37-feature vector ผ่าน data_engine.extract_features.get_xgboost_feature
    4. ส่งให้ ml_core.signal.XGBoostPredictor → (signal, confidence)
    5. ส่งให้ core.CoreDecision → fan-out ไป risk + session_gate (concurrent)
    6. ALL PASS  → ส่ง notification (Discord + Telegram) + บันทึก database
       REJECT/HOLD → ข้าม notification, แต่ยังบันทึก database เสมอ
    7. รอ interval (default 900s = 15 นาที) แล้ววนรอบใหม่

ระบบนี้ไม่มีส่วนใดเกี่ยวข้องกับ Generative Models / Agent loops
ทั้ง Decision Engine เป็น Pure ML (XGBoost) ตามสถาปัตยกรรม v2

ใช้งาน:
    python -m Src_V2.main                      # ใช้ default
    python Src_V2/main.py --interval 600       # รัน loop ทุก 10 นาที
    python Src_V2/main.py --no-save --once     # dry-run รอบเดียว
"""

from __future__ import annotations

import argparse
import logging
import os
import signal as _os_signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# ── Path setup: ให้ import จาก Src_V2/* ทำงานได้ทั้งจาก root และ จากในโฟลเดอร์
_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

# ── Domain imports (after sys.path tweak) ────────────────────
from core import CoreDecision, Decision  # noqa: E402
from data_engine.extract_features import get_xgboost_feature  # noqa: E402
from data_engine.orchestrator import GoldTradingOrchestrator  # noqa: E402
from logs.logger_setup import sys_logger  # noqa: E402
from ml_core.risk import RiskManager  # noqa: E402

# ── Optional dependencies (graceful import) ──────────────────
try:
    from ml_core.signal import XGBoostPredictor
except Exception as _e:  # pragma: no cover
    XGBoostPredictor = None  # type: ignore
    sys_logger.warning(f"[main] ml_core.signal import failed → using mock: {_e}")

try:
    from database.database import RunDatabase
except Exception as _e:  # pragma: no cover
    RunDatabase = None  # type: ignore
    sys_logger.warning(f"[main] database.database import failed → DB disabled: {_e}")

try:
    from notification.discord_notifier import DiscordNotifier
except Exception as _e:  # pragma: no cover
    DiscordNotifier = None  # type: ignore
    sys_logger.warning(f"[main] DiscordNotifier import failed: {_e}")

try:
    from notification.telegram_notifier import TelegramNotifier
except Exception as _e:  # pragma: no cover
    TelegramNotifier = None  # type: ignore
    sys_logger.warning(f"[main] TelegramNotifier import failed: {_e}")

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Constants — อ้างอิงจาก Src_V2/about-main.md §1.3
# ─────────────────────────────────────────────────────────────

INITIAL_CAPITAL_THB: float = 1500.0       # ทุนเริ่มต้น (Aom NOW)
DEFAULT_INTERVAL_SEC: int = 900           # 15 นาที / รอบ
DEFAULT_MODEL_PATH: str = "models/xgb_v1.json"
PROVIDER_TAG: str = "xgboost-v2"          # tag ที่จะบันทึกใน runs.provider


# ─────────────────────────────────────────────────────────────
# Mock signal predictor — ใช้ตอน model file หาย (fail-safe)
# ─────────────────────────────────────────────────────────────


class _MockPredictor:
    """Fallback predictor ถ้าโหลด XGBoost ไม่ได้ — คืน HOLD เสมอเพื่อความปลอดภัย"""

    def __init__(self, *_args, **_kwargs) -> None:
        self.loaded = False

    def predict(self, _features: Dict[str, Any], session: str = "Unknown"):
        @dataclass
        class _Out:
            direction: str = "HOLD"
            confidence: float = 0.0
            prob_buy: float = 0.0
            prob_sell: float = 0.0
            session: str = session
            is_high_accuracy_session: bool = False

        return _Out()


# ─────────────────────────────────────────────────────────────
# Runtime container
# ─────────────────────────────────────────────────────────────


@dataclass
class Runtime:
    """รวม dependency ทั้งหมดที่ main loop ต้องใช้"""

    orchestrator: GoldTradingOrchestrator
    signal_engine: Any           # XGBoostPredictor | _MockPredictor
    core: CoreDecision
    database: Optional[Any]      # RunDatabase | None
    discord: Optional[Any]
    telegram: Optional[Any]
    save_to_db: bool = True


# ─────────────────────────────────────────────────────────────
# Build runtime
# ─────────────────────────────────────────────────────────────


def build_runtime(
    *,
    model_path: str = DEFAULT_MODEL_PATH,
    enable_db: bool = True,
    enable_notify: bool = True,
) -> Runtime:
    """ประกอบ runtime สำหรับ main loop"""
    sys_logger.info("=" * 60)
    sys_logger.info("[main] Building runtime — XGBoost v2 pipeline")
    sys_logger.info("=" * 60)

    # 1) Data orchestrator (เริ่ม WebSocket interceptor ในตัว)
    orchestrator = GoldTradingOrchestrator()
    sys_logger.info("[main] ✓ GoldTradingOrchestrator ready")

    # 2) XGBoost signal engine — fail-safe fallback to mock
    signal_engine: Any
    if XGBoostPredictor is not None and os.path.exists(model_path):
        try:
            signal_engine = XGBoostPredictor(model_path=model_path)
            sys_logger.info(f"[main] ✓ XGBoostPredictor loaded from {model_path}")
        except Exception as exc:
            sys_logger.error(f"[main] XGBoostPredictor init failed: {exc} → mock")
            signal_engine = _MockPredictor()
    else:
        if XGBoostPredictor is None:
            sys_logger.warning("[main] XGBoostPredictor unavailable → mock")
        else:
            sys_logger.warning(f"[main] Model file not found at {model_path} → mock")
        signal_engine = _MockPredictor()

    # 3) Core decision (ภายในรัน RiskManager + SessionGate ขนานกัน)
    risk_manager = RiskManager(
        atr_multiplier=2.5,
        risk_reward_ratio=1.5,
        min_confidence=0.60,
        min_sell_confidence=0.60,
        min_trade_thb=1400.0,
        max_daily_loss_thb=500.0,
        max_trade_risk_pct=0.20,
        enable_trailing_stop=True,
    )
    core = CoreDecision(risk_manager=risk_manager)
    sys_logger.info("[main] ✓ CoreDecision (RiskManager + SessionGate concurrent) ready")

    # 4) Database (optional)
    database: Optional[Any] = None
    if enable_db and RunDatabase is not None:
        try:
            database = RunDatabase()
            sys_logger.info("[main] ✓ RunDatabase connected")
        except Exception as exc:
            sys_logger.error(f"[main] RunDatabase init failed: {exc} → DB disabled")
            database = None

    # 5) Notifiers (optional)
    discord = None
    telegram = None
    if enable_notify:
        if DiscordNotifier is not None:
            try:
                discord = DiscordNotifier()
                sys_logger.info("[main] ✓ DiscordNotifier ready")
            except Exception as exc:
                sys_logger.warning(f"[main] DiscordNotifier disabled: {exc}")
        if TelegramNotifier is not None:
            try:
                telegram = TelegramNotifier()
                sys_logger.info("[main] ✓ TelegramNotifier ready")
            except Exception as exc:
                sys_logger.warning(f"[main] TelegramNotifier disabled: {exc}")

    return Runtime(
        orchestrator=orchestrator,
        signal_engine=signal_engine,
        core=core,
        database=database,
        discord=discord,
        telegram=telegram,
        save_to_db=enable_db and database is not None,
    )


# ─────────────────────────────────────────────────────────────
# One full analysis cycle
# ─────────────────────────────────────────────────────────────


def run_analysis_once(rt: Runtime, *, skip_fetch: bool = False) -> Decision:
    """
    รันรอบ pipeline 1 ครั้ง:

        market_state → feature_list → (signal, conf) → CoreDecision → notify + persist

    คืน `Decision` สุดท้ายที่ตัดสินใจ
    """
    cycle_start = time.perf_counter()

    # ── 1. Data Engine ─────────────────────────────────────────
    sys_logger.info("[cycle] (1/5) fetching market_state via orchestrator")
    market_state = rt.orchestrator.run(save_to_file=not skip_fetch)

    # ── 2. Feature extraction ──────────────────────────────────
    sys_logger.info("[cycle] (2/5) extracting 37-dim feature vector")
    try:
        feature_dict = get_xgboost_feature(market_state, as_dataframe=False)
    except Exception as exc:
        sys_logger.exception(f"[cycle] feature extraction failed: {exc}")
        return Decision(
            final="HOLD", model_signal="HOLD", confidence=0.0,
            reject_reason=f"feature_error:{exc}", notify=False,
        )

    # ── 3. XGBoost prediction → (signal, confidence) ──────────
    sys_logger.info("[cycle] (3/5) XGBoost predict + predict_proba")
    session_label = _resolve_session_label(market_state)
    try:
        xgb_out = rt.signal_engine.predict(feature_dict, session=session_label)
        signal = str(getattr(xgb_out, "direction", "HOLD")).upper()
        confidence = float(getattr(xgb_out, "confidence", 0.0))
    except Exception as exc:
        sys_logger.exception(f"[cycle] XGBoost predict failed: {exc}")
        signal, confidence = "HOLD", 0.0

    sys_logger.info(f"[cycle] XGBoost → {signal} (conf={confidence:.3f})")

    # ── 4. Core decision (fan-out gates) ───────────────────────
    sys_logger.info("[cycle] (4/5) CoreDecision evaluating gates concurrently")
    decision = rt.core.evaluate(
        signal=signal,
        confidence=confidence,
        market_state=market_state,
        rationale=f"[XGBoost v2] {signal} @ {confidence:.2%}",
    )

    sys_logger.info(
        f"[cycle] Decision: final={decision.final} notify={decision.notify} "
        f"reject={decision.reject_reason or '-'}"
    )

    # ── 5. Notify (YES only) + Persist (always) ────────────────
    sys_logger.info("[cycle] (5/5) notify + persist")
    _notify_if_pass(rt, decision, market_state)
    _persist_run(rt, decision, market_state)

    elapsed_ms = (time.perf_counter() - cycle_start) * 1000
    sys_logger.info(f"[cycle] DONE in {elapsed_ms:,.1f} ms")
    return decision


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _resolve_session_label(market_state: Dict[str, Any]) -> str:
    """แปลง session_gate.session_id → label ที่ XGBoost รู้จัก (Morning/Afternoon/Evening)"""
    sg = market_state.get("session_gate") or {}
    sid = (sg.get("session_id") or "").lower()
    if sid in ("night", "morning"):
        return "Morning"
    if sid == "noon":
        return "Afternoon"
    if sid == "evening":
        return "Evening"
    return "Unknown"


def _notify_if_pass(
    rt: Runtime, decision: Decision, market_state: Dict[str, Any]
) -> None:
    """ส่ง Discord + Telegram เฉพาะกรณี ALL PASS (decision.notify == True)"""
    if not decision.notify:
        sys_logger.debug("[notify] skipped — gate not all-pass")
        return

    voting_result = {
        "final_signal":        decision.final,
        "weighted_confidence": float(decision.confidence),
        "rationale":           decision.rationale,
    }
    interval_results = {
        "xgb": {
            "signal":       decision.final,
            "confidence":   float(decision.confidence),
            "entry_price":  decision.entry_price,
            "stop_loss":    decision.stop_loss,
            "take_profit":  decision.take_profit,
            "provider":     PROVIDER_TAG,
        }
    }

    if rt.discord is not None:
        try:
            ok = rt.discord.notify(
                voting_result=voting_result,
                interval_results=interval_results,
                market_state=market_state,
                provider=PROVIDER_TAG,
                period="live",
                run_id=None,
            )
            sys_logger.info(f"[notify] discord sent={ok}")
        except Exception as exc:
            sys_logger.error(f"[notify] discord failed: {exc}")

    if rt.telegram is not None:
        try:
            ok = rt.telegram.notify(
                voting_result=voting_result,
                provider=PROVIDER_TAG,
                period="live",
                interval_results=interval_results,
                market_state=market_state,
                run_id=None,
            )
            sys_logger.info(f"[notify] telegram sent={ok}")
        except Exception as exc:
            sys_logger.error(f"[notify] telegram failed: {exc}")


def _persist_run(
    rt: Runtime, decision: Decision, market_state: Dict[str, Any]
) -> Optional[int]:
    """บันทึกลง DB เสมอ (ทั้ง YES และ HOLD) — ตามหลัก database-first ใน spec §11.1"""
    if not rt.save_to_db or rt.database is None:
        sys_logger.debug("[persist] skipped — DB disabled")
        return None

    try:
        run_id = rt.database.save_run(
            provider=PROVIDER_TAG,
            result=decision.to_persist_dict(),
            market_state=market_state,
            interval_tf=str(market_state.get("interval", "")),
            period="live",
        )
        sys_logger.info(f"[persist] run saved → id={run_id}")
        return run_id
    except Exception as exc:
        sys_logger.error(f"[persist] save_run failed: {exc}")
        return None


# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────


_SHUTDOWN = False


def _install_signal_handlers() -> None:
    """ดักจับ SIGINT/SIGTERM เพื่อ graceful shutdown"""

    def _handler(signum, _frame):
        global _SHUTDOWN
        sys_logger.warning(f"[main] received signal {signum} → graceful shutdown")
        _SHUTDOWN = True

    try:
        _os_signal.signal(_os_signal.SIGINT, _handler)
        _os_signal.signal(_os_signal.SIGTERM, _handler)
    except (AttributeError, ValueError):  # Windows / non-main thread
        pass


def main_loop(rt: Runtime, *, interval_sec: int, skip_fetch: bool, run_once: bool) -> None:
    """ลูปหลัก — รันต่อเนื่องทุก interval_sec วินาที จนกว่าจะถูก signal shutdown"""
    cycle_no = 0
    while not _SHUTDOWN:
        cycle_no += 1
        sys_logger.info(f"\n{'=' * 60}\n[main] ── Cycle #{cycle_no} START ──\n{'=' * 60}")

        try:
            run_analysis_once(rt, skip_fetch=skip_fetch)
        except Exception as exc:  # pragma: no cover - top-level safety
            sys_logger.exception(f"[main] cycle {cycle_no} crashed: {exc}")

        if run_once:
            sys_logger.info("[main] --once flag set → exiting after 1 cycle")
            break

        if _SHUTDOWN:
            break

        sys_logger.info(f"[main] sleeping {interval_sec}s until next cycle")
        # sleep แบบ chunk เล็ก ๆ เพื่อให้ตอบ shutdown signal เร็ว
        for _ in range(interval_sec):
            if _SHUTDOWN:
                break
            time.sleep(1)


# ─────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nakkhutthong-v2",
        description="นักขุดทอง v2 — XGBoost-based gold trading signal loop",
    )
    p.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL_SEC,
        help=f"loop interval in seconds (default {DEFAULT_INTERVAL_SEC})",
    )
    p.add_argument(
        "--model", type=str, default=DEFAULT_MODEL_PATH,
        help=f"path to XGBoost model file (default {DEFAULT_MODEL_PATH})",
    )
    p.add_argument(
        "--skip-fetch", action="store_true",
        help="ใช้ snapshot ล่าสุด ไม่บันทึก payload ใหม่",
    )
    p.add_argument(
        "--no-save", action="store_true",
        help="ไม่บันทึกผลลง database (dry run)",
    )
    p.add_argument(
        "--no-notify", action="store_true",
        help="ปิดการส่ง Discord/Telegram",
    )
    p.add_argument(
        "--once", action="store_true",
        help="รันรอบเดียวแล้วจบ (สำหรับเทสต์)",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    _install_signal_handlers()

    sys_logger.info("=" * 60)
    sys_logger.info(f"นักขุดทอง v2 starting | initial capital ฿{INITIAL_CAPITAL_THB:,.0f}")
    sys_logger.info(f"interval={args.interval}s | model={args.model}")
    sys_logger.info(f"skip_fetch={args.skip_fetch} no_save={args.no_save} once={args.once}")
    sys_logger.info("=" * 60)

    try:
        rt = build_runtime(
            model_path=args.model,
            enable_db=not args.no_save,
            enable_notify=not args.no_notify,
        )
    except Exception as exc:
        sys_logger.exception(f"[main] build_runtime failed: {exc}")
        return 2

    try:
        main_loop(
            rt,
            interval_sec=max(1, int(args.interval)),
            skip_fetch=args.skip_fetch,
            run_once=args.once,
        )
    finally:
        if rt.database is not None:
            try:
                rt.database.close()
            except Exception:
                pass
        sys_logger.info("[main] shutdown complete")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
