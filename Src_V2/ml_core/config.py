"""
config.py — Production Configuration
====================================

Central source of runtime configuration for the `Src_V2` production pipeline.
Environment variables may override paths so deployments can tune behavior
without editing code.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Tuple


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    path = Path(raw)
    if not path.is_absolute():
        path = default.parent / path
    return path.resolve()


_SRC_V2_DIR = Path(__file__).resolve().parent.parent
_MODEL_BASE_DIR = _env_path("MODEL_BASE_DIR", _SRC_V2_DIR / "models")
_REGISTRY_PATH = _env_path("REGISTRY_PATH", _MODEL_BASE_DIR / "registry.json")


def _resolve_from_registry(
    registry_path: Path = _REGISTRY_PATH,
    base_dir: Path = _MODEL_BASE_DIR,
    override_active: str = "",
) -> tuple[Path, Path, Path, float, str]:
    try:
        reg: dict = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"[ModelConfig] registry.json not found at: {registry_path}\n"
            f"  Set REGISTRY_PATH to the correct file for this deployment."
        ) from exc

    active = override_active or os.getenv("ACTIVE_MODEL", "") or reg.get("active", "")
    if not active:
        raise ValueError("[ModelConfig] Missing 'active' model in registry.json")

    models: dict = reg.get("models", {})
    if active not in models:
        available = list(models.keys())
        raise KeyError(
            f"[ModelConfig] model key '{active}' not found in registry.json\n"
            f"  available keys: {available}"
        )

    entry = models[active]
    buy_path = (base_dir / entry["buy"]).resolve()
    sell_path = (base_dir / entry["sell"]).resolve()
    features_path = (base_dir / entry["features"]).resolve()
    threshold = float(entry.get("threshold", 0.5))
    return buy_path, sell_path, features_path, threshold, active


@dataclass(slots=True)
class ModelConfig:
    registry_path: Path = field(default_factory=lambda: _REGISTRY_PATH)
    base_dir: Path = field(default_factory=lambda: _MODEL_BASE_DIR)

    active_model: str = ""
    buy_model_path: Path = field(default_factory=Path)
    sell_model_path: Path = field(default_factory=Path)
    feature_columns_path: Path = field(default_factory=Path)
    threshold: float = 0.5

    model_type: str = "xgboost"
    random_state: int = 42
    n_jobs: int = -1

    buy_n_estimators: int = 270
    buy_learning_rate: float = 0.02568177356257289
    buy_max_depth: int = 7
    buy_subsample: float = 0.8469126011150903
    buy_colsample_bytree: float = 0.9962714834928094
    buy_scale_pos_weight: float = 1.3777090544750767

    sell_n_estimators: int = 579
    sell_learning_rate: float = 0.01012015792641747
    sell_max_depth: int = 7
    sell_subsample: float = 0.8973233413246483
    sell_colsample_bytree: float = 0.96746657749076
    sell_scale_pos_weight: float = 1.0836476460180258

    def __post_init__(self) -> None:
        buy, sell, feat, thr, active = _resolve_from_registry(
            registry_path=self.registry_path,
            base_dir=self.base_dir,
        )
        self.buy_model_path = buy
        self.sell_model_path = sell
        self.feature_columns_path = feat
        self.threshold = thr
        self.active_model = active


@dataclass(slots=True)
class SignalConfig:
    base_threshold: float = 0.60
    min_threshold: float = 0.55
    conflict_gap: float = 0.15
    early_session_progress_cutoff: float = 0.5
    late_session_progress_cutoff: float = 0.9
    early_session_threshold_boost: float = 0.10
    repeat_trade_threshold_boost: float = 0.15

    buy_label: str = "BUY"
    hold_label: str = "HOLD"
    sell_label: str = "SELL"
    high_accuracy_sessions: Tuple[str, ...] = ("Evening",)
    aggregator_conflict_gap: float = 0.20
    aggregator_weights: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {
            "Evening": {"xgboost": 0.30, "news": 0.50, "technical": 0.20},
            "Morning": {"xgboost": 0.55, "news": 0.15, "technical": 0.30},
            "Afternoon": {"xgboost": 0.45, "news": 0.25, "technical": 0.30},
            "default": {"xgboost": 0.50, "news": 0.15, "technical": 0.35},
        }
    )


@dataclass(slots=True)
class RiskConfig:
    risk_fraction_per_trade: float = 0.20
    max_daily_loss_thb: float = 500.0
    max_consecutive_losses: int = 1000
    stop_loss_pct: float = 0.0032
    take_profit_pct: float = 0.0020
    blowup_equity_thb: float = 500.0
    blowup_loss_thb: float = 1000.0

    atr_multiplier: float = 1.3
    risk_reward_ratio: float = 1.2
    min_confidence: float = 0.55
    min_sell_confidence: float = 0.55
    micro_port_threshold_thb: float = 2000.0
    session_end_force_sell_minutes: int = 30
    enable_trailing_stop: bool = True
    trailing_activation_atr_multiple: float = 1.0
    acceptable_loss_thb: float = 2.0
    spread_per_baht_weight: float = 200.0
    force_sell_threshold_minutes: int = 10
    force_buy_threshold_minutes: int = 25
    fallback_atr_pct_of_price: float = 0.003
    min_move_pct: float = 0.0007
    htf_bearish_min_confidence: float = 0.75
    capital_critical_min_confidence: float = 0.76
    capital_defensive_min_confidence: float = 0.68
    holding_profiting_buy_min_confidence: float = 0.74
    holding_losing_buy_min_confidence: float = 0.80

@dataclass(slots=True)
class ProjectConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


CONFIG = ProjectConfig()


def get_config() -> ProjectConfig:
    return CONFIG
