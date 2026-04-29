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

การแก้ไขจาก v2.1:
    FIX #1 — _restore_trailing_stop() เรียก public method แทน private attr
    FIX #2 — _calc_gold_grams() มี unit guard + docstring ชัดเจน
    FIX #3 — Trailing Stop flush ลง DB ทันทีเมื่อ RiskManager อัปเดต
    FIX #4 — DefaultPortfolio เป็น TypedDict แทน plain dict
    FIX #5 — _notify_if_pass() มี retry + exponential backoff
"""

from __future__ import annotations

import argparse
import logging
import os
import signal as _os_signal
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

# ── TypedDict (stdlib ≥ 3.8) ──────────────────────────────────
from typing import TypedDict

# ── Path setup ────────────────────────────────────────────────
_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

# ── Domain imports ────────────────────────────────────────────
from core import CoreDecision, Decision  # noqa: E402
from data_engine.extract_features import get_xgboost_feature  # noqa: E402
from data_engine.orchestrator import GoldTradingOrchestrator  # noqa: E402
from logs.api_logger import send_trade_log  # noqa: E402
from logs.logger_setup import sys_logger  # noqa: E402
from ml_core.risk import RiskManager  # noqa: E402

# ── Optional dependencies (graceful import) ──────────────────
try:
    from ml_core.signal import XGBoostPredictor
except Exception as _e:
    XGBoostPredictor = None  # type: ignore
    sys_logger.warning(f"[main] ml_core.signal import failed → using mock: {_e}")

try:
    from database.database import RunDatabase
except Exception as _e:
    RunDatabase = None  # type: ignore
    sys_logger.warning(f"[main] database.database import failed → DB disabled: {_e}")

try:
    from notification.discord_notifier import DiscordNotifier
except Exception as _e:
    DiscordNotifier = None  # type: ignore
    sys_logger.warning(f"[main] DiscordNotifier import failed: {_e}")

try:
    from notification.telegram_notifier import TelegramNotifier
except Exception as _e:
    TelegramNotifier = None  # type: ignore
    sys_logger.warning(f"[main] TelegramNotifier import failed: {_e}")

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

INITIAL_CAPITAL_THB: float = 1500.0
DEFAULT_INTERVAL_SEC: int = 900
DEFAULT_MODEL_PATH: str = "models/xgb_v1.json"
PROVIDER_TAG: str = "xgboost-v2"

# 1 บาทน้ำหนักทอง 96.5% = 15.244 กรัม
# ใช้หน่วยนี้แปลง position_size_thb → gold_grams เสมอ
# price_thb ใน _calc_gold_grams() หมายถึง "ราคาต่อบาทน้ำหนัก" เท่านั้น
GRAMS_PER_BAHT_WEIGHT: float = 15.244

# Retry สำหรับ notification
_NOTIFY_MAX_RETRIES: int = 2
_NOTIFY_BACKOFF_BASE_SEC: float = 2.0  # sleep = base^attempt ก่อน retry


# ─────────────────────────────────────────────────────────────
# [FIX #4] DefaultPortfolio — TypedDict แทน mutable plain dict
# ─────────────────────────────────────────────────────────────


class PortfolioDict(TypedDict, total=False):
    cash_thb: float
    gold_grams: float
    cost_basis: float
    trades_today: int
    trailing_stop_level_thb: Optional[float]
    unrealized_pnl: float


def _make_default_portfolio() -> PortfolioDict:
    """
    คืน portfolio ที่มีค่า default ปลอดภัย (fresh dict ทุกครั้ง)
    ใช้ฟังก์ชันแทน module-level dict เพื่อป้องกัน shared mutable state
    """
    return PortfolioDict(
        cash_thb=INITIAL_CAPITAL_THB,
        gold_grams=0.0,
        cost_basis=0.0,
        trades_today=0,
        trailing_stop_level_thb=None,
        unrealized_pnl=0.0,
    )


# ─────────────────────────────────────────────────────────────
# Mock signal predictor
# ─────────────────────────────────────────────────────────────


@dataclass
class _MockPrediction:
    direction: str = "HOLD"
    confidence: float = 0.0
    prob_buy: float = 0.0
    prob_sell: float = 0.0
    session: str = "Unknown"
    is_high_accuracy_session: bool = False


class _MockPredictor:
    """Fallback predictor ถ้าโหลด XGBoost ไม่ได้ — คืน HOLD เสมอเพื่อความปลอดภัย"""

    loaded: bool = False

    def predict(self, _features: Dict[str, Any], session: str = "Unknown") -> _MockPrediction:
        return _MockPrediction(session=session)


# ─────────────────────────────────────────────────────────────
# Runtime container
# ─────────────────────────────────────────────────────────────


@dataclass
class Runtime:
    """รวม dependency ทั้งหมดที่ main loop ต้องใช้"""

    orchestrator: GoldTradingOrchestrator
    signal_engine: Any            # XGBoostPredictor | _MockPredictor
    core: CoreDecision
    database: Optional[Any]       # RunDatabase | None
    discord: Optional[Any]
    telegram: Optional[Any]
    save_to_db: bool = True

    @property
    def risk(self) -> RiskManager:
        return self.core.risk


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

    orchestrator = GoldTradingOrchestrator()
    sys_logger.info("[main] ✓ GoldTradingOrchestrator ready")

    signal_engine: Any = _build_signal_engine(model_path)

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

    database = _build_database(enable_db)
    discord, telegram = _build_notifiers(enable_notify)

    return Runtime(
        orchestrator=orchestrator,
        signal_engine=signal_engine,
        core=core,
        database=database,
        discord=discord,
        telegram=telegram,
        save_to_db=enable_db and database is not None,
    )


def _build_signal_engine(model_path: str) -> Any:
    if XGBoostPredictor is None:
        sys_logger.warning("[main] XGBoostPredictor unavailable → mock")
        return _MockPredictor()
    if not os.path.exists(model_path):
        sys_logger.warning(f"[main] Model file not found at {model_path} → mock")
        return _MockPredictor()
    try:
        engine = XGBoostPredictor(model_path=model_path)
        sys_logger.info(f"[main] ✓ XGBoostPredictor loaded from {model_path}")
        return engine
    except Exception as exc:
        sys_logger.error(f"[main] XGBoostPredictor init failed: {exc} → mock")
        return _MockPredictor()


def _build_database(enable_db: bool) -> Optional[Any]:
    if not enable_db or RunDatabase is None:
        return None
    try:
        db = RunDatabase()
        sys_logger.info("[main] ✓ RunDatabase connected")
        return db
    except Exception as exc:
        sys_logger.error(f"[main] RunDatabase init failed: {exc} → DB disabled")
        return None


def _build_notifiers(enable_notify: bool) -> tuple[Optional[Any], Optional[Any]]:
    discord = telegram = None
    if not enable_notify:
        return discord, telegram

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

    return discord, telegram


# ─────────────────────────────────────────────────────────────
# Portfolio helpers
# ─────────────────────────────────────────────────────────────


def _load_portfolio_from_db(database: Optional[Any]) -> PortfolioDict:
    """
    ดึงข้อมูล Portfolio จริงจาก DB
    คืน default ที่ปลอดภัย (HOLD เสมอ) ถ้า DB ไม่พร้อม
    """
    if database is None:
        sys_logger.warning("[portfolio] DB not available — using default portfolio")
        return _make_default_portfolio()

    try:
        portfolio = database.get_portfolio()
        if not portfolio:
            sys_logger.warning("[portfolio] DB returned empty portfolio — using default")
            return _make_default_portfolio()

        # เติม key ที่ขาด โดยเริ่มจาก default แล้วทับด้วยค่าจาก DB
        result: PortfolioDict = {**_make_default_portfolio(), **portfolio}
        sys_logger.info(
            f"[portfolio] Loaded: cash=฿{result['cash_thb']:,.0f} "
            f"gold={result['gold_grams']:.4f}g "
            f"trades_today={result['trades_today']}"
        )
        return result

    except Exception as exc:
        sys_logger.error(f"[portfolio] get_portfolio failed: {exc} — using default")
        return _make_default_portfolio()


def _load_recent_trades_from_db(database: Optional[Any], limit: int = 10) -> List[Dict[str, Any]]:
    """ดึงประวัติการเทรดล่าสุดจาก DB เพื่อนับโควต้า 6 ไม้/วัน"""
    if database is None:
        return []
    try:
        trades = database.get_recent_trades(limit=limit) or []
        sys_logger.info(f"[trades] Loaded {len(trades)} recent trades from DB")
        return trades
    except Exception as exc:
        sys_logger.error(f"[trades] get_recent_trades failed: {exc}")
        return []


def _restore_trailing_stop(risk_manager: RiskManager, portfolio: PortfolioDict) -> None:
    """
    โหลดค่า trailing_stop_level_thb จาก portfolio มาตั้งค่าให้ RiskManager
    ป้องกันการสูญเสียสถานะ Trailing Stop เมื่อ process รีสตาร์ท

    [FIX #1] เรียก public method restore_trailing_stop() แทนการแก้ private attr โดยตรง
    → RiskManager ต้องมี method นี้ (ดูตัวอย่างใน docstring ด้านล่าง)

    ตัวอย่าง method ที่ต้องเพิ่มใน RiskManager:
        def restore_trailing_stop(self, level_thb: float) -> None:
            \"\"\"โหลดสถานะ trailing stop จาก persistent storage\"\"\"
            if level_thb > 0:
                self._active_trailing_sl = level_thb
                logger.info(f"[RiskManager] trailing stop restored: ฿{level_thb:,.0f}")
    """
    raw = portfolio.get("trailing_stop_level_thb")
    if raw is None:
        return
    try:
        level = float(raw)
        if level <= 0:
            return

        # ── [FIX #1] ใช้ public method แทน private attr ─────
        if hasattr(risk_manager, "restore_trailing_stop"):
            risk_manager.restore_trailing_stop(level)
            sys_logger.info(f"[trailing_stop] Restored via public method: ฿{level:,.0f}")
        else:
            # Fallback: เตือนและใช้ private attr ชั่วคราวเพื่อไม่ให้ระบบพัง
            # TODO: เพิ่ม restore_trailing_stop() ใน RiskManager แล้วลบบรรทัดนี้ออก
            sys_logger.warning(
                "[trailing_stop] RiskManager.restore_trailing_stop() not found — "
                "falling back to direct attr access. Please add the public method."
            )
            risk_manager._active_trailing_sl = level  # type: ignore[attr-defined]
            sys_logger.info(f"[trailing_stop] Restored via fallback: ฿{level:,.0f}")

    except (TypeError, ValueError) as exc:
        sys_logger.warning(f"[trailing_stop] Could not restore trailing stop: {exc}")


def _flush_trailing_stop_to_db(database: Optional[Any], risk_manager: RiskManager) -> None:
    """
    [FIX #3] บันทึกค่า Trailing Stop ปัจจุบันลง DB ทันทีหลัง evaluate แต่ละ cycle
    ป้องกัน race condition ที่ RiskManager อัปเดต _active_trailing_sl ระหว่าง cycle
    แต่ DB ยังไม่ได้รับค่าใหม่ → cycle ถัดไปจะโหลดค่าเก่า

    เรียกหลัง CoreDecision.evaluate() ทุกครั้ง ไม่ว่าจะ BUY/SELL/HOLD
    """
    if database is None:
        return

    try:
        # ดึงค่าจาก public property ก่อน ถ้ายังไม่มีให้ fallback private attr
        if hasattr(risk_manager, "active_trailing_stop"):
            current_level: Optional[float] = risk_manager.active_trailing_stop
        else:
            current_level = getattr(risk_manager, "_active_trailing_sl", None)

        if current_level is None:
            return

        database.update_trailing_stop(trailing_stop_level_thb=float(current_level))
        sys_logger.debug(f"[trailing_stop] Flushed to DB: ฿{current_level:,.0f}")

    except AttributeError as exc:
        # update_trailing_stop() อาจยังไม่มีใน RunDatabase รุ่นเก่า
        sys_logger.warning(
            f"[trailing_stop] DB method update_trailing_stop() not found ({exc}). "
            "กรุณาเพิ่ม method นี้ใน RunDatabase เพื่อป้องกัน trailing stop drift"
        )
    except Exception as exc:
        sys_logger.error(f"[trailing_stop] flush failed: {exc}")


def _calculate_unrealized_pnl(
    portfolio: PortfolioDict,
    market_state: Dict[str, Any],
) -> float:
    """
    คำนวณ unrealized_pnl โดยเทียบราคาตลาดปัจจุบัน vs cost_basis ใน DB

    สูตร:
        market_value_thb = (sell_price_thb / GRAMS_PER_BAHT_WEIGHT) * gold_grams
            — sell_price_thb คือราคาขาย "ต่อบาทน้ำหนัก" จาก thai_gold_thb
        unrealized_pnl   = market_value_thb - cost_basis
    """
    gold_grams = float(portfolio.get("gold_grams") or 0.0)
    if gold_grams <= 0:
        return 0.0

    cost_basis = float(portfolio.get("cost_basis") or 0.0)

    try:
        thai_gold = market_state.get("market_data", {}).get("thai_gold_thb", {})
        sell_price_thb = float(thai_gold.get("sell_price_thb") or 0.0)
        if sell_price_thb <= 0:
            sys_logger.warning("[unrealized_pnl] sell_price_thb unavailable → 0")
            return 0.0

        # sell_price_thb = ราคาต่อบาทน้ำหนัก → แปลงเป็นราคาต่อกรัมก่อน
        price_per_gram = sell_price_thb / GRAMS_PER_BAHT_WEIGHT
        market_value_thb = price_per_gram * gold_grams
        unrealized = round(market_value_thb - cost_basis, 2)

        sys_logger.info(
            f"[unrealized_pnl] gold={gold_grams:.4f}g "
            f"cost=฿{cost_basis:,.2f} "
            f"market=฿{market_value_thb:,.2f} "
            f"pnl=฿{unrealized:+,.2f}"
        )
        return unrealized

    except Exception as exc:
        sys_logger.error(f"[unrealized_pnl] calculation failed: {exc}")
        return 0.0


# ─────────────────────────────────────────────────────────────
# Trade persistence
# ─────────────────────────────────────────────────────────────


def _persist_trade_to_db(
    rt: Runtime,
    decision: Decision,
    market_state: Dict[str, Any],
    portfolio: PortfolioDict,
) -> None:
    """
    บันทึกการซื้อขายจริงลง DB (portfolio + trade_log)

    เงื่อนไข: final IN ("BUY", "SELL") เท่านั้น
    ไม่ขึ้นกับ decision.notify เพื่อป้องกันการพลาดบันทึกเมื่อ notification ล้มเหลว
    """
    if not rt.save_to_db or rt.database is None:
        return
    if decision.final not in ("BUY", "SELL"):
        return

    try:
        entry_price = _resolve_entry_price(decision, market_state)
        position_size_thb = float(decision.position_size_thb or 0.0)

        # [FIX #2] ส่ง entry_price ในหน่วย "ราคาต่อบาทน้ำหนัก" เสมอ
        gold_grams_traded = _calc_gold_grams(
            position_size_thb=position_size_thb,
            price_per_baht_weight_thb=entry_price,
        )
        trailing_sl = _get_trailing_sl(rt.risk)

        trade_payload = {
            "action":            decision.final,
            "entry_price_thb":   entry_price,
            "position_size_thb": position_size_thb,
            "gold_grams":        gold_grams_traded,
            "stop_loss":         decision.stop_loss,
            "take_profit":       decision.take_profit,
            "confidence":        float(decision.confidence),
            "rationale":         decision.rationale or "",
            "provider":          PROVIDER_TAG,
            "trailing_stop":     trailing_sl,
        }

        trade_id = rt.database.save_trade_log(trade_payload)
        sys_logger.info(f"[trade_db] trade_log saved → id={trade_id}")

        rt.database.update_portfolio(
            action=decision.final,
            gold_grams=gold_grams_traded,
            price_thb=entry_price,
            position_size_thb=position_size_thb,
            trailing_stop_level_thb=trailing_sl,
        )
        sys_logger.info(
            f"[trade_db] portfolio updated: {decision.final} "
            f"{gold_grams_traded:.4f}g @ ฿{entry_price:,.0f}"
        )

    except AttributeError as exc:
        sys_logger.warning(
            f"[trade_db] DB method not found ({exc}) — "
            "กรุณาเพิ่ม save_trade_log() และ update_portfolio() ใน RunDatabase"
        )
    except Exception as exc:
        sys_logger.error(f"[trade_db] persist_trade failed: {exc}")


def _resolve_entry_price(decision: Decision, market_state: Dict[str, Any]) -> float:
    """
    ดึง entry price จาก decision หรือ fallback ไปยัง market_state
    คืนค่าในหน่วย "ราคาต่อบาทน้ำหนัก" (THB/บาทน้ำหนัก) เสมอ
    """
    if decision.entry_price is not None:
        return float(decision.entry_price)
    thai_gold = market_state.get("market_data", {}).get("thai_gold_thb", {})
    return float(
        thai_gold.get("sell_price_thb")
        or thai_gold.get("mid_price_thb")
        or 0.0
    )


def _calc_gold_grams(
    position_size_thb: float,
    price_per_baht_weight_thb: float,
) -> float:
    """
    คำนวณปริมาณทอง (กรัม) จาก position size และ entry price

    [FIX #2] ชัดเจนว่า price_per_baht_weight_thb คือ "ราคาต่อบาทน้ำหนัก"
    (เช่น 45,000 บาท/บาทน้ำหนัก) ไม่ใช่ราคาต่อกรัม

    สูตร:
        จำนวนบาทน้ำหนัก = position_size_thb / price_per_baht_weight_thb
        gold_grams       = จำนวนบาทน้ำหนัก * GRAMS_PER_BAHT_WEIGHT

    ตัวอย่าง:
        position = 1,500 THB, price = 45,000 THB/บาทน้ำหนัก
        → baht_weight = 1500/45000 = 0.0333
        → gold_grams  = 0.0333 * 15.244 ≈ 0.508 กรัม

    Args:
        position_size_thb:        มูลค่าที่ต้องการซื้อ/ขาย (บาท)
        price_per_baht_weight_thb: ราคาทองต่อบาทน้ำหนัก (บาท/บาทน้ำหนัก)
                                   ✗ ห้ามส่งราคาต่อกรัม มิเช่นนั้นค่าจะเกินจริง ~15x

    Returns:
        ปริมาณทองเป็นกรัม (>= 0)
    """
    if price_per_baht_weight_thb <= 0 or position_size_thb <= 0:
        return 0.0

    # Guard: ราคาทองไทยต้องอยู่ในช่วง 30,000–100,000 บาท/บาทน้ำหนัก
    # ถ้าต่ำกว่านี้แสดงว่าส่งราคาต่อกรัมมาผิดหน่วย
    _PRICE_FLOOR_THB = 30_000.0
    _PRICE_CEIL_THB = 100_000.0
    if not (_PRICE_FLOOR_THB <= price_per_baht_weight_thb <= _PRICE_CEIL_THB):
        sys_logger.error(
            f"[calc_gold_grams] price_per_baht_weight_thb={price_per_baht_weight_thb:,.2f} "
            f"อยู่นอกช่วงที่คาดหวัง [{_PRICE_FLOOR_THB:,.0f}–{_PRICE_CEIL_THB:,.0f}] "
            "— อาจส่งหน่วยราคาผิด (ต่อกรัม แทนที่จะเป็นต่อบาทน้ำหนัก) → คืน 0"
        )
        return 0.0

    baht_weight = position_size_thb / price_per_baht_weight_thb
    return round(baht_weight * GRAMS_PER_BAHT_WEIGHT, 4)


def _get_trailing_sl(risk_manager: RiskManager) -> Optional[float]:
    """ดึงค่า trailing stop ปัจจุบันผ่าน public property ก่อน แล้ว fallback private attr"""
    if hasattr(risk_manager, "active_trailing_stop"):
        return risk_manager.active_trailing_stop
    return getattr(risk_manager, "_active_trailing_sl", None)


# ─────────────────────────────────────────────────────────────
# One full analysis cycle
# ─────────────────────────────────────────────────────────────


def run_analysis_once(rt: Runtime, *, skip_fetch: bool = False) -> Decision:
    """
    รันรอบ pipeline 1 ครั้ง:

        [DB] portfolio + trades
          ↓
        market_state → feature_list → (signal, conf) → CoreDecision
          ↓
        flush trailing stop → notify + persist_run + persist_trade
    """
    with _timed_step("cycle total"):

        # ── 0. โหลด Portfolio + Trades + Trailing Stop จาก DB ──
        sys_logger.info("[cycle] (0/5) loading portfolio & recent trades from DB")
        portfolio = _load_portfolio_from_db(rt.database)
        recent_trades = _load_recent_trades_from_db(rt.database, limit=10)
        _restore_trailing_stop(rt.risk, portfolio)

        # ── 1. Data Engine ────────────────────────────────────
        sys_logger.info("[cycle] (1/5) fetching market_state via orchestrator")
        market_state = rt.orchestrator.run(
            save_to_file=not skip_fetch,
            recent_trades=recent_trades,
        )
        # Inject portfolio จริงจาก DB (ทับ default ของ orchestrator)
        market_state["portfolio"] = portfolio
        market_state["portfolio"]["unrealized_pnl"] = _calculate_unrealized_pnl(
            portfolio, market_state
        )

        # ── 2. Feature extraction ─────────────────────────────
        sys_logger.info("[cycle] (2/5) extracting 37-dim feature vector")
        feature_dict = _safe_extract_features(market_state)
        if feature_dict is None:
            return Decision(
                final="HOLD", model_signal="HOLD", confidence=0.0,
                reject_reason="feature_extraction_failed", notify=False,
            )

        # ── 3. XGBoost prediction ─────────────────────────────
        sys_logger.info("[cycle] (3/5) XGBoost predict + predict_proba")
        signal, confidence = _safe_predict(rt.signal_engine, feature_dict, market_state)
        sys_logger.info(f"[cycle] XGBoost → {signal} (conf={confidence:.3f})")

        # ── 4. Core decision (fan-out gates) ──────────────────
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

        # ── [FIX #3] Flush Trailing Stop ทันทีหลัง evaluate ──
        _flush_trailing_stop_to_db(rt.database, rt.risk)

        # ── 5. Notify (YES only) + Persist (always) ───────────
        sys_logger.info("[cycle] (5/5) notify + persist")
        _notify_if_pass(rt, decision, market_state)
        _persist_run(rt, decision, market_state)
        _persist_trade_to_db(rt, decision, market_state, portfolio)
        _send_trade_log(decision, market_state)

    return decision


def _safe_extract_features(market_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return get_xgboost_feature(market_state, as_dataframe=False)
    except Exception as exc:
        sys_logger.exception(f"[cycle] feature extraction failed: {exc}")
        return None


def _safe_predict(
    signal_engine: Any,
    feature_dict: Dict[str, Any],
    market_state: Dict[str, Any],
) -> tuple[str, float]:
    session_label = _resolve_session_label(market_state)
    try:
        out = signal_engine.predict(feature_dict, session=session_label)
        return str(getattr(out, "direction", "HOLD")).upper(), float(getattr(out, "confidence", 0.0))
    except Exception as exc:
        sys_logger.exception(f"[cycle] XGBoost predict failed: {exc}")
        return "HOLD", 0.0


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


@contextmanager
def _timed_step(label: str) -> Generator[None, None, None]:
    """Context manager วัดเวลาแต่ละขั้นตอน"""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        sys_logger.info(f"[{label}] elapsed: {elapsed_ms:,.1f} ms")


def _resolve_session_label(market_state: Dict[str, Any]) -> str:
    """แปลง session_gate.session_id → Morning / Afternoon / Evening"""
    sid = (
        (market_state.get("session_gate") or {})
        .get("session_id", "")
        .lower()
    )
    return {
        "night":   "Morning",
        "morning": "Morning",
        "noon":    "Afternoon",
        "evening": "Evening",
    }.get(sid, "Unknown")


def _notify_if_pass(
    rt: Runtime, decision: Decision, market_state: Dict[str, Any]
) -> None:
    """
    ส่ง Discord + Telegram เฉพาะกรณี ALL PASS

    [FIX #5] เพิ่ม retry + exponential backoff สูงสุด _NOTIFY_MAX_RETRIES ครั้ง
    ป้องกันการพลาดแจ้งเตือนจาก transient network error หรือ Telegram rate limit
    """
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
            "signal":      decision.final,
            "confidence":  float(decision.confidence),
            "entry_price": decision.entry_price,
            "stop_loss":   decision.stop_loss,
            "take_profit": decision.take_profit,
            "provider":    PROVIDER_TAG,
        }
    }
    common_kwargs = dict(
        voting_result=voting_result,
        interval_results=interval_results,
        market_state=market_state,
        provider=PROVIDER_TAG,
        period="live",
        run_id=None,
    )

    for name, notifier in (("discord", rt.discord), ("telegram", rt.telegram)):
        if notifier is None:
            continue
        _notify_with_retry(name=name, notifier=notifier, kwargs=common_kwargs)


def _notify_with_retry(
    *,
    name: str,
    notifier: Any,
    kwargs: Dict[str, Any],
) -> None:
    """
    [FIX #5] ส่ง notification พร้อม retry + exponential backoff

    Retry strategy:
        attempt 0 → ส่งทันที
        attempt 1 → sleep 2s แล้วลองใหม่
        attempt 2 → sleep 4s แล้วลองใหม่  (base^attempt)
        หยุดเมื่อสำเร็จหรือหมด _NOTIFY_MAX_RETRIES
    """
    last_exc: Optional[Exception] = None

    for attempt in range(_NOTIFY_MAX_RETRIES + 1):
        if attempt > 0:
            backoff = _NOTIFY_BACKOFF_BASE_SEC ** attempt
            sys_logger.warning(
                f"[notify] {name} retry {attempt}/{_NOTIFY_MAX_RETRIES} "
                f"(backoff={backoff:.0f}s)"
            )
            time.sleep(backoff)
        try:
            ok = notifier.notify(**kwargs)
            sys_logger.info(f"[notify] {name} sent={ok} (attempt={attempt})")
            return  # สำเร็จ — ออกทันที
        except Exception as exc:
            last_exc = exc
            sys_logger.warning(f"[notify] {name} attempt {attempt} failed: {exc}")

    sys_logger.error(
        f"[notify] {name} failed after {_NOTIFY_MAX_RETRIES + 1} attempts: {last_exc}"
    )


def _persist_run(
    rt: Runtime, decision: Decision, market_state: Dict[str, Any]
) -> Optional[int]:
    """บันทึกลง DB เสมอ (ทั้ง BUY/SELL และ HOLD) — database-first"""
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


def _send_trade_log(decision: Decision, market_state: Dict[str, Any]) -> None:
    """ส่ง trade log ผ่าน api_logger เฉพาะเมื่อ decision.notify == True"""
    if not decision.notify:
        sys_logger.debug("[trade_log] skipped — decision.notify=False")
        return

    team_api_key = os.getenv("TEAM_API_KEY")
    if not team_api_key:
        sys_logger.error("[trade_log] TEAM_API_KEY missing, cannot send trade log")
        return

    try:
        send_trade_log(
            action=decision.final,
            price=decision.entry_price if decision.entry_price is not None else "MARKET",
            reason=decision.rationale or f"Auto-generated signal: {decision.final}",
            api_key=team_api_key,
            confidence=float(decision.confidence),
            stop_loss=float(decision.stop_loss or 0.0),
            take_profit=float(decision.take_profit or 0.0),
            provider=PROVIDER_TAG,
            session_id=market_state.get("session_gate", {}).get("session_id"),
        )
        sys_logger.info("[trade_log] sent")
    except Exception as exc:
        sys_logger.error(f"[trade_log] failed: {exc}")


# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────

_SHUTDOWN = False


def _install_signal_handlers() -> None:
    """ดักจับ SIGINT/SIGTERM เพื่อ graceful shutdown"""

    def _handler(signum: int, _frame: Any) -> None:
        global _SHUTDOWN
        sys_logger.warning(f"[main] received signal {signum} → graceful shutdown")
        _SHUTDOWN = True

    try:
        _os_signal.signal(_os_signal.SIGINT, _handler)
        _os_signal.signal(_os_signal.SIGTERM, _handler)
    except (AttributeError, ValueError):
        pass  # Windows / non-main thread


def main_loop(
    rt: Runtime,
    *,
    interval_sec: int,
    skip_fetch: bool,
    run_once: bool,
) -> None:
    """ลูปหลัก — รันต่อเนื่องทุก interval_sec วินาที"""
    cycle_no = 0

    while not _SHUTDOWN:
        cycle_no += 1
        sys_logger.info(f"\n{'=' * 60}\n[main] ── Cycle #{cycle_no} START ──\n{'=' * 60}")

        try:
            run_analysis_once(rt, skip_fetch=skip_fetch)
        except Exception as exc:
            sys_logger.exception(f"[main] cycle {cycle_no} crashed: {exc}")

        if run_once:
            sys_logger.info("[main] --once flag set → exiting after 1 cycle")
            break
        if _SHUTDOWN:
            break

        sys_logger.info(f"[main] sleeping {interval_sec}s until next cycle")
        # sleep แบบ chunk เพื่อตอบ shutdown signal เร็ว
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
            interval_sec=max(1, args.interval),
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