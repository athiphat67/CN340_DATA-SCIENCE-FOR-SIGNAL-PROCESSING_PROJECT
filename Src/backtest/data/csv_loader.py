"""
backtest/data/csv_loader.py
══════════════════════════════════════════════════════════════════════
โหลด CSV ทองไทย (format: Datetime, Open, High, Low, Close, Volume)
และคำนวณ Technical Indicators ครบชุดพร้อมใช้ใน backtest pipeline

Indicators ที่คำนวณ:
  RSI(14)             — Relative Strength Index
  MACD(12,26,9)       — Moving Average Convergence Divergence
  EMA(20), EMA(50)    — Exponential Moving Average
  BB(20,2)            — Bollinger Bands
  ATR(14)             — Average True Range

หมายเหตุ:
  - ใช้ shift(1) ป้องกัน look-ahead bias (indicator คำนวณจาก candle ก่อนหน้า)
  - DropNA: candles แรกๆ ที่ indicator ยังไม่ครบ warmup จะถูกตัดออก
  - Output columns ตรงกับที่ build_market_state() ใน backtest pipeline ต้องการ

Usage:
  from backtest.data.csv_loader import load_gold_csv

  df = load_gold_csv("Final_Merged_Backtest_Data_M5.csv")
  # ได้ DataFrame พร้อม timestamp, OHLCV, indicators ครบ
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Indicator parameters ─────────────────────────────────────────────
RSI_PERIOD   = 14
EMA_FAST     = 20
EMA_SLOW     = 50
MACD_FAST    = 12
MACD_SLOW    = 26
MACD_SIGNAL  = 9
BB_PERIOD    = 20
BB_STD       = 2.0
ATR_PERIOD   = 14
WARMUP_BARS  = MACD_SLOW + MACD_SIGNAL + 5   # ~40 bars minimum


# ══════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════


def load_gold_csv(
    csv_path: str | Path,
    drop_warmup: bool = True,
) -> pd.DataFrame:
    """
    โหลด CSV ทองไทย format ใหม่ (ISO datetime) และคำนวณ indicators

    Parameters
    ----------
    csv_path    : path ไปยัง CSV
    drop_warmup : ตัด candles ที่ indicators ยังไม่ครบ warmup (แนะนำ True)

    Returns
    -------
    pd.DataFrame พร้อมใช้งาน:
      timestamp  : datetime64 (Bangkok timezone-naive, sorted ascending)
      open, high, low, close, volume
      open_thai, high_thai, low_thai, close_thai  ← aliases สำหรับ pipeline
      rsi, rsi_signal
      macd_line, signal_line, macd_hist, macd_signal
      ema_20, ema_50, trend_signal
      bb_upper, bb_mid, bb_lower, bb_signal
      atr

    Raises
    ------
    FileNotFoundError : ไม่พบไฟล์
    ValueError        : ไม่พบ columns ที่จำเป็น
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    logger.info(f"📂 Loading {path.name} ...")

    # ── 1. อ่านและ normalize columns ────────────────────────────────
    raw = pd.read_csv(path, encoding="utf-8-sig")
    raw.columns = raw.columns.str.strip()

    # หา datetime column
    dt_col = _find_col(raw.columns, ["datetime", "time", "timestamp", "date"])
    if dt_col is None:
        raise ValueError(
            f"ไม่พบ datetime column\n"
            f"  columns ที่พบ: {list(raw.columns)}\n"
            f"  ต้องการ: Datetime / Time / Timestamp"
        )

    # parse datetime
    raw["timestamp"] = pd.to_datetime(raw[dt_col], errors="coerce")
    bad = raw["timestamp"].isna().sum()
    if bad > 0:
        logger.warning(f"  ⚠ parse datetime ไม่ได้ {bad} แถว → dropped")
    raw = raw.dropna(subset=["timestamp"]).copy()

    # rename OHLCV → lowercase
    col_map = {
        _find_col(raw.columns, ["open"]):   "open",
        _find_col(raw.columns, ["high"]):   "high",
        _find_col(raw.columns, ["low"]):    "low",
        _find_col(raw.columns, ["close"]):  "close",
        _find_col(raw.columns, ["volume"]): "volume",
    }
    col_map = {k: v for k, v in col_map.items() if k is not None}
    raw = raw.rename(columns=col_map)

    for col in ["open", "high", "low", "close"]:
        if col not in raw.columns:
            raise ValueError(f"ไม่พบ column '{col}' — ตรวจสอบ CSV headers")
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    raw = raw.dropna(subset=["open", "high", "low", "close"])
    raw = raw.sort_values("timestamp").reset_index(drop=True)

    logger.info(f"  ✓ raw rows: {len(raw):,} | "
                f"{raw['timestamp'].min()} → {raw['timestamp'].max()}")

    # ── 2. คำนวณ indicators (ป้องกัน look-ahead ด้วย shift ด้านล่าง) ─
    cols_to_keep = ["timestamp", "open", "high", "low", "close", "volume"]
    if "gold_spot_usd" in raw.columns: cols_to_keep.append("gold_spot_usd")
    if "usd_thb_rate"  in raw.columns: cols_to_keep.append("usd_thb_rate")
    # HSH real prices — pass-through ไม่ shift (เป็นราคา execution ไม่ใช่ indicator)
    if "hsh_buy"      in raw.columns: cols_to_keep.append("hsh_buy")
    if "hsh_sell"     in raw.columns: cols_to_keep.append("hsh_sell")
    if "has_real_hsh" in raw.columns: cols_to_keep.append("has_real_hsh")
    
    df = raw[cols_to_keep].copy()
    close = df["close"].astype(float)
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)

    df["rsi"]         = _rsi(close, RSI_PERIOD)
    df["ema_20"]      = close.ewm(span=EMA_FAST,  adjust=False).mean()
    df["ema_50"]      = close.ewm(span=EMA_SLOW,  adjust=False).mean()

    macd_line, sig_line, hist = _macd(close, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    df["macd_line"]   = macd_line
    df["signal_line"] = sig_line
    df["macd_hist"]   = hist

    bb_upper, bb_mid, bb_lower = _bollinger(close, BB_PERIOD, BB_STD)
    df["bb_upper"]    = bb_upper
    df["bb_mid"]      = bb_mid
    df["bb_lower"]    = bb_lower

    df["atr"]         = _atr(high, low, close, ATR_PERIOD)

    # ── 3. shift(1) — ป้องกัน look-ahead bias ──────────────────────
    # indicator ณ candle T ต้องใช้ข้อมูลถึง candle T-1 เท่านั้น
    ind_cols = [
        "rsi", "ema_20", "ema_50",
        "macd_line", "signal_line", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower",
        "atr",
    ]

    if "gold_spot_usd" in df.columns: ind_cols.append("gold_spot_usd")
    if "usd_thb_rate"  in df.columns: ind_cols.append("usd_thb_rate")
    # หมายเหตุ: hsh_buy, hsh_sell, has_real_hsh ไม่ shift —
    # เป็นราคา execution ณ candle นั้น ไม่ใช่ indicator ย้อนหลัง
    
    df[ind_cols] = df[ind_cols].shift(1)

    # ── 4. Derived signal labels ─────────────────────────────────────
    df["rsi_signal"]   = df["rsi"].apply(_rsi_signal)
    df["macd_signal"]  = df["macd_hist"].apply(
        lambda x: "bullish" if x > 0 else ("bearish" if x < 0 else "neutral")
    )
    df["trend_signal"] = df.apply(
        lambda r: "uptrend" if r["ema_20"] > r["ema_50"]
        else ("downtrend" if r["ema_20"] < r["ema_50"] else "neutral"),
        axis=1,
    )
    df["bb_signal"] = df.apply(
        lambda r: (
            "overbought" if r["close"] > r["bb_upper"]
            else ("oversold" if r["close"] < r["bb_lower"] else "neutral")
        ),
        axis=1,
    )

    # ── 5. _thai aliases ─────────────────────────────────────────────
    for col in ("open", "high", "low", "close"):
        df[f"{col}_thai"] = df[col].astype(float)

    # ── 6. Drop warmup rows (ถ้า enable) ─────────────────────────────
    if drop_warmup:
        before = len(df)
        df = df.dropna(subset=ind_cols).reset_index(drop=True)
        dropped = before - len(df)
        if dropped > 0:
            logger.info(f"  ✓ dropped {dropped} warmup bars (indicators not ready)")

    df = df.reset_index(drop=True)
    logger.info(
        f"  ✓ final rows: {len(df):,} | "
        f"indicators: RSI/MACD/EMA/BB/ATR ✅"
    )
    return df


# ══════════════════════════════════════════════════════════════════
# Indicator Functions
# ══════════════════════════════════════════════════════════════════


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI — Wilder's smoothing method"""
    delta  = close.diff()
    gain   = delta.clip(lower=0)
    loss   = (-delta).clip(lower=0)

    # Wilder's RMA (EMA with alpha=1/period)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.round(4)


def _macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD — returns (macd_line, signal_line, histogram)"""
    ema_fast   = close.ewm(span=fast,   adjust=False).mean()
    ema_slow   = close.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line.round(4), signal_line.round(4), histogram.round(4)


def _bollinger(
    close: pd.Series,
    period: int = 20,
    n_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands — returns (upper, mid, lower)"""
    mid   = close.rolling(window=period).mean()
    std   = close.rolling(window=period).std(ddof=0)
    upper = (mid + n_std * std).round(2)
    lower = (mid - n_std * std).round(2)
    return upper, mid.round(2), lower


def _atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """ATR — Average True Range (Wilder's smoothing)"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return atr.round(2)


def _rsi_signal(rsi_val: float) -> str:
    if pd.isna(rsi_val):
        return "neutral"
    if rsi_val > 70:
        return "overbought"
    if rsi_val < 30:
        return "oversold"
    return "neutral"


# ══════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════


def _find_col(columns, candidates: list[str]) -> Optional[str]:
    """หา column name แบบ case-insensitive"""
    lower_cols = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_cols:
            return lower_cols[cand.lower()]
    return None


# ── Self-test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "Final_Merged_Backtest_Data_M5.csv"

    print("=" * 60)
    print("CSV Loader — Self Test")
    print("=" * 60)

    df = load_gold_csv(csv_path)

    print(f"\nShape    : {df.shape}")
    print(f"Columns  : {df.columns.tolist()}")
    print(f"\nDate range: {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"Price range (close): {df['close'].min():,} → {df['close'].max():,} THB")

    print("\nSample row (indicator values):")
    sample = df.iloc[50]
    for col in ["timestamp", "close", "rsi", "rsi_signal",
                "macd_line", "macd_hist", "macd_signal",
                "ema_20", "ema_50", "trend_signal",
                "bb_upper", "bb_lower", "atr"]:
        print(f"  {col:<20} {sample[col]}")

    print("\nNull check (should all be 0):")
    ind_cols = ["rsi", "macd_line", "ema_20", "ema_50", "bb_upper", "atr"]
    for col in ind_cols:
        nulls = df[col].isna().sum()
        status = "✓" if nulls == 0 else f"✗ {nulls} nulls"
        print(f"  {col:<20} {status}")

    print("\n" + "=" * 60)
    print("DONE ✓")