"""
indicators.py — Gold Trading Agent · Phase 1 (Deterministic)
คำนวณ Technical Indicators ด้วย Pandas (RSI, MACD, Bollinger Bands, ATR, EMA, SMA)
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
    value: float            # ค่า RSI ล่าสุด (0–100)
    signal: str             # "overbought" | "oversold" | "neutral"
    period: int = 14

@dataclass
class MACDResult:
    macd_line: float        # MACD Line
    signal_line: float      # Signal Line
    histogram: float        # Histogram (MACD − Signal)
    crossover: str          # "bullish_cross" | "bearish_cross" | "none"

@dataclass
class BollingerResult:
    upper: float
    middle: float           # SMA
    lower: float
    bandwidth: float        # (upper − lower) / middle
    pct_b: float            # (close − lower) / (upper − lower)
    signal: str             # "above_upper" | "below_lower" | "inside"

@dataclass
class ATRResult:
    value: float            # Average True Range
    period: int = 14
    volatility_level: str = "normal"  # "low" | "normal" | "high"

@dataclass
class TrendResult:
    ema_20: float
    ema_50: float
    sma_200: float
    trend: str              # "uptrend" | "downtrend" | "sideways"
    golden_cross: bool      # EMA20 > EMA50 > SMA200
    death_cross: bool       # EMA20 < EMA50 < SMA200

@dataclass
class AllIndicators:
    rsi:        RSIResult
    macd:       MACDResult
    bollinger:  BollingerResult
    atr:        ATRResult
    trend:      TrendResult
    latest_close: float
    calculated_at: str


# ─── Indicator Calculator ────────────────────────────────────────────────────────

class TechnicalIndicators:
    """คำนวณ Technical Indicators จาก OHLCV DataFrame"""

    def __init__(self, df: pd.DataFrame):
        """
        Parameters
        ----------
        df : pd.DataFrame
            ต้องมี column: open, high, low, close, volume
            Index เป็น DatetimeIndex หรือ RangeIndex
        """
        if df.empty:
            raise ValueError("DataFrame is empty — cannot compute indicators")
        required = {"open", "high", "low", "close"}
        if not required.issubset(df.columns):
            raise ValueError(f"DataFrame ต้องมี columns: {required}")
        self.df = df.copy().reset_index(drop=True)
        self.close = self.df["close"]
        self.high  = self.df["high"]
        self.low   = self.df["low"]

    # ─── RSI ──────────────────────────────────────────────────────────────────
    def rsi(self, period: int = 14) -> RSIResult:
        """Relative Strength Index (Wilder's smoothing)"""
        delta = self.close.diff()
        gain  = delta.clip(lower=0)
        loss  = (-delta).clip(lower=0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        # avg_loss = 0 หมายถึงไม่มี loss เลย → RSI = 100 (overbought สุด)
        # ไม่ใช่ fillna(50) ซึ่งทำให้ผลผิด
        last_gain = avg_gain.iloc[-1]
        last_loss = avg_loss.iloc[-1]

        if last_loss == 0:
            value = 100.0 if last_gain > 0 else 50.0
        else:
            rs_val = last_gain / last_loss
            value  = round(100 - (100 / (1 + rs_val)), 2)

        if value >= 70:
            signal = "overbought"
        elif value <= 30:
            signal = "oversold"
        else:
            signal = "neutral"

        logger.debug(f"RSI({period}): {value} → {signal}")
        return RSIResult(value=value, signal=signal, period=period)

    # ─── MACD ─────────────────────────────────────────────────────────────────
    def macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> MACDResult:
        """Moving Average Convergence/Divergence"""
        ema_fast   = self.close.ewm(span=fast, adjust=False).mean()
        ema_slow   = self.close.ewm(span=slow, adjust=False).mean()
        macd_line  = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram  = macd_line - signal_line

        prev_hist  = histogram.iloc[-2] if len(histogram) >= 2 else 0
        curr_hist  = histogram.iloc[-1]

        if prev_hist < 0 and curr_hist >= 0:
            crossover = "bullish_cross"
        elif prev_hist > 0 and curr_hist <= 0:
            crossover = "bearish_cross"
        else:
            crossover = "none"

        result = MACDResult(
            macd_line   = round(float(macd_line.iloc[-1]), 4),
            signal_line = round(float(signal_line.iloc[-1]), 4),
            histogram   = round(float(curr_hist), 4),
            crossover   = crossover,
        )
        logger.debug(f"MACD: {result}")
        return result

    # ─── Bollinger Bands ──────────────────────────────────────────────────────
    def bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> BollingerResult:
        """Bollinger Bands (SMA ± k·σ)"""
        sma    = self.close.rolling(period).mean()
        std    = self.close.rolling(period).std(ddof=0)
        upper  = sma + std_dev * std
        lower  = sma - std_dev * std

        u = float(upper.iloc[-1])
        m = float(sma.iloc[-1])
        l = float(lower.iloc[-1])
        c = float(self.close.iloc[-1])

        bandwidth = round((u - l) / m, 6) if m != 0 else 0
        pct_b     = round((c - l) / (u - l), 4) if (u - l) != 0 else 0.5

        if c > u:
            signal = "above_upper"
        elif c < l:
            signal = "below_lower"
        else:
            signal = "inside"

        return BollingerResult(
            upper=round(u, 2), middle=round(m, 2), lower=round(l, 2),
            bandwidth=bandwidth, pct_b=pct_b, signal=signal,
        )

    # ─── ATR ──────────────────────────────────────────────────────────────────
    def atr(self, period: int = 14) -> ATRResult:
        """Average True Range — วัดระดับ Volatility"""
        prev_close = self.close.shift(1)
        tr = pd.concat([
            self.high - self.low,
            (self.high - prev_close).abs(),
            (self.low  - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr_value = float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])

        # กำหนดระดับ volatility จาก % ของราคา
        close_price = float(self.close.iloc[-1])
        atr_pct     = atr_value / close_price if close_price else 0

        if atr_pct < 0.005:
            vol_level = "low"
        elif atr_pct > 0.015:
            vol_level = "high"
        else:
            vol_level = "normal"

        return ATRResult(
            value=round(atr_value, 2),
            period=period,
            volatility_level=vol_level,
        )

    # ─── Trend (EMA/SMA) ──────────────────────────────────────────────────────
    def trend(self) -> TrendResult:
        """EMA 20/50 + SMA 200 พร้อมระบุ Trend และ Golden/Death Cross"""
        ema20  = float(self.close.ewm(span=20,  adjust=False).mean().iloc[-1])
        ema50  = float(self.close.ewm(span=50,  adjust=False).mean().iloc[-1])

        # SMA200 ต้องการข้อมูลอย่างน้อย 200 แท่ง
        if len(self.close) >= 200:
            sma200 = float(self.close.rolling(200).mean().iloc[-1])
        else:
            sma200 = float(self.close.rolling(len(self.close)).mean().iloc[-1])
            logger.warning("ข้อมูลน้อยกว่า 200 แท่ง — SMA200 ใช้ข้อมูลทั้งหมดแทน")

        golden = ema20 > ema50 > sma200
        death  = ema20 < ema50 < sma200

        if ema20 > ema50:
            trend_label = "uptrend"
        elif ema20 < ema50:
            trend_label = "downtrend"
        else:
            trend_label = "sideways"

        return TrendResult(
            ema_20=round(ema20, 2),
            ema_50=round(ema50, 2),
            sma_200=round(sma200, 2),
            trend=trend_label,
            golden_cross=golden,
            death_cross=death,
        )

    # ─── Compute All ──────────────────────────────────────────────────────────
    def compute_all(self) -> AllIndicators:
        """คำนวณทุก Indicator และส่งกลับเป็น AllIndicators dataclass"""
        from datetime import datetime

        return AllIndicators(
            rsi         = self.rsi(),
            macd        = self.macd(),
            bollinger   = self.bollinger_bands(),
            atr         = self.atr(),
            trend       = self.trend(),
            latest_close= round(float(self.close.iloc[-1]), 2),
            calculated_at = get_thai_time().isoformat(),
        )

    def to_dict(self) -> dict:
        """คำนวณทั้งหมดแล้วแปลงเป็น dict พร้อม serialize"""
        return asdict(self.compute_all())


# ─── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # สร้างข้อมูลจำลอง
    np.random.seed(42)
    n = 300
    price = 2300 + np.cumsum(np.random.randn(n) * 5)
    df_mock = pd.DataFrame({
        "open":   price - np.random.rand(n) * 3,
        "high":   price + np.random.rand(n) * 8,
        "low":    price - np.random.rand(n) * 8,
        "close":  price,
        "volume": np.random.randint(10000, 50000, n),
    })

    calc = TechnicalIndicators(df_mock)
    result = calc.to_dict()

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))