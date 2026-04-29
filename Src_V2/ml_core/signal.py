"""
ml_core/signal.py — Dual-Model XGBoost Signal Predictor (v2.1)
==============================================================

โหลดโมเดล XGBoost binary classifier 2 ตัวจาก pickle:
    - models/model_buy.pkl   →  predict_proba()[0][1] = ความน่าจะเป็น "BUY"
    - models/model_sell.pkl  →  predict_proba()[0][1] = ความน่าจะเป็น "SELL"

Feature schema:
    - 26 features ตามไฟล์ models/feature_columns.json (exact name + order)
    - ทุก feature ต้องเป็น numeric (NaN/Inf → 0.0)

Decision rule (unified threshold = 0.60):
    if buy_proba > 0.60 และ buy_proba >= sell_proba   →  BUY  (conf = buy_proba)
    elif sell_proba > 0.60 และ sell_proba > buy_proba →  SELL (conf = sell_proba)
    else                                              →  HOLD (conf = max(buy, sell))
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

try:
    import shap
except ImportError:
    shap = None

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

THRESHOLD: float = 0.6                         # unified threshold for BUY/SELL
HIGH_ACCURACY_SESSIONS = {"Evening"}             # legacy hint จาก v1 (ไม่ blocking)

# Default file paths (resolved relative to repo root or this file)
_MODULE_DIR = Path(__file__).resolve().parent
_DEFAULT_MODELS_DIR = _MODULE_DIR.parent / "models"
DEFAULT_MODEL_BUY_PATH  = str(_DEFAULT_MODELS_DIR / "model_buy.pkl")
DEFAULT_MODEL_SELL_PATH = str(_DEFAULT_MODELS_DIR / "model_sell.pkl")
DEFAULT_FEATURE_SCHEMA  = str(_DEFAULT_MODELS_DIR / "feature_columns.json")


# ─────────────────────────────────────────────────────────────
# Output dataclass — ใช้ทั้ง XGBoostPredictor และ _MockPredictor
# ─────────────────────────────────────────────────────────────


@dataclass
class XGBOutput:
    """ผลลัพธ์รวมของ predict() — main.py ใช้ .direction และ .confidence"""

    prob_buy: float
    prob_sell: float
    direction: str                          # "BUY" | "SELL" | "HOLD"
    confidence: float
    session: str = "Unknown"
    is_high_accuracy_session: bool = False
    avg_mfe: float = 0.0
    avg_mae: float = 0.0
    top_features: str = ""


# ─────────────────────────────────────────────────────────────
# Backward-compat alias — บาง integration เก่าใช้ ExternalSignal
# ─────────────────────────────────────────────────────────────


@dataclass
class ExternalSignal:
    """สัญญาณจากภายนอก (News / Technical) — ใช้กับ SignalAggregator เดิม"""

    direction: str
    confidence: float


# ─────────────────────────────────────────────────────────────
# Dual-Model XGBoost Predictor
# ─────────────────────────────────────────────────────────────


class XGBoostPredictor:
    """
    Dual binary-classifier XGBoost predictor.

    Parameters
    ----------
    model_buy_path : str
        Path ของ pickle (.pkl) สำหรับโมเดล BUY (sklearn-compatible classifier)
    model_sell_path : str
        Path ของ pickle (.pkl) สำหรับโมเดล SELL
    feature_schema_path : str | None
        Path ของไฟล์ JSON ที่มี list ชื่อ feature 26 ตัว (default = models/feature_columns.json)
    threshold : float
        Threshold ของ predict_proba positive class (default 0.60)

    Attributes
    ----------
    feature_columns : list[str]
        ชื่อ feature ในลำดับที่ถูกต้องตาม schema (length = 26)
    """

    def __init__(
        self,
        model_buy_path: str = DEFAULT_MODEL_BUY_PATH,
        model_sell_path: str = DEFAULT_MODEL_SELL_PATH,
        *,
        feature_schema_path: Optional[str] = None,
        threshold: float = THRESHOLD,
    ) -> None:
        self.threshold: float = float(threshold)
        self.feature_columns: List[str] = self._load_feature_schema(feature_schema_path)
        self._buy_model = self._load_pickle(model_buy_path, label="BUY")
        self._sell_model = self._load_pickle(model_sell_path, label="SELL")
        self.loaded: bool = True

        # Initialize SHAP Explainers
        self.use_shap = False
        self._buy_explainer = None
        self._sell_explainer = None
        if shap is not None:
            try:
                self._buy_explainer = shap.TreeExplainer(self._buy_model)
                self._sell_explainer = shap.TreeExplainer(self._sell_model)
                self.use_shap = True
                logger.info("[XGB] ✓ SHAP TreeExplainers initialized successfully")
            except Exception as e:
                logger.warning(f"[XGB] SHAP initialization failed: {e}. 'reason' will not include top features.")

        logger.info(
            "[XGB] ✓ Dual-model predictor ready | features=%d threshold=%.2f",
            len(self.feature_columns), self.threshold,
        )

    # ── Loaders ──────────────────────────────────────────────

    @staticmethod
    def _load_feature_schema(path: Optional[str]) -> List[str]:
        schema_path = path or DEFAULT_FEATURE_SCHEMA
        if not os.path.exists(schema_path):
            raise RuntimeError(f"[XGB] feature_columns.json not found: {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            cols = json.load(f)
        if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
            raise RuntimeError(f"[XGB] invalid schema format in {schema_path}")
        logger.info("[XGB] Loaded %d feature columns from %s", len(cols), schema_path)
        return cols

    @staticmethod
    def _load_pickle(path: str, *, label: str):
        if not os.path.exists(path):
            raise RuntimeError(f"[XGB] {label} model file not found: {path}")
        try:
            import joblib  # imported lazily so test envs without joblib still parse
            model = joblib.load(path)
        except Exception as exc:
            raise RuntimeError(f"[XGB] failed to load {label} model from {path}: {exc}")

        if not (hasattr(model, "predict_proba") or hasattr(model, "predict")):
            raise RuntimeError(
                f"[XGB] {label} model lacks predict_proba/predict — got {type(model).__name__}"
            )

        logger.info("[XGB] ✓ %s model loaded from %s (%s)", label, path, type(model).__name__)
        return model

    # ── Inference ────────────────────────────────────────────

    def predict(self, features: dict, session: str = "Unknown") -> XGBOutput:
        """
        Run dual prediction on a single observation.

        Parameters
        ----------
        features : dict
            dict ที่มี key ตรงตาม `self.feature_columns` (key ที่ขาดจะถูกเติม 0.0)
        session : str
            ชื่อ session — เก็บลงใน output เพื่อ trace; ไม่กระทบ inference
        """
        try:
            row = self._build_row(features)
            buy_proba = self._proba(self._buy_model, row)
            sell_proba = self._proba(self._sell_model, row)
        except Exception as exc:
            logger.error("[XGB] predict failed: %s", exc)
            return XGBOutput(
                prob_buy=0.0, prob_sell=0.0,
                direction="HOLD", confidence=0.0,
                session=session,
                is_high_accuracy_session=session in HIGH_ACCURACY_SESSIONS,
            )

        direction, confidence = self._apply_rule(buy_proba, sell_proba)

        top_features_str = ""
        if self.use_shap and direction in ("BUY", "SELL"):
            try:
                explainer = self._buy_explainer if direction == "BUY" else self._sell_explainer
                shap_values = explainer.shap_values(row)
                
                # shap_values shape handling: binary classification might return a list of arrays or a single array
                if isinstance(shap_values, list):
                    vals = np.abs(shap_values[1][0]) # positive class
                else:
                    vals = np.abs(shap_values[0])
                
                # Get indices of top 3 absolute SHAP values
                top_indices = np.argsort(vals)[-3:][::-1]
                top_feats = []
                for idx in top_indices:
                    feat_name = self.feature_columns[idx]
                    feat_val = row.iloc[0, idx]
                    top_feats.append(f"{feat_name} ({feat_val:.2f})")
                
                if len(top_feats) > 1:
                    top_features_str = " และ ".join([", ".join(top_feats[:-1]), top_feats[-1]])
                elif len(top_feats) == 1:
                    top_features_str = top_feats[0]
                else:
                    top_features_str = ""
            except Exception as e:
                logger.error(f"[XGB] SHAP calculation failed: {e}")

        return XGBOutput(
            prob_buy=round(buy_proba, 4),
            prob_sell=round(sell_proba, 4),
            direction=direction,
            confidence=round(confidence, 4),
            session=session,
            is_high_accuracy_session=session in HIGH_ACCURACY_SESSIONS,
            top_features=top_features_str,
        )

    # ── Internal helpers ─────────────────────────────────────

    def _build_row(self, features: dict):
        """สร้าง DataFrame 1 แถวตาม order ของ `self.feature_columns` (เติม 0.0 ถ้าไม่มี)"""
        import pandas as pd

        ordered = {}
        missing: List[str] = []
        for col in self.feature_columns:
            v = features.get(col)
            if v is None:
                missing.append(col)
                ordered[col] = 0.0
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                missing.append(col)
                fv = 0.0
            if np.isnan(fv) or np.isinf(fv):
                fv = 0.0
            ordered[col] = fv

        if missing:
            logger.warning("[XGB] %d/%d feature(s) missing/invalid → 0.0: %s",
                           len(missing), len(self.feature_columns), missing[:5])

        # columns= บังคับลำดับให้ตรง schema เสมอ
        return pd.DataFrame([ordered], columns=self.feature_columns)

    @staticmethod
    def _proba(model, row) -> float:
        """ดึง probability ของ positive class (class index = 1) จากโมเดล binary"""
        if hasattr(model, "predict_proba"):
            arr = model.predict_proba(row)
            arr = np.asarray(arr)
            # รูปแบบมาตรฐาน: shape (1, 2) → [neg, pos]
            if arr.ndim == 2 and arr.shape[1] >= 2:
                return float(arr[0][1])
            if arr.ndim == 2 and arr.shape[1] == 1:
                return float(arr[0][0])
            return float(arr.flat[-1])
        # Fallback: ใช้ predict() ตรง ๆ (booster) ที่คืน probability score
        score = model.predict(row)
        return float(np.asarray(score).flat[0])

    def _apply_rule(self, buy_proba: float, sell_proba: float) -> tuple[str, float]:
        """กฎตัดสินใจ — unified threshold (default 0.60)"""
        if buy_proba > self.threshold and buy_proba >= sell_proba:
            return "BUY", buy_proba
        if sell_proba > self.threshold and sell_proba > buy_proba:
            return "SELL", sell_proba
        return "HOLD", max(buy_proba, sell_proba)


# ─────────────────────────────────────────────────────────────
# SignalAggregator — เดิม (legacy from v1) — คงไว้เพื่อ backward-compat
# main.py v2.1 ไม่ใช้แล้ว แต่ยังมีโค้ดอื่นอาจอ้างถึง
# ─────────────────────────────────────────────────────────────


_DIR_SCORE = {"BUY": 1, "HOLD": 0, "SELL": -1}
CONFLICT_GAP = 0.20


class SignalAggregator:
    """
    Legacy weighted-score aggregator (XGBoost + News + Technical).

    NOTE: ไม่ใช้ใน pipeline หลัก v2.1 — เก็บไว้เพื่อให้ test/integration เก่ายังเรียกได้
    """

    def __init__(self, session: str, market_open: bool):
        self.session = session
        self.market_open = market_open
        self.weights = self._get_weights()

    def aggregate(
        self,
        xgb: XGBOutput,
        news: Optional[ExternalSignal] = None,
        tech: Optional[ExternalSignal] = None,
    ) -> dict:
        w = self.weights
        score = _DIR_SCORE[xgb.direction] * xgb.confidence * w["xgboost"]
        if news:
            score += _DIR_SCORE[news.direction] * news.confidence * w["news"]
        if tech:
            score += _DIR_SCORE[tech.direction] * tech.confidence * w["technical"]

        if score > 0.20:
            agg_dir = "BUY"
        elif score < -0.20:
            agg_dir = "SELL"
        else:
            agg_dir = "HOLD"

        return {
            "direction": agg_dir,
            "score": round(score, 3),
            "confidence": round(abs(score), 3),
            "weights": w,
            "components": {
                "xgboost": f"{xgb.direction} ({xgb.confidence:.0%}) "
                           f"prob_buy={xgb.prob_buy} prob_sell={xgb.prob_sell}",
                "news": f"{news.direction} ({news.confidence:.0%})" if news else "N/A",
                "technical": f"{tech.direction} ({tech.confidence:.0%})" if tech else "N/A",
            },
            "session": self.session,
            "market_open": self.market_open,
            "xgb_session_quality": "HIGH" if xgb.is_high_accuracy_session else "LOW",
        }

    def _get_weights(self) -> dict:
        s, o = self.session, self.market_open
        if o and s == "Evening":
            return {"xgboost": 0.30, "news": 0.50, "technical": 0.20}
        if s == "Morning":
            return {"xgboost": 0.55, "news": 0.15, "technical": 0.30}
        if s == "Afternoon":
            return {"xgboost": 0.45, "news": 0.25, "technical": 0.30}
        return {"xgboost": 0.50, "news": 0.15, "technical": 0.35}
