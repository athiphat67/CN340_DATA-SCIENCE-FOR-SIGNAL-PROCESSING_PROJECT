"""
xgboost_signal.py — XGBoost Signal Predictor + Signal Aggregator

Usage:
    from xgboost_signal import XGBoostPredictor, SignalAggregator, build_xgb_context

    predictor  = XGBoostPredictor("models/xgb_gold.json")
    aggregator = SignalAggregator(session="Evening", market_open=True)

    xgb_out    = predictor.predict(features_dict)
    ctx_str    = aggregator.aggregate_to_prompt(xgb_out, news_signal, tech_signal)

    # inject เข้า market_state แล้วส่ง PromptBuilder ต่อ
    market_state["xgb_signal"] = ctx_str
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

# Feature order ต้องตรงกับที่ train model ไว้
FEATURE_COLUMNS = [
    "xauusd_open", "xauusd_high", "xauusd_low", "xauusd_close",
    "xauusd_ret1", "xauusd_ret3", "usdthb_ret1",
    "xau_macd_delta1", "xauusd_dist_ema21", "xauusd_dist_ema50",
    "usdthb_dist_ema21", "trend_regime", "xauusd_rsi14", "xau_rsi_delta1",
    "xauusd_macd_hist", "xauusd_atr_norm", "xauusd_bb_width",
    "atr_rank50", "wick_bias", "body_strength",
    "hour_sin", "hour_cos", "minute_sin", "minute_cos",
    "session_progress", "day_of_week",
]

# Threshold ที่ได้จาก backtest (ปรับได้)
BUY_THRESHOLD  = 0.80
SELL_THRESHOLD = 0.60
CONFLICT_GAP   = 0.20   # |prob_buy - prob_sell| < นี้ = mixed signal

# Session ที่ model แม่นที่สุด (จากภาพ backtest)
HIGH_ACCURACY_SESSIONS = {"Evening"}


# ─────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────

@dataclass
class XGBOutput:
    prob_buy:   float
    prob_sell:  float
    direction:  str        # "BUY" | "SELL" | "HOLD"
    confidence: float      # max(prob_buy, prob_sell)
    session:    str
    is_high_accuracy_session: bool
    avg_mfe:    float = 0.0
    avg_mae:    float = 0.0

@dataclass
class ExternalSignal:
    """Generic signal จาก source อื่น (News / Technical)"""
    direction:  str    # "BUY" | "SELL" | "HOLD"
    confidence: float  # 0.0–1.0
    source:     str


# ─────────────────────────────────────────────────────────────────
# XGBoostPredictor
# ─────────────────────────────────────────────────────────────────

class XGBoostPredictor:
    """
    Load XGBoost model แล้ว predict prob_buy / prob_sell

    model ต้องเป็น multi-class (3 classes: 0=SELL, 1=HOLD, 2=BUY)
    หรือ binary ก็ได้ — ปรับ predict() ตามนั้น
    """

    def __init__(self, model_path: str):
        try:
            import xgboost as xgb
            self._model = xgb.XGBClassifier()
            self._model.load_model(model_path)
            logger.info(f"[XGB] Model loaded from {model_path}")
        except ImportError:
            raise RuntimeError("xgboost not installed — pip install xgboost")
        except Exception as e:
            raise RuntimeError(f"[XGB] Failed to load model: {e}")

    def predict(self, features: dict, session: str = "Unknown") -> XGBOutput:
        """
        features: dict ที่มี keys ตาม FEATURE_COLUMNS
        session:  "Morning" | "Afternoon" | "Evening"
        """
        try:
            import pandas as pd
            row = pd.DataFrame([{col: features.get(col, 0.0) for col in FEATURE_COLUMNS}])
            probs = self._model.predict_proba(row)[0]

            # สมมติ class order: [SELL=0, HOLD=1, BUY=2]
            prob_sell = float(probs[0])
            prob_buy  = float(probs[2])

        except Exception as e:
            logger.error(f"[XGB] Prediction failed: {e}")
            return XGBOutput(
                prob_buy=0.0, prob_sell=0.0,
                direction="HOLD", confidence=0.0,
                session=session, is_high_accuracy_session=False,
            )

        # ── Direction logic ──────────────────────────────────────
        is_high = session in HIGH_ACCURACY_SESSIONS

        if prob_buy >= BUY_THRESHOLD and (prob_buy - prob_sell) >= CONFLICT_GAP:
            direction  = "BUY"
            confidence = prob_buy
        elif prob_sell >= SELL_THRESHOLD and (prob_sell - prob_buy) >= CONFLICT_GAP:
            direction  = "SELL"
            confidence = prob_sell
        else:
            direction  = "HOLD"
            confidence = max(prob_buy, prob_sell)

        # ลด confidence ถ้าไม่ใช่ session ที่แม่น
        if not is_high and direction != "HOLD":
            confidence = round(confidence * 0.85, 3)

        return XGBOutput(
            prob_buy=round(prob_buy, 3),
            prob_sell=round(prob_sell, 3),
            direction=direction,
            confidence=round(confidence, 3),
            session=session,
            is_high_accuracy_session=is_high,
        )


# ─────────────────────────────────────────────────────────────────
# SignalAggregator — dynamic weight ตาม session
# ─────────────────────────────────────────────────────────────────

_DIR_SCORE = {"BUY": 1, "HOLD": 0, "SELL": -1}

class SignalAggregator:
    """
    รวม XGBoost + News + Technical → weighted score → direction + confidence

    Dynamic weights:
        Evening  + market_open  → News หนัก (ข่าว NY/London มีผล)
        Morning  / market_close → XGBoost หนัก (technical-driven)
        Afternoon               → balanced
    """

    def __init__(self, session: str, market_open: bool):
        self.session     = session
        self.market_open = market_open
        self.weights     = self._get_weights()

    # ── public ───────────────────────────────────────────────────

    def aggregate(
        self,
        xgb:  XGBOutput,
        news: Optional[ExternalSignal] = None,
        tech: Optional[ExternalSignal] = None,
    ) -> dict:
        """คืน aggregated signal dict"""
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
            "direction":   agg_dir,
            "score":       round(score, 3),
            "confidence":  round(abs(score), 3),
            "weights":     w,
            "components": {
                "xgboost": f"{xgb.direction} ({xgb.confidence:.0%}) prob_buy={xgb.prob_buy} prob_sell={xgb.prob_sell}",
                "news":    f"{news.direction} ({news.confidence:.0%})" if news else "N/A",
                "technical": f"{tech.direction} ({tech.confidence:.0%})" if tech else "N/A",
            },
            "session":  self.session,
            "market_open": self.market_open,
            "xgb_session_quality": "HIGH" if xgb.is_high_accuracy_session else "LOW",
        }

    def aggregate_to_prompt(
        self,
        xgb:  XGBOutput,
        news: Optional[ExternalSignal] = None,
        tech: Optional[ExternalSignal] = None,
    ) -> str:
        """สร้าง string พร้อม inject เข้า market_state["xgb_signal"]"""
        agg = self.aggregate(xgb, news, tech)
        w   = agg["weights"]
        c   = agg["components"]

        session_note = (
            "⚡ High-accuracy session (Evening)" if xgb.is_high_accuracy_session
            else "⚠️ Lower-accuracy session — reduce confidence"
        )

        conflict_note = ""
        if abs(xgb.prob_buy - xgb.prob_sell) < CONFLICT_GAP:
            conflict_note = " | ⚠️ Mixed XGB signal — treat as HOLD prior"

        return (
            f"[XGBoost Pre-Analysis]\n"
            f"  XGB:  {c['xgboost']}{conflict_note}\n"
            f"  News: {c['news']}\n"
            f"  Tech: {c['technical']}\n"
            f"  Weights: XGB={w['xgboost']} News={w['news']} Tech={w['technical']}\n"
            f"  ── Aggregated: {agg['direction']} | score={agg['score']} | conf={agg['confidence']:.0%}\n"
            f"  {session_note}\n"
            f"→ Use as prior. Override only if hard rules (SL/TP/candles) trigger."
        )

    # ── private ──────────────────────────────────────────────────

    def _get_weights(self) -> dict:
        s = self.session
        o = self.market_open

        if o and s == "Evening":         # NY/London open — news มีผลสูง
            return {"xgboost": 0.30, "news": 0.50, "technical": 0.20}
        elif s == "Morning":             # Asian session — technical + XGBoost
            return {"xgboost": 0.55, "news": 0.15, "technical": 0.30}
        elif s == "Afternoon":
            return {"xgboost": 0.45, "news": 0.25, "technical": 0.30}
        else:                            # market closed / unknown
            return {"xgboost": 0.50, "news": 0.15, "technical": 0.35}
