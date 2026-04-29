"""
indicators.py — Gold Trading Agent
คำนวณ Technical Indicators รองรับทั้ง Phase 1 (Bot Signals) และ Phase 2 (ML Features)

รองรับ 2 ชุด:
    XAU/USD  → get_ml_features()       / get_ml_features_clean()
    Thai HSH → get_ml_features_thai()  / get_ml_features_thai_clean()

26 ML Features ชุด XAU/USD:
    OHLC (4):           xauusd_open, xauusd_high, xauusd_low, xauusd_close
    Returns (3):        xauusd_ret1, xauusd_ret3, usdthb_ret1
    MACD (2):           xau_macd_delta1, xauusd_macd_hist
    EMA Distance (3):   xauusd_dist_ema21, xauusd_dist_ema50, usdthb_dist_ema21
    Trend (1):          trend_regime
    RSI (2):            xauusd_rsi14, xau_rsi_delta1
    Volatility (3):     xauusd_atr_norm, atr_rank50, xauusd_bb_width
    Candle Shape (2):   wick_bias, body_strength
    Time Cyclic (5):    hour_sin, hour_cos, minute_sin, minute_cos, session_progress
    Calendar (1):       day_of_week

26 ML Features ชุด Thai HSH:
    OHLC (4):           thai_open, thai_high, thai_low, thai_close
    Returns (3):        thai_ret1, thai_ret3, xauusd_ret1
    MACD (2):           thai_macd_delta1, thai_macd_hist
    EMA Distance (3):   thai_dist_ema21, thai_dist_ema50, xauusd_dist_ema21
    Trend (1):          trend_regime
    RSI (2):            thai_rsi14, thai_rsi_delta1
    Volatility (3):     thai_atr_norm, atr_rank50, thai_bb_width
    Candle Shape (2):   wick_bias, body_strength
    Time Cyclic (5):    hour_sin, hour_cos, minute_sin, minute_cos, session_progress
    Calendar (1):       day_of_week
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional, Literal
import logging
from data_engine.thailand_timestamp import get_thai_time

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Feature Column Definitions (ลำดับคงที่ — ห้ามเปลี่ยน)
# ══════════════════════════════════════════════════════════════════════════════

ML_FEATURE_COLUMNS_XAUUSD: list[str] = [
    # OHLC raw (4)
    "xauusd_open",
    "xauusd_high",
    "xauusd_low",
    "xauusd_close",
    # Returns (3)
    "xauusd_ret1",        # (close[t] - close[t-1]) / close[t-1]
    "xauusd_ret3",        # (close[t] - close[t-3]) / close[t-3]
    "usdthb_ret1",        # (usdthb[t] - usdthb[t-1]) / usdthb[t-1]
    # MACD (2)
    "xau_macd_delta1",    # macd_hist[t] - macd_hist[t-1]
    "xauusd_macd_hist",   # EMA(12) - EMA(26) - signal(9)
    # EMA Distance % (3)
    "xauusd_dist_ema21",  # (close - ema21) / ema21
    "xauusd_dist_ema50",  # (close - ema50) / ema50
    "usdthb_dist_ema21",  # (usdthb - usdthb_ema21) / usdthb_ema21
    # Trend (1)
    "trend_regime",       # 1=up, 0=side, -1=down
    # RSI (2)
    "xauusd_rsi14",
    "xau_rsi_delta1",     # rsi[t] - rsi[t-1]
    # Volatility (3)
    "xauusd_atr_norm",    # ATR(14) / close
    "atr_rank50",         # percentile rank ATR ใน 50 bars
    "xauusd_bb_width",    # (bb_upper - bb_lower) / bb_middle
    # Candle Shape (2)
    "wick_bias",          # (upper_wick - lower_wick) / range
    "body_strength",      # |close - open| / range
    # Time Cyclic (5)
    "hour_sin",
    "hour_cos",
    "minute_sin",
    "minute_cos",
    "session_progress",
    # Calendar (1)
    "day_of_week",
]

ML_FEATURE_COLUMNS_THAI: list[str] = [
    # OHLC raw (4)
    "thai_open",
    "thai_high",
    "thai_low",
    "thai_close",
    # Returns (3)
    "thai_ret1",          # (close[t] - close[t-1]) / close[t-1]
    "thai_ret3",          # (close[t] - close[t-3]) / close[t-3]
    "xauusd_ret1",        # ทองโลก 1-bar return — external signal
    # MACD (2)
    "thai_macd_delta1",
    "thai_macd_hist",
    # EMA Distance % (3)
    "thai_dist_ema21",
    "thai_dist_ema50",
    "xauusd_dist_ema21",  # ทองโลก dist EMA21 — cross-market signal
    # Trend (1)
    "trend_regime",
    # RSI (2)
    "thai_rsi14",
    "thai_rsi_delta1",
    # Volatility (3)
    "thai_atr_norm",
    "atr_rank50",
    "thai_bb_width",
    # Candle Shape (2)
    "wick_bias",
    "body_strength",
    # Time Cyclic (5)
    "hour_sin",
    "hour_cos",
    "minute_sin",
    "minute_cos",
    "session_progress",   # session ทองไทย 09:00-17:00
    # Calendar (1)
    "day_of_week",
]

# backward compat alias
ML_FEATURE_COLUMNS = ML_FEATURE_COLUMNS_XAUUSD

assert len(ML_FEATURE_COLUMNS_XAUUSD) == 26, f"xauusd: expected 26, got {len(ML_FEATURE_COLUMNS_XAUUSD)}"
assert len(ML_FEATURE_COLUMNS_THAI)   == 26, f"thai: expected 26, got {len(ML_FEATURE_COLUMNS_THAI)}"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 Result Dataclasses
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RSIResult:
    value: float
    signal: str
    period: int = 14


@dataclass
class MACDResult:
    macd_line: float
    signal_line: float
    histogram: float
    crossover: str


@dataclass
class BollingerResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float
    pct_b: float
    signal: str


@dataclass
class ATRResult:
    value: float
    period: int = 14
    volatility_level: str = "normal"
    unit: str = "USD_PER_OZ"


@dataclass
class TrendResult:
    ema_20: float
    ema_50: float
    trend: str
    golden_cross: bool
    death_cross: bool


@dataclass
class AllIndicators:
    rsi: RSIResult
    macd: MACDResult
    bollinger: BollingerResult
    atr: ATRResult
    trend: TrendResult
    latest_close: float
    calculated_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Core Calculator
# ══════════════════════════════════════════════════════════════════════════════

class TechnicalIndicators:
    """
    คำนวณ Technical Indicators จาก OHLCV DataFrame

    Phase 1 (Bot):
        rsi() / macd() / bollinger_bands() / atr() / trend() / to_dict()

    Phase 2 ML — XAU/USD (หน่วย USD/oz):
        get_ml_features(usdthb_series)       → DataFrame 26 features ยังไม่ dropna
        get_ml_features_clean(usdthb_series) → DataFrame 26 features dropna แล้ว

    Phase 2 ML — Thai HSH (หน่วย THB/บาททอง):
        get_ml_features_thai(xauusd_series)       → DataFrame 26 features ยังไม่ dropna
        get_ml_features_thai_clean(xauusd_series) → DataFrame 26 features dropna แล้ว

    Unified API:
        get_features(symbol, external_series, drop_na) → เลือกชุดด้วย "xauusd" / "thai"

    Args:
        df      : OHLCV DataFrame ต้องมี columns: open, high, low, close
                  index ควรเป็น DatetimeIndex (UTC) เพื่อให้ time features ทำงาน
        usd_thb : float (optional) ถ้าส่งมา atr() จะ convert เป็น THB อัตโนมัติ
    """

    def __init__(self, df: pd.DataFrame, usd_thb: Optional[float] = None):
        if df.empty:
            raise ValueError("DataFrame is empty — cannot compute indicators")
        required = {"open", "high", "low", "close"}
        if not required.issubset(df.columns):
            raise ValueError(f"DataFrame ต้องมี columns: {required}")

        self.df      = df.copy().reset_index(drop=True)
        self.close   = self.df["close"]
        self.high    = self.df["high"]
        self.low     = self.df["low"]
        self.open_   = self.df["open"]
        self.usd_thb = usd_thb

        # เก็บ original DatetimeIndex ไว้สำหรับ time features
        self._orig_index: Optional[pd.DatetimeIndex] = (
            df.index if isinstance(df.index, pd.DatetimeIndex) else None
        )

        self._calculate_all_vectorized()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal: Vectorized pre-calculation (รันครั้งเดียวใน __init__)
    # ──────────────────────────────────────────────────────────────────────────

    def _calculate_all_vectorized(self) -> None:
        close = self.close
        high  = self.high
        low   = self.low

        # ── RSI-14 (Wilder EWM) ───────────────────────────────────────────────
        delta    = close.diff()
        avg_gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = (-delta).clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs                = avg_gain / avg_loss.replace(0, np.nan)
        self.df["rsi_14"] = (100 - (100 / (1 + rs))).fillna(100)

        # ── MACD (12, 26, 9) ──────────────────────────────────────────────────
        ema_fast               = close.ewm(span=12, adjust=False).mean()
        ema_slow               = close.ewm(span=26, adjust=False).mean()
        self.df["macd_line"]   = ema_fast - ema_slow
        self.df["macd_signal"] = self.df["macd_line"].ewm(span=9, adjust=False).mean()
        self.df["macd_hist"]   = self.df["macd_line"] - self.df["macd_signal"]

        # ── Bollinger Bands (20, 2σ) ──────────────────────────────────────────
        self.df["bb_mid"]       = close.rolling(20).mean()
        std                     = close.rolling(20).std(ddof=0)
        self.df["bb_up"]        = self.df["bb_mid"] + 2.0 * std
        self.df["bb_low_band"]  = self.df["bb_mid"] - 2.0 * std
        mid_safe                = self.df["bb_mid"].replace(0, np.nan)
        band_range              = (self.df["bb_up"] - self.df["bb_low_band"]).replace(0, np.nan)
        self.df["bb_bandwidth"] = (self.df["bb_up"] - self.df["bb_low_band"]) / mid_safe
        self.df["bb_pct_b"]     = ((close - self.df["bb_low_band"]) / band_range).fillna(0.5)

        # ── ATR-14 (Wilder EWM) ───────────────────────────────────────────────
        prev_close        = close.shift(1)
        tr                = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)
        self.df["atr_14"] = tr.ewm(alpha=1/14, adjust=False).mean()

        # ── EMA 20 / 21 / 50 / 200 ────────────────────────────────────────────
        # Phase-1 → ema_20  |  Phase-2 ML → ema_21
        self.df["ema_20"]  = close.ewm(span=20, adjust=False).mean()
        self.df["ema_21"]  = close.ewm(span=21, adjust=False).mean()
        self.df["ema_50"]  = close.ewm(span=50, adjust=False).mean()
        self.df["ema_200"] = close.ewm(span=200, adjust=False).mean()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal: Shared helpers (ใช้ร่วมกันทั้งสองชุด)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_candle_shape(self) -> tuple[pd.Series, pd.Series]:
        """
        คืน (wick_bias, body_strength) — ค่าไม่ขึ้นกับ unit ของราคา

        wick_bias    = (upper_wick - lower_wick) / range
                       > 0 = selling pressure, < 0 = buying pressure
        body_strength = |close - open| / range
                       0 = doji, 1 = full body
        """
        close  = self.df["close"]
        high   = self.df["high"]
        low    = self.df["low"]
        open_  = self.df["open"]
        range_ = (high - low).replace(0, np.nan)
        max_oc = pd.concat([open_, close], axis=1).max(axis=1)
        min_oc = pd.concat([open_, close], axis=1).min(axis=1)
        wick_bias     = ((high - max_oc) - (min_oc - low)) / range_
        body_strength = (close - open_).abs() / range_
        return wick_bias, body_strength

    def _build_time_features(
        self,
        session_start_hour: int,
        session_end_hour: int,
    ) -> dict[str, pd.Series]:
        """
        คืน dict time cyclic + calendar features
        ถ้าไม่มี DatetimeIndex → คืน zeros ทั้งหมด (fallback สำหรับ CSV ที่ไม่มี index)
        """
        idx = self._orig_index
        n   = len(self.df)

        # พยายามดึง DatetimeIndex จาก column "datetime" ถ้าไม่มี index
        if idx is None and "datetime" in self.df.columns:
            try:
                idx = pd.DatetimeIndex(self.df["datetime"])
            except Exception:
                idx = None

        if idx is None:
            zeros = pd.Series(np.zeros(n), index=self.df.index)
            return {k: zeros.copy() for k in
                    ["hour_sin", "hour_cos", "minute_sin", "minute_cos",
                     "session_progress", "day_of_week"]}

        hour_s   = pd.Series(idx.hour,      index=self.df.index).astype(float)
        minute_s = pd.Series(idx.minute,    index=self.df.index).astype(float)
        dow_s    = pd.Series(idx.dayofweek, index=self.df.index).astype(float)

        session_len = max((session_end_hour - session_start_hour) * 60, 1)
        elapsed     = (hour_s - session_start_hour) * 60 + minute_s

        return {
            "hour_sin":         np.sin(2 * np.pi * hour_s   / 24),
            "hour_cos":         np.cos(2 * np.pi * hour_s   / 24),
            "minute_sin":       np.sin(2 * np.pi * minute_s / 60),
            "minute_cos":       np.cos(2 * np.pi * minute_s / 60),
            "session_progress": (elapsed / session_len).clip(0, 1),
            "day_of_week":      dow_s,
        }

    def _build_trend_regime(self) -> pd.Series:
        """
        1  = uptrend   (ema21 > ema50 + 0.1%)
        0  = sideways  (ema21 ≈ ema50, ±0.1% band)
        -1 = downtrend (ema21 < ema50 - 0.1%)
        """
        ema21 = self.df["ema_21"]
        ema50 = self.df["ema_50"]
        band  = ema50 * 0.001
        return pd.Series(
            np.where(ema21 > ema50 + band,  1,
            np.where(ema21 < ema50 - band, -1, 0)).astype(float),
            index=self.df.index,
        )

    def _build_atr_rank50(self) -> pd.Series:
        """percentile rank ของ ATR ใน 50 bars ล่าสุด (0–1)"""
        return (
            self.df["atr_14"]
            .rolling(50)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        )

    def _align_external(self, series: Optional[pd.Series]) -> Optional[pd.Series]:
        """reindex + ffill external series ให้ index ตรงกับ self.df"""
        if series is None or series.empty:
            return None
        return series.reindex(self.df.index).ffill()

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 2 — XAU/USD  (26 features, หน่วย USD/oz)
    # ──────────────────────────────────────────────────────────────────────────

    def get_ml_features(
        self,
        usdthb_series: Optional[pd.Series] = None,
        session_start_hour: int = 6,
        session_end_hour: int = 23,
    ) -> pd.DataFrame:
        """
        สร้าง 26 ML features สำหรับทองโลก XAU/USD

        Args:
            usdthb_series      : pd.Series ราคา USD/THB (index ตรงกับ df)
                                 None → usdthb features = 0.0
            session_start_hour : เริ่ม session (default 6 = 06:00)
            session_end_hour   : สิ้นสุด session (default 23 = 23:00)

        Returns:
            pd.DataFrame  columns = ML_FEATURE_COLUMNS_XAUUSD (26 ตัว)
            ยังไม่ dropna — ใช้ get_ml_features_clean() ถ้าต้องการ dropna
        """
        df    = self.df
        close = df["close"]
        out   = pd.DataFrame(index=df.index)

        # 1. OHLC (4)
        out["xauusd_open"]  = df["open"]
        out["xauusd_high"]  = df["high"]
        out["xauusd_low"]   = df["low"]
        out["xauusd_close"] = close

        # 2. Returns (3)
        out["xauusd_ret1"] = close.pct_change(1)
        out["xauusd_ret3"] = close.pct_change(3)
        usdthb             = self._align_external(usdthb_series)
        out["usdthb_ret1"] = usdthb.pct_change(1) if usdthb is not None else 0.0

        # 3. MACD (2)
        out["xauusd_macd_hist"] = df["macd_hist"]
        out["xau_macd_delta1"]  = df["macd_hist"].diff(1)

        # 4. EMA Distance % (3)
        ema21_safe = df["ema_21"].replace(0, np.nan)
        ema50_safe = df["ema_50"].replace(0, np.nan)
        out["xauusd_dist_ema21"] = (close - df["ema_21"]) / ema21_safe
        out["xauusd_dist_ema50"] = (close - df["ema_50"]) / ema50_safe
        if usdthb is not None:
            usdthb_ema21             = usdthb.ewm(span=21, adjust=False).mean()
            out["usdthb_dist_ema21"] = (usdthb - usdthb_ema21) / usdthb_ema21.replace(0, np.nan)
        else:
            out["usdthb_dist_ema21"] = 0.0

        # 5. Trend Regime (1)
        out["trend_regime"] = self._build_trend_regime()

        # 6. RSI (2)
        out["xauusd_rsi14"]   = df["rsi_14"]
        out["xau_rsi_delta1"] = df["rsi_14"].diff(1)

        # 7. Volatility (3)
        out["xauusd_atr_norm"] = df["atr_14"] / close.replace(0, np.nan)
        out["atr_rank50"]      = self._build_atr_rank50()
        out["xauusd_bb_width"] = df["bb_bandwidth"]

        # 8. Candle Shape (2)
        out["wick_bias"], out["body_strength"] = self._build_candle_shape()

        # 9. Time Cyclic + Calendar (6)
        for k, v in self._build_time_features(session_start_hour, session_end_hour).items():
            out[k] = v

        return out[ML_FEATURE_COLUMNS_XAUUSD]

    def get_ml_features_clean(
        self,
        usdthb_series: Optional[pd.Series] = None,
        session_start_hour: int = 6,
        session_end_hour: int = 23,
    ) -> pd.DataFrame:
        """เหมือน get_ml_features() แต่ dropna + reset_index — ใช้สำหรับ training"""
        return self.get_ml_features(
            usdthb_series=usdthb_series,
            session_start_hour=session_start_hour,
            session_end_hour=session_end_hour,
        ).dropna().reset_index(drop=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 2 — Thai HSH  (26 features, หน่วย THB/บาททอง)
    # ──────────────────────────────────────────────────────────────────────────

    def get_ml_features_thai(
        self,
        xauusd_series: Optional[pd.Series] = None,
        session_start_hour: int = 9,
        session_end_hour: int = 17,
    ) -> pd.DataFrame:
        """
        สร้าง 26 ML features สำหรับทองไทย HSH/THB

        ต่างจาก get_ml_features() ตรงที่:
        - prefix xauusd_ → thai_
        - external signal: usdthb_ → xauusd_ (ทองโลกเป็น signal แทน forex)
        - session_progress default = 09:00–17:00 (ออม NOW)

        Args:
            xauusd_series      : pd.Series ราคา XAU/USD (index ตรงกับ df)
                                 None → xauusd features = 0.0
            session_start_hour : เริ่ม session ทองไทย (default 9 = 09:00)
            session_end_hour   : สิ้นสุด session ทองไทย (default 17 = 17:00)

        Returns:
            pd.DataFrame  columns = ML_FEATURE_COLUMNS_THAI (26 ตัว)
            ยังไม่ dropna — ใช้ get_ml_features_thai_clean() ถ้าต้องการ dropna
        """
        df    = self.df
        close = df["close"]
        out   = pd.DataFrame(index=df.index)

        # 1. OHLC (4)
        out["thai_open"]  = df["open"]
        out["thai_high"]  = df["high"]
        out["thai_low"]   = df["low"]
        out["thai_close"] = close

        # 2. Returns (3)
        out["thai_ret1"]   = close.pct_change(1)
        out["thai_ret3"]   = close.pct_change(3)
        xauusd             = self._align_external(xauusd_series)
        out["xauusd_ret1"] = xauusd.pct_change(1) if xauusd is not None else 0.0

        # 3. MACD (2) — คำนวณบน THB แล้ว
        out["thai_macd_hist"]   = df["macd_hist"]
        out["thai_macd_delta1"] = df["macd_hist"].diff(1)

        # 4. EMA Distance % (3)
        ema21_safe = df["ema_21"].replace(0, np.nan)
        ema50_safe = df["ema_50"].replace(0, np.nan)
        out["thai_dist_ema21"] = (close - df["ema_21"]) / ema21_safe
        out["thai_dist_ema50"] = (close - df["ema_50"]) / ema50_safe
        if xauusd is not None:
            xauusd_ema21             = xauusd.ewm(span=21, adjust=False).mean()
            out["xauusd_dist_ema21"] = (xauusd - xauusd_ema21) / xauusd_ema21.replace(0, np.nan)
        else:
            out["xauusd_dist_ema21"] = 0.0

        # 5. Trend Regime (1) — คำนวณบน ema_21/ema_50 ของ THB
        out["trend_regime"] = self._build_trend_regime()

        # 6. RSI (2)
        out["thai_rsi14"]      = df["rsi_14"]
        out["thai_rsi_delta1"] = df["rsi_14"].diff(1)

        # 7. Volatility (3)
        out["thai_atr_norm"] = df["atr_14"] / close.replace(0, np.nan)
        out["atr_rank50"]    = self._build_atr_rank50()
        out["thai_bb_width"] = df["bb_bandwidth"]

        # 8. Candle Shape (2) — shape ไม่ขึ้นกับ unit
        out["wick_bias"], out["body_strength"] = self._build_candle_shape()

        # 9. Time Cyclic + Calendar (6)
        for k, v in self._build_time_features(session_start_hour, session_end_hour).items():
            out[k] = v

        return out[ML_FEATURE_COLUMNS_THAI]

    def get_ml_features_thai_clean(
        self,
        xauusd_series: Optional[pd.Series] = None,
        session_start_hour: int = 9,
        session_end_hour: int = 17,
    ) -> pd.DataFrame:
        """เหมือน get_ml_features_thai() แต่ dropna + reset_index — ใช้สำหรับ training"""
        return self.get_ml_features_thai(
            xauusd_series=xauusd_series,
            session_start_hour=session_start_hour,
            session_end_hour=session_end_hour,
        ).dropna().reset_index(drop=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 2 — Unified API
    # ──────────────────────────────────────────────────────────────────────────

    def get_features(
        self,
        symbol: Literal["xauusd", "thai"] = "xauusd",
        external_series: Optional[pd.Series] = None,
        session_start_hour: Optional[int] = None,
        session_end_hour: Optional[int] = None,
        drop_na: bool = True,
    ) -> pd.DataFrame:
        """
        Unified entry point — เลือกชุด features ด้วย symbol

        Args:
            symbol          : "xauusd" หรือ "thai"
            external_series : usdthb_series (xauusd) หรือ xauusd_series (thai)
            session_start_hour / session_end_hour : override default ได้
            drop_na         : True = dropna (default)

        ตัวอย่าง:
            feat_usd  = calc.get_features("xauusd", usdthb_series)
            feat_thai = calc.get_features("thai",   xauusd_series)
        """
        _defaults = {"xauusd": (6, 23), "thai": (9, 17)}
        if symbol not in _defaults:
            raise ValueError(f"symbol ต้องเป็น 'xauusd' หรือ 'thai'  ได้รับ: '{symbol}'")

        s_start, s_end = _defaults[symbol]
        s_start = session_start_hour if session_start_hour is not None else s_start
        s_end   = session_end_hour   if session_end_hour   is not None else s_end

        if symbol == "xauusd":
            fn = self.get_ml_features_clean if drop_na else self.get_ml_features
            return fn(usdthb_series=external_series,
                      session_start_hour=s_start, session_end_hour=s_end)
        else:
            fn = self.get_ml_features_thai_clean if drop_na else self.get_ml_features_thai
            return fn(xauusd_series=external_series,
                      session_start_hour=s_start, session_end_hour=s_end)

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 1 — Signal Methods
    # ──────────────────────────────────────────────────────────────────────────

    def rsi(self) -> RSIResult:
        value  = round(float(self.df["rsi_14"].iloc[-1]), 2)
        signal = "overbought" if value >= 70 else "oversold" if value <= 30 else "neutral"
        return RSIResult(value=value, signal=signal, period=14)

    def macd(self) -> MACDResult:
        curr_hist = float(self.df["macd_hist"].iloc[-1])
        prev_hist = float(self.df["macd_hist"].iloc[-2]) if len(self.df) >= 2 else 0.0
        if   prev_hist <= 0 and curr_hist > 0: crossover = "bullish_cross"
        elif prev_hist >= 0 and curr_hist < 0: crossover = "bearish_cross"
        elif curr_hist > 0:                    crossover = "bullish_zone"
        elif curr_hist < 0:                    crossover = "bearish_zone"
        else:                                  crossover = "neutral"
        return MACDResult(
            macd_line   = round(float(self.df["macd_line"].iloc[-1]), 4),
            signal_line = round(float(self.df["macd_signal"].iloc[-1]), 4),
            histogram   = round(curr_hist, 4),
            crossover   = crossover,
        )

    def bollinger_bands(self) -> BollingerResult:
        u = float(self.df["bb_up"].iloc[-1])
        m = float(self.df["bb_mid"].iloc[-1])
        l = float(self.df["bb_low_band"].iloc[-1])
        c = float(self.close.iloc[-1])
        signal = "above_upper" if c > u else "below_lower" if c < l else "inside"
        return BollingerResult(
            upper=round(u, 2), middle=round(m, 2), lower=round(l, 2),
            bandwidth = round(float(self.df["bb_bandwidth"].iloc[-1]), 6),
            pct_b     = round(float(self.df["bb_pct_b"].iloc[-1]), 4),
            signal    = signal,
        )

    def atr(self) -> ATRResult:
        val     = float(self.df["atr_14"].iloc[-1])
        atr_sma = self.df["atr_14"].rolling(50).mean()
        avg_val = float(atr_sma.iloc[-1]) if len(atr_sma.dropna()) > 0 else val
        vol_level = "low" if val < avg_val * 0.8 else "high" if val > avg_val * 1.5 else "normal"
        if self.usd_thb is not None:
            # USD/oz → THB/baht_weight:  × usd_thb / 31.1035 × 15.244 × 0.965
            val  = val * self.usd_thb / 31.1035 * 15.244 * 0.965
            unit = "THB_PER_BAHT_GOLD"
        else:
            unit = "USD_PER_OZ"
        return ATRResult(value=round(val, 2), period=14,
                         volatility_level=vol_level, unit=unit)

    def trend(self) -> TrendResult:
        e20 = float(self.df["ema_20"].iloc[-1])
        e50 = float(self.df["ema_50"].iloc[-1])
        trend_label = "uptrend" if e20 > e50 else "downtrend" if e20 < e50 else "sideways"
        return TrendResult(
            ema_20=round(e20, 2), ema_50=round(e50, 2),
            trend=trend_label, golden_cross=(e20 > e50), death_cross=(e20 < e50),
        )

    def compute_all(self) -> AllIndicators:
        return AllIndicators(
            rsi=self.rsi(), macd=self.macd(), bollinger=self.bollinger_bands(),
            atr=self.atr(), trend=self.trend(),
            latest_close  = round(float(self.close.iloc[-1]), 2),
            calculated_at = get_thai_time().isoformat(),
        )

    def to_dict(self, interval: str = "1h") -> dict:
        result_dict = asdict(self.compute_all())
        result_dict["data_quality"] = {
            "warnings": [], "is_weekend": False, "quality_score": "good",
        }
        return result_dict

    def get_ml_dataframe(self) -> pd.DataFrame:
        """[Legacy] ใช้ get_features() แทน"""
        return self.df.dropna().reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Quick Test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    np.random.seed(42)
    n         = 300
    price_usd = 2300 + np.cumsum(np.random.randn(n) * 5)
    price_thb = price_usd * 35 / 31.1035 * 15.244
    ts        = pd.date_range("2024-01-01 06:00", periods=n, freq="5min", tz="UTC")

    def _mock_ohlcv(price: np.ndarray) -> pd.DataFrame:
        rng = np.random.default_rng(0)
        return pd.DataFrame({
            "open":   price - rng.random(n) * 3,
            "high":   price + rng.random(n) * 8,
            "low":    price - rng.random(n) * 8,
            "close":  price,
            "volume": rng.integers(10_000, 50_000, n),
        }, index=ts)

    usdthb_s = pd.Series(35.0 + np.cumsum(np.random.randn(n) * 0.05), index=ts)
    xauusd_s = pd.Series(price_usd, index=ts)

    # ── XAU/USD ───────────────────────────────────────────────────────────────
    calc_usd  = TechnicalIndicators(_mock_ohlcv(price_usd))
    feat_usd  = calc_usd.get_ml_features_clean(usdthb_series=usdthb_s)
    feat_usd2 = calc_usd.get_features("xauusd", usdthb_s)

    assert feat_usd.shape[1] == 26
    assert list(feat_usd.columns) == ML_FEATURE_COLUMNS_XAUUSD
    assert feat_usd.shape == feat_usd2.shape
    print(f"✅ XAU/USD  shape={feat_usd.shape}  cols={list(feat_usd.columns)}")

    # ── Thai HSH ──────────────────────────────────────────────────────────────
    calc_thai  = TechnicalIndicators(_mock_ohlcv(price_thb))
    feat_thai  = calc_thai.get_ml_features_thai_clean(xauusd_series=xauusd_s)
    feat_thai2 = calc_thai.get_features("thai", xauusd_s)

    assert feat_thai.shape[1] == 26
    assert list(feat_thai.columns) == ML_FEATURE_COLUMNS_THAI
    assert feat_thai.shape == feat_thai2.shape
    print(f"✅ Thai HSH shape={feat_thai.shape}  cols={list(feat_thai.columns)}")

    # ── Shared features ───────────────────────────────────────────────────────
    shared = sorted(set(ML_FEATURE_COLUMNS_XAUUSD) & set(ML_FEATURE_COLUMNS_THAI))
    print(f"✅ Shared ({len(shared)}): {shared}")

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    p1 = calc_usd.to_dict("5m")
    print(f"✅ Phase 1 rsi={p1['rsi']['value']}  trend={p1['trend']['trend']}")

    print("\n✅ ทุก test ผ่าน")