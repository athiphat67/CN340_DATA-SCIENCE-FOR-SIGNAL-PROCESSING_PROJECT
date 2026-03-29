"""
indicators.py — Gold Trading Agent
คำนวณ Technical Indicators รองรับทั้ง Phase 1 (Bot Signals) และ Phase 2 (ML Features)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional
import logging
from thailand_timestamp import get_thai_time

logger = logging.getLogger(__name__)


# ─── Result Dataclasses ─────────────────────────────────────────────────────────


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


@dataclass
class TrendResult:
    ema_20: float
    ema_50: float
    sma_200: float
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


# ─── Indicator Calculator ────────────────────────────────────────────────────────


class TechnicalIndicators:
    """
    คำนวณ Technical Indicators จาก OHLCV DataFrame
    - Phase 1: ใช้ method แต่ละตัว (rsi, macd, ...) → Rule-based signals
    - Phase 2: ใช้ get_ml_dataframe() → ML-ready DataFrame
    """

    def __init__(self, df: pd.DataFrame):
        if df.empty:
            raise ValueError("DataFrame is empty — cannot compute indicators")
        required = {"open", "high", "low", "close"}
        if not required.issubset(df.columns):
            raise ValueError(f"DataFrame ต้องมี columns: {required}")

        self.df = df.copy().reset_index(drop=True)
        self.close = self.df["close"]
        self.high = self.df["high"]
        self.low = self.df["low"]

        # คำนวณ vectorized ล่วงหน้าทั้งหมด
        self._calculate_all_vectorized()

    # ─── Vectorized pre-calculation ──────────────────────────────────────────────

    def _calculate_all_vectorized(self):
        close = self.close
        high = self.high
        low = self.low

        # RSI-14
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        # แก้ Edge Case RSI
        self.df["rsi_14"] = (100 - (100 / (1 + rs))).fillna(100)

        # MACD (12, 26, 9)
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        self.df["macd_line"] = ema_fast - ema_slow
        self.df["macd_signal"] = self.df["macd_line"].ewm(span=9, adjust=False).mean()
        self.df["macd_hist"] = self.df["macd_line"] - self.df["macd_signal"]

        # Bollinger Bands (20, 2.0)
        self.df["bb_mid"] = close.rolling(20).mean()
        std = close.rolling(20).std(ddof=0)
        self.df["bb_up"] = self.df["bb_mid"] + 2.0 * std
        self.df["bb_low"] = self.df["bb_mid"] - 2.0 * std
        mid_safe = self.df["bb_mid"].replace(0, np.nan)
        range_safe = (self.df["bb_up"] - self.df["bb_low"]).replace(0, np.nan)
        self.df["bb_bandwidth"] = (self.df["bb_up"] - self.df["bb_low"]) / mid_safe
        self.df["bb_pct_b"] = ((close - self.df["bb_low"]) / range_safe).fillna(0.5)

        # ATR-14
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        self.df["atr_14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

        # Trend: EMA20, EMA50, SMA200
        self.df["ema_20"] = close.ewm(span=20, adjust=False).mean()
        self.df["ema_50"] = close.ewm(span=50, adjust=False).mean()
        window_200 = min(200, len(self.df))
        self.df["sma_200"] = close.rolling(window=window_200).mean()
        if len(self.df) < 200:
            logger.warning("ข้อมูลน้อยกว่า 200 แท่ง — SMA200 ใช้ข้อมูลทั้งหมดแทน")

    # ─── ML DataFrame export ─────────────────────────────────────────────────────

    def get_ml_dataframe(self) -> pd.DataFrame:
        """ส่งออก DataFrame ที่มี features ครบ ตัด NaN แล้ว พร้อมยัดเข้าโมเดล ML"""
        return self.df.dropna().reset_index(drop=True)

    # ─── Phase 1 Signal Methods ──────────────────────────────────────────────────

    def rsi(self) -> RSIResult:
        value = round(float(self.df["rsi_14"].iloc[-1]), 2)
        if value >= 70:
            signal = "overbought"
        elif value <= 30:
            signal = "oversold"
        else:
            signal = "neutral"
        return RSIResult(value=value, signal=signal, period=14)

    def macd(self) -> MACDResult:
        curr_hist = float(self.df["macd_hist"].iloc[-1])
        prev_hist = float(self.df["macd_hist"].iloc[-2]) if len(self.df) >= 2 else 0.0

        # Strict Crossover
        if prev_hist < 0 and curr_hist > 0:
            crossover = "bullish_cross"
        elif prev_hist > 0 and curr_hist < 0:
            crossover = "bearish_cross"
        else:
            crossover = "none"

        return MACDResult(
            macd_line=round(float(self.df["macd_line"].iloc[-1]), 4),
            signal_line=round(float(self.df["macd_signal"].iloc[-1]), 4),
            histogram=round(curr_hist, 4),
            crossover=crossover,
        )

    def bollinger_bands(self) -> BollingerResult:
        u = float(self.df["bb_up"].iloc[-1])
        m = float(self.df["bb_mid"].iloc[-1])
        l = float(self.df["bb_low"].iloc[-1])
        c = float(self.close.iloc[-1])

        if c > u:
            signal = "above_upper"
        elif c < l:
            signal = "below_lower"
        else:
            signal = "inside"

        return BollingerResult(
            upper=round(u, 2),
            middle=round(m, 2),
            lower=round(l, 2),
            bandwidth=round(float(self.df["bb_bandwidth"].iloc[-1]), 6),
            pct_b=round(float(self.df["bb_pct_b"].iloc[-1]), 4),
            signal=signal,
        )

    def atr(self) -> ATRResult:
        val = float(self.df["atr_14"].iloc[-1])
        close_price = float(self.close.iloc[-1])
        atr_pct = val / close_price if close_price else 0

        if atr_pct < 0.005:
            vol_level = "low"
        elif atr_pct > 0.015:
            vol_level = "high"
        else:
            vol_level = "normal"

        return ATRResult(value=round(val, 2), period=14, volatility_level=vol_level)

    def trend(self) -> TrendResult:
        e20 = float(self.df["ema_20"].iloc[-1])
        e50 = float(self.df["ema_50"].iloc[-1])
        s200 = float(self.df["sma_200"].iloc[-1])

        golden = e20 > e50 > s200
        death = e20 < e50 < s200

        if e20 > e50:
            trend_label = "uptrend"
        elif e20 < e50:
            trend_label = "downtrend"
        else:
            trend_label = "sideways"

        return TrendResult(
            ema_20=round(e20, 2),
            ema_50=round(e50, 2),
            sma_200=round(s200, 2),
            trend=trend_label,
            golden_cross=golden,
            death_cross=death,
        )

    def compute_all(self) -> AllIndicators:
        return AllIndicators(
            rsi=self.rsi(),
            macd=self.macd(),
            bollinger=self.bollinger_bands(),
            atr=self.atr(),
            trend=self.trend(),
            latest_close=round(float(self.close.iloc[-1]), 2),
            calculated_at=get_thai_time().isoformat(),
        )

    def get_reliability_warnings(self, interval: str) -> list[str]:
        warnings = []
        t = self.trend()

        # MA ทั้ง 3 ใกล้กันเกินไป = sideways จริง แต่ trend label อาจผิด
        ma_range = max(t.ema_20, t.ema_50, t.sma_200) - min(
            t.ema_20, t.ema_50, t.sma_200
        )
        if ma_range < 1.0:  # ปรับตาม instrument
            warnings.append(
                f"EMA20/50/SMA200 ห่างกันแค่ {ma_range:.4f} — trend signal '{t.trend}' ไม่น่าเชื่อถือ ตลาดอาจ sideways"
            )

        # interval สั้น + ข้อมูลเยอะ → MA converge เป็นเรื่องปกติ
        if interval in ("1m", "5m", "15m"):
            warnings.append(
                f"Interval {interval}: SMA200 คำนวณจากแท่งสั้น ไม่ใช่ long-term trend"
            )

        return warnings

    def to_dict(self) -> dict:
        return asdict(self.compute_all())


# ─── Quick test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)
    n = 300
    price = 2300 + np.cumsum(np.random.randn(n) * 5)
    df_mock = pd.DataFrame(
        {
            "open": price - np.random.rand(n) * 3,
            "high": price + np.random.rand(n) * 8,
            "low": price - np.random.rand(n) * 8,
            "close": price,
            "volume": np.random.randint(10000, 50000, n),
        }
    )

    calc = TechnicalIndicators(df_mock)

    import json

    # ทดสอบรันดูได้เลยครับ JSON Output ออกมาเหมือนเป๊ะ
    print(json.dumps(calc.to_dict(), indent=2, ensure_ascii=False))
