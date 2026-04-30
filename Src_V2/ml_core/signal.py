"""
ml_core/signal.py — Dual-Model XGBoost Signal Predictor (v2.2)
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

[v2.2] EndOfSessionForcer:
    ติดตาม BUY/SELL history ใน session และตรวจสอบใน 30 นาทีสุดท้าย
    ถ้า HOLD ต่อเนื่อง >= 20 นาที → บังคับออก signal ตาม round ที่เหลือ

    round table:
        rounds  | ความหมาย                   | forced sequence
        --------|----------------------------|------------------------------------
        0.0     | ไม่มี signal เลย            | BUY → (+1m) SELL → (+1m) BUY → (+1m) SELL
        0.5     | มีแค่ SELL ค้างอยู่          | BUY → (+1m) SELL → (+1m) BUY
        1.0     | BUY→SELL ครบ 1 รอบ         | BUY → (+1m) SELL
        1.5     | BUY→SELL→BUY ค้างอยู่      | SELL ทันที
        ≥2.0    | ครบแล้ว                     | ไม่ทำอะไร

    forced signal จะถูก inject เข้า XGBOutput ด้วย is_forced=True
    core.py จะอ่าน flag นี้และแนบ forced_reason ลงใน Decision
    โดย logic การสร้างเหตุผล (reason) อยู่ใน core.py ทั้งหมด
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, List, Optional, Tuple

import numpy as np

try:
    import shap
except ImportError:
    shap = None

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

THRESHOLD: float = 0.6                          # unified threshold for BUY/SELL
HIGH_ACCURACY_SESSIONS = {"Evening"}            # legacy hint จาก v1 (ไม่ blocking)

# Default file paths (resolved relative to repo root or this file)
_MODULE_DIR = Path(__file__).resolve().parent
_DEFAULT_MODELS_DIR = _MODULE_DIR.parent / "models"
DEFAULT_MODEL_BUY_PATH  = str(_DEFAULT_MODELS_DIR / "model_buy.pkl")
DEFAULT_MODEL_SELL_PATH = str(_DEFAULT_MODELS_DIR / "model_sell.pkl")
DEFAULT_FEATURE_SCHEMA  = str(_DEFAULT_MODELS_DIR / "feature_columns.json")

# [v2.2] EndOfSessionForcer constants
_ROUND_NONE     = 0.0   # ไม่มี signal เลย
_ROUND_HALF     = 0.5   # มีแค่ SELL ค้างอยู่ (net short)
_ROUND_ONE      = 1.0   # BUY→SELL ครบ 1 รอบ (flat)
_ROUND_ONE_HALF = 1.5   # BUY→SELL→BUY ค้างอยู่ (net long)
_ROUND_TWO_PLUS = 2.0   # ≥ 2 รอบ → ไม่ต้องทำอะไร

EOS_FORCE_CONFIDENCE: float = 0.75             # confidence สำหรับ forced signal


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

    # [v2.2] forced signal metadata — core.py อ่าน flag นี้เพื่อสร้าง forced_reason
    is_forced: bool = False                 # True ถ้าถูก inject โดย EndOfSessionForcer
    forced_rounds: float = 0.0             # round ณ เวลาที่ trigger (ใช้ใน core.py สร้าง reason)
    session_mins_left: int = 0             # นาทีที่เหลือใน session (ใช้ใน core.py สร้าง reason)
    session_name: str = ""                 # ชื่อ session (ใช้ใน core.py สร้าง reason)


# ─────────────────────────────────────────────────────────────
# Backward-compat alias — บาง integration เก่าใช้ ExternalSignal
# ─────────────────────────────────────────────────────────────


@dataclass
class ExternalSignal:
    """สัญญาณจากภายนอก (News / Technical) — ใช้กับ SignalAggregator เดิม"""

    direction: str
    confidence: float


# ─────────────────────────────────────────────────────────────
# [v2.2] End-of-Session Forcer
# ─────────────────────────────────────────────────────────────


class EndOfSessionForcer:
    """
    ตรวจสอบและบังคับออก forced signal ในช่วง 30 นาทีสุดท้ายของ session

    หน้าที่ (ใน signal.py):
        - ติดตาม BUY/SELL history ใน session
        - นับ round และตัดสินใจว่า sequence ไหนต้องออก
        - inject forced signal เข้า XGBOutput (direction + is_forced + metadata)

    หน้าที่ที่ไม่ทำ (อยู่ใน core.py):
        - สร้างข้อความ reason / rationale
        - ตัดสินใจว่า bypass gate หรือไม่

    Parameters
    ----------
    session_end_time     : datetime  — เวลาสิ้นสุด session
    session_name         : str       — ชื่อ session ("Morning" / "Afternoon" / "Evening")
    window_minutes       : int       — ช่วงก่อน end ที่จะเริ่ม monitor (default 30)
    hold_threshold_minutes: int      — HOLD ต่อเนื่องที่จะ trigger (default 20)
    """

    def __init__(
        self,
        session_end_time: datetime,
        session_name: str = "Unknown",
        *,
        window_minutes: int = 30,
        hold_threshold_minutes: int = 20,
    ) -> None:
        self.session_end_time    = session_end_time
        self.session_name        = session_name
        self.window_minutes      = window_minutes
        self.hold_threshold_min  = hold_threshold_minutes

        self._lock: threading.Lock               = threading.Lock()
        self._signal_history: List[Tuple[datetime, str]] = []   # [(ts, "BUY"|"SELL")]
        self._last_active_ts: Optional[datetime] = None         # BUY/SELL ล่าสุด
        self._forced_queue: Deque[str]           = deque()      # คิว signal ที่รอ inject
        self._force_triggered: bool              = False        # กัน trigger ซ้ำ

        logger.info(
            "[EOS] Initialized | session=%s end=%s window=%dm hold=%dm",
            session_name, session_end_time.strftime("%H:%M"),
            window_minutes, hold_threshold_minutes,
        )

    # ── Public API ────────────────────────────────────────────

    def record_signal(self, signal: str, ts: Optional[datetime] = None) -> None:
        """
        บันทึก BUY/SELL ที่ออกจริงใน session
        เรียกโดย XGBoostPredictor.predict() ทุกครั้งที่ direction เป็น BUY/SELL
        (ทั้งจาก model ปกติ และ forced)
        """
        now = ts or datetime.now()
        sig = (signal or "").upper().strip()
        if sig not in ("BUY", "SELL"):
            return
        with self._lock:
            self._signal_history.append((now, sig))
            self._last_active_ts = now
            logger.debug("[EOS] recorded %s (history=%d)", sig, len(self._signal_history))

    def get_next_forced(self, now: Optional[datetime] = None) -> Optional[Tuple[str, float, int]]:
        """
        ดึง forced signal ถัดไป (ถ้าถึงเวลาแล้ว)

        Returns
        -------
        (signal, rounds, mins_left) หรือ None ถ้าไม่มี forced signal

        signal    : "BUY" | "SELL"
        rounds    : round ณ เวลา trigger (ส่งให้ core.py สร้าง reason)
        mins_left : นาทีที่เหลือใน session (ส่งให้ core.py สร้าง reason)
        """
        now = now or datetime.now()
        with self._lock:
            # ถ้าคิวมีอยู่แล้ว → dequeue ตรง ๆ
            if self._forced_queue:
                sig       = self._forced_queue.popleft()
                rounds    = self._calc_rounds()
                mins_left = max(0, int((self.session_end_time - now).total_seconds() / 60))
                logger.info("[EOS] dequeue forced %s (remaining=%d)", sig, len(self._forced_queue))
                return sig, rounds, mins_left

            # ตรวจว่าควร trigger ไหม
            if not self._should_trigger(now):
                return None

            sequence = self._build_sequence()
            if not sequence:
                self._force_triggered = True
                return None

            self._force_triggered = True
            self._forced_queue.extend(sequence[1:])

            rounds    = self._calc_rounds()
            mins_left = max(0, int((self.session_end_time - now).total_seconds() / 60))
            logger.warning(
                "[EOS] TRIGGERED | session=%s mins_left=%d rounds=%.1f seq=%s",
                self.session_name, mins_left, rounds, sequence,
            )
            return sequence[0], rounds, mins_left

    def reset_for_new_session(
        self,
        session_end_time: datetime,
        session_name: str = "Unknown",
    ) -> None:
        """รีเซ็ต state ทั้งหมดเมื่อเริ่ม session ใหม่"""
        with self._lock:
            self.session_end_time = session_end_time
            self.session_name     = session_name
            self._signal_history.clear()
            self._last_active_ts  = None
            self._forced_queue.clear()
            self._force_triggered = False
        logger.info("[EOS] reset → session=%s end=%s",
                    session_name, session_end_time.strftime("%H:%M"))

    # ── Internal helpers ─────────────────────────────────────

    def _should_trigger(self, now: datetime) -> bool:
        """เช็คเงื่อนไขครบ 4 ข้อก่อน trigger"""
        if self._force_triggered:
            return False
        window_start = self.session_end_time - timedelta(minutes=self.window_minutes)
        if now < window_start or now >= self.session_end_time:
            return False
        ref           = self._last_active_ts or window_start
        hold_mins     = (now - ref).total_seconds() / 60
        if hold_mins < self.hold_threshold_min:
            return False
        if self._calc_rounds() >= _ROUND_TWO_PLUS:
            return False
        return True

    def _calc_rounds(self) -> float:
        """
        คำนวณ round จาก signal_history

            []                     → 0.0   (ไม่มีเลย)
            [SELL]                 → 0.5   (SELL ค้าง / net short)
            [BUY, SELL]            → 1.0   (flat)
            [BUY, SELL, BUY]       → 1.5   (BUY ค้าง / net long)
            [BUY, SELL, BUY, SELL] → 2.0   (flat, 2 รอบ)
        """
        if not self._signal_history:
            return _ROUND_NONE
        buy_count  = sum(1 for _, s in self._signal_history if s == "BUY")
        sell_count = sum(1 for _, s in self._signal_history if s == "SELL")
        complete   = min(buy_count, sell_count)
        rounds     = float(complete) + (0.5 if buy_count != sell_count else 0.0)
        return min(rounds, _ROUND_TWO_PLUS)

    def _build_sequence(self) -> List[str]:
        """
        เลือก sequence ตาม round:

            rounds    │ sequence
            ──────────┼──────────────────────────────────
            0.0       │ [BUY, SELL, BUY, SELL]
            0.5       │ [BUY, SELL, BUY]
            1.0       │ [BUY, SELL]
            1.5       │ [SELL]
            ≥2.0      │ []
        """
        r = self._calc_rounds()
        if r < _ROUND_HALF:       return ["BUY", "SELL", "BUY", "SELL"]
        elif r < _ROUND_ONE:      return ["BUY", "SELL", "BUY"]
        elif r < _ROUND_ONE_HALF: return ["BUY", "SELL"]
        elif r < _ROUND_TWO_PLUS: return ["SELL"]
        else:                     return []


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
    eos_forcer : EndOfSessionForcer | None
        [v2.2] ถ้าส่งเข้ามา → predict() จะตรวจ forced signal ก่อนรัน model

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
        eos_forcer: Optional[EndOfSessionForcer] = None,
    ) -> None:
        self.threshold: float = float(threshold)
        self.feature_columns: List[str] = self._load_feature_schema(feature_schema_path)
        self._buy_model  = self._load_pickle(model_buy_path, label="BUY")
        self._sell_model = self._load_pickle(model_sell_path, label="SELL")
        self.loaded: bool = True
        self.eos: Optional[EndOfSessionForcer] = eos_forcer  # [v2.2]

        # Initialize SHAP Explainers
        self.use_shap = False
        self._buy_explainer  = None
        self._sell_explainer = None
        if shap is not None:
            try:
                self._buy_explainer  = shap.TreeExplainer(self._buy_model)
                self._sell_explainer = shap.TreeExplainer(self._sell_model)
                self.use_shap = True
                logger.info("[XGB] ✓ SHAP TreeExplainers initialized successfully")
            except Exception as e:
                logger.warning("[XGB] SHAP initialization failed: %s", e)

        logger.info(
            "[XGB] ✓ Dual-model predictor ready | features=%d threshold=%.2f eos=%s",
            len(self.feature_columns), self.threshold,
            "enabled" if eos_forcer else "disabled",
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
            import joblib
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

        [v2.2] ถ้า EndOfSessionForcer มี forced signal รอ → inject เข้า XGBOutput
               โดยตรง (ข้ามการรัน model) พร้อม metadata สำหรับ core.py

        Parameters
        ----------
        features : dict
            dict ที่มี key ตรงตาม `self.feature_columns` (key ที่ขาดจะถูกเติม 0.0)
        session : str
            ชื่อ session — เก็บลงใน output เพื่อ trace; ไม่กระทบ inference
        """
        now = datetime.now()

        # ── [v2.2] ตรวจ forced signal ก่อนรัน model ──────────
        if self.eos is not None:
            forced = self.eos.get_next_forced(now)
            if forced is not None:
                forced_sig, forced_rounds, mins_left = forced
                logger.warning(
                    "[XGB] EOS forced signal: %s (rounds=%.1f mins_left=%d)",
                    forced_sig, forced_rounds, mins_left,
                )
                # บันทึกลง history ทันที เพื่อให้ round ถัดไปนับถูก
                self.eos.record_signal(forced_sig, now)
                return XGBOutput(
                    prob_buy=EOS_FORCE_CONFIDENCE if forced_sig == "BUY" else 0.0,
                    prob_sell=EOS_FORCE_CONFIDENCE if forced_sig == "SELL" else 0.0,
                    direction=forced_sig,
                    confidence=EOS_FORCE_CONFIDENCE,
                    session=session,
                    is_high_accuracy_session=session in HIGH_ACCURACY_SESSIONS,
                    # [v2.2] metadata สำหรับ core.py สร้าง reason
                    is_forced=True,
                    forced_rounds=forced_rounds,
                    session_mins_left=mins_left,
                    session_name=self.eos.session_name,
                )

        # ── รัน model ปกติ ────────────────────────────────────
        try:
            row        = self._build_row(features)
            buy_proba  = self._proba(self._buy_model, row)
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

        # บันทึก BUY/SELL จริงลงใน forcer เพื่อนับ round
        if self.eos is not None and direction in ("BUY", "SELL"):
            self.eos.record_signal(direction, now)

        # ── SHAP top features ─────────────────────────────────
        top_features_str = ""
        if self.use_shap and direction in ("BUY", "SELL"):
            try:
                explainer   = self._buy_explainer if direction == "BUY" else self._sell_explainer
                shap_values = explainer.shap_values(row)
                if isinstance(shap_values, list):
                    vals = np.abs(shap_values[1][0])
                else:
                    vals = np.abs(shap_values[0])
                top_indices = np.argsort(vals)[-3:][::-1]
                top_feats   = [
                    f"{self.feature_columns[i]} ({row.iloc[0, i]:.2f})"
                    for i in top_indices
                ]
                if len(top_feats) > 1:
                    top_features_str = " และ ".join([", ".join(top_feats[:-1]), top_feats[-1]])
                elif top_feats:
                    top_features_str = top_feats[0]
            except Exception as e:
                logger.error("[XGB] SHAP calculation failed: %s", e)

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

        ordered: dict = {}
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
        return pd.DataFrame([ordered], columns=self.feature_columns)

    @staticmethod
    def _proba(model, row) -> float:
        """ดึง probability ของ positive class (class index = 1) จากโมเดล binary"""
        if hasattr(model, "predict_proba"):
            arr = np.asarray(model.predict_proba(row))
            if arr.ndim == 2 and arr.shape[1] >= 2:
                return float(arr[0][1])
            if arr.ndim == 2 and arr.shape[1] == 1:
                return float(arr[0][0])
            return float(arr.flat[-1])
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

