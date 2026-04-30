"""
config.py — Production Configuration
=====================================

ใช้สำหรับ production / live trading เท่านั้น
(ไฟล์ config ของ train/backtest แยกออกไป)

การปรับจาก training config:
  - ลบ DataConfig, SplitConfig, LabelConfig, TrainOutputConfig, BacktestOutputConfig
    ออกทั้งหมด — ไม่จำเป็นสำหรับ production
  - ModelConfig ไม่ hardcode path อีกต่อไป → อ่านจาก registry.json
  - ทุก path รองรับ env var override สำหรับ Docker / deployment ที่หลากหลาย

Environment Variables
---------------------
  MODEL_BASE_DIR   : path ไปยัง folder models/  (default: ml_core/models)
  REGISTRY_PATH    : path ไปยัง registry.json   (default: ml_core/models/registry.json)
  LOG_BASE_DIR     : path ไปยัง log folder       (default: logs)
  ACTIVE_MODEL     : override active model key   (ถ้าไม่ตั้ง ใช้ค่าใน registry.json)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────────────────────
# Base paths — อ่านจาก env var ก่อน แล้ว fallback ไป default
# ─────────────────────────────────────────────────────────────

_MODEL_BASE_DIR = Path(os.getenv("MODEL_BASE_DIR", "ml_core/models"))
_REGISTRY_PATH  = Path(os.getenv("REGISTRY_PATH",  "ml_core/models/registry.json"))
_LOG_BASE_DIR   = Path(os.getenv("LOG_BASE_DIR",   "logs"))


# ─────────────────────────────────────────────────────────────
# Registry helper
# ─────────────────────────────────────────────────────────────

def _resolve_from_registry(
    registry_path: Path = _REGISTRY_PATH,
    base_dir: Path = _MODEL_BASE_DIR,
    override_active: str = "",
) -> tuple[Path, Path, Path, float, str]:
    """
    อ่าน registry.json แล้วคืน (buy_path, sell_path, features_path, threshold, active_key)

    Parameters
    ----------
    registry_path   : path ไปยัง registry.json
    base_dir        : base directory ของ model files
    override_active : ถ้าไม่ว่าง → ใช้แทน "active" ใน registry.json
    """
    try:
        reg: dict = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"[ModelConfig] registry.json not found at: {registry_path}\n"
            f"  ตั้ง env var REGISTRY_PATH ให้ชี้ไปที่ไฟล์ที่ถูกต้อง"
        ) from exc

    active = override_active or os.getenv("ACTIVE_MODEL", "") or reg.get("active", "")
    if not active:
        raise ValueError("[ModelConfig] ไม่พบ 'active' model ใน registry.json")

    models: dict = reg.get("models", {})
    if active not in models:
        available = list(models.keys())
        raise KeyError(
            f"[ModelConfig] model key '{active}' ไม่อยู่ใน registry.json\n"
            f"  keys ที่มี: {available}"
        )

    entry = models[active]
    buy_path      = base_dir / entry["buy"]
    sell_path     = base_dir / entry["sell"]
    features_path = base_dir / entry["features"]
    threshold     = float(entry.get("threshold", 0.5))

    return buy_path, sell_path, features_path, threshold, active


# ─────────────────────────────────────────────────────────────
# ModelConfig — resolved from registry.json at init time
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class ModelConfig:
    """
    Model configuration สำหรับ production

    Paths ทั้งหมดถูก resolve จาก registry.json ที่ __post_init__
    ไม่ต้อง hardcode path หรือ version string ในไฟล์นี้

    หากต้องการสลับโมเดล → แก้ "active" ใน registry.json
    หรือตั้ง env var  ACTIVE_MODEL=v3  ก่อนเริ่ม process
    """
    # ── Registry / base ──────────────────────────────────────
    registry_path: Path = field(default_factory=lambda: _REGISTRY_PATH)
    base_dir:      Path = field(default_factory=lambda: _MODEL_BASE_DIR)

    # ── Resolved at __post_init__ (อย่าตั้งมือ) ──────────────
    active_model:         str  = ""
    buy_model_path:       Path = field(default_factory=Path)
    sell_model_path:      Path = field(default_factory=Path)
    feature_columns_path: Path = field(default_factory=Path)
    threshold:            float = 0.5

    # ── Model type / infra ────────────────────────────────────
    model_type:   str = "xgboost"
    random_state: int = 42
    n_jobs:       int = -1

    # ── BUY model hyperparams (จาก Optuna) ───────────────────
    buy_n_estimators:      int   = 270
    buy_learning_rate:     float = 0.02568177356257289
    buy_max_depth:         int   = 7
    buy_subsample:         float = 0.8469126011150903
    buy_colsample_bytree:  float = 0.9962714834928094
    buy_scale_pos_weight:  float = 1.3777090544750767

    # ── SELL model hyperparams (จาก Optuna) ──────────────────
    sell_n_estimators:     int   = 579
    sell_learning_rate:    float = 0.01012015792641747
    sell_max_depth:        int   = 7
    sell_subsample:        float = 0.8973233413246483
    sell_colsample_bytree: float = 0.96746657749076
    sell_scale_pos_weight: float = 1.0836476460180258

    def __post_init__(self) -> None:
        buy, sell, feat, thr, active = _resolve_from_registry(
            registry_path=self.registry_path,
            base_dir=self.base_dir,
        )
        self.buy_model_path       = buy
        self.sell_model_path      = sell
        self.feature_columns_path = feat
        self.threshold            = thr
        self.active_model         = active


# ─────────────────────────────────────────────────────────────
# SignalConfig
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class SignalConfig:
    base_threshold: float = 0.70  # threshold ปกติ
    min_threshold:  float = 0.55  # ยอมต่ำสุดตอนใกล้หมด session
    conflict_gap:   float = 0.15  # ช่องว่างขั้นต่ำระหว่าง BUY/SELL proba

    buy_label:  str = "BUY"
    hold_label: str = "HOLD"
    sell_label: str = "SELL"


# ─────────────────────────────────────────────────────────────
# BrokerConfig
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class BrokerConfig:
    starting_capital_thb: float = 1500.0
    min_order_size_thb:   float = 1000.0
    spread_rate:          float = 0.0014   # ~0.14% round-trip
    slippage_rate:        float = 0.0001
    commission_rate:      float = 0.0
    fee_rate:             float = 0.0


# ─────────────────────────────────────────────────────────────
# RiskConfig
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class RiskConfig:
    risk_fraction_per_trade:  float = 1.0
    max_daily_loss_thb:       float = 500.0
    max_consecutive_losses:   int   = 1000

    # ตรงกับ MAX_RISK_PCT ที่ใช้ตอน label
    stop_loss_pct:   float = 0.0032

    # ตรงกับ TARGET_MOVE_PCT ที่ใช้ตอน label
    take_profit_pct: float = 0.0020

    blowup_equity_thb: float = 500.0
    blowup_loss_thb:   float = 1000.0


# ─────────────────────────────────────────────────────────────
# SessionConfig
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class SessionConfig:
    timezone:                    ZoneInfo = field(
                                     default_factory=lambda: ZoneInfo("Asia/Bangkok")
                                 )
    deny_new_entries_outside_session: bool = True
    close_all_at_session_end:         bool = True
    force_close_at_session_end:       bool = True
    allow_overnight_holding:          bool = False


# ─────────────────────────────────────────────────────────────
# MetricsConfig
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class MetricsConfig:
    risk_free_rate_annual:          float = 0.02
    annualization_days:             int   = 252
    annualization_bars_per_day:     int   = 288
    min_days_for_trade_annualization: float = 5.0
    xirr_day_count:                 float = 365.25


# ─────────────────────────────────────────────────────────────
# LoggingConfig — ใช้ env var LOG_BASE_DIR แทน hardcode
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class LoggingConfig:
    base_dir: Path = field(default_factory=lambda: _LOG_BASE_DIR)


# ─────────────────────────────────────────────────────────────
# ProjectConfig — production-only
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class ProjectConfig:
    """
    Config หลักสำหรับ production

    DataConfig / SplitConfig / LabelConfig / TrainOutputConfig /
    BacktestOutputConfig ถูกลบออกเพราะไม่จำเป็นใน production
    → ดูใน config_train.py แทน
    """
    model:   ModelConfig   = field(default_factory=ModelConfig)
    signals: SignalConfig  = field(default_factory=SignalConfig)
    broker:  BrokerConfig  = field(default_factory=BrokerConfig)
    risk:    RiskConfig    = field(default_factory=RiskConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# ─────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────

CONFIG = ProjectConfig()