_DIR_SCORE  = {"BUY": 1, "HOLD": 0, "SELL": -1}
CONFLICT_GAP = 0.20


class SignalAggregator:
    """
    Legacy weighted-score aggregator (XGBoost + News + Technical).

    NOTE: ไม่ใช้ใน pipeline หลัก v2.1 — เก็บไว้เพื่อให้ test/integration เก่ายังเรียกได้
    """

    def __init__(self, session: str, market_open: bool):
        self.session     = session
        self.market_open = market_open
        self.weights     = self._get_weights()

    def aggregate(
        self,
        xgb: XGBOutput,
        news: Optional[ExternalSignal] = None,
        tech: Optional[ExternalSignal] = None,
    ) -> dict:
        w     = self.weights
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
            "direction":  agg_dir,
            "score":      round(score, 3),
            "confidence": round(abs(score), 3),
            "weights":    w,
            "components": {
                "xgboost":   f"{xgb.direction} ({xgb.confidence:.0%}) "
                             f"prob_buy={xgb.prob_buy} prob_sell={xgb.prob_sell}",
                "news":      f"{news.direction} ({news.confidence:.0%})" if news else "N/A",
                "technical": f"{tech.direction} ({tech.confidence:.0%})" if tech else "N/A",
            },
            "session":           self.session,
            "market_open":       self.market_open,
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