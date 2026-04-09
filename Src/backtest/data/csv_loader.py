"""
backtest/data/csv_loader.py
══════════════════════════════════════════════════════════════════════
โหลด CSV ทองไทย พร้อม Merge กับ External CSV (Premium/Spot/Spread)
โดยแบ่งฟังก์ชันย่อยระดับ Indicator (Modular) เพื่อให้ง่ายต่อการ Debug ขั้นสุด
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

# ตั้งค่า Logger
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Indicator parameters ─────────────────────────────────────────────
RSI_PERIOD   = 14
EMA_FAST     = 20
EMA_SLOW     = 50
MACD_FAST    = 12
MACD_SLOW    = 26
MACD_SIGNAL  = 9
BB_PERIOD    = 20
BB_STD       = 2
ATR_PERIOD   = 14

# ══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════════════════════════

def load_gold_csv(gold_csv: str, external_csv: str = None) -> pd.DataFrame:
    """
    ฟังก์ชันหลักสำหรับเรียกใช้งาน: โหลด, Merge, และคำนวณ Indicators
    """
    df = _load_and_prep_main(gold_csv)

    if external_csv:
        df = _load_and_merge_external(df, external_csv)

    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info("▶ กำลังคำนวณ Technical Indicators...")
    df = _calculate_indicators(df)
    
    # ตัดแถวแรกๆ ที่ Indicator ยังคำนวณไม่เสร็จ (Warmup period)
    initial_len = len(df)
    df = df.dropna(subset=["rsi", "macd_line", "ema_50", "bb_upper", "atr"]).reset_index(drop=True)
    logger.info(f"✓ Drop warmup candles: ตัดทิ้งไป {initial_len - len(df)} แถว -> พร้อมใช้งาน {len(df):,} แถว")
    
    return df

# ══════════════════════════════════════════════════════════════════════
# Data Loading Helpers
# ══════════════════════════════════════════════════════════════════════

def _load_and_prep_main(gold_csv: str) -> pd.DataFrame:
    gold_path = Path(gold_csv)
    if not gold_path.exists():
        logger.error(f"❌ ไม่พบไฟล์ข้อมูลหลัก: {gold_csv}")
        raise FileNotFoundError(f"ไม่พบไฟล์ {gold_csv}")

    logger.info(f"▶ เริ่มโหลดข้อมูลหลักจาก: {gold_csv}")
    df = pd.read_csv(gold_csv)

    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    time_col = _find_column(df, "timestamp", ["datetime", "date", "time", "timestamp"])
    if not time_col:
        raise ValueError("Missing datetime column in main CSV")
    
    df["timestamp"] = pd.to_datetime(df[time_col], errors="coerce")
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("Asia/Bangkok", ambiguous="NaT", nonexistent="shift_forward")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Bangkok")
    
    if "Mock_HSH_Sell_Close" in df.columns:
        df["close"]  = df["Mock_HSH_Sell_Close"]
        df["open"]   = df.get("Mock_HSH_Sell_Open", df["close"])
        df["high"]   = df.get("Mock_HSH_Sell_High", df["close"])
        df["low"]    = df.get("Mock_HSH_Sell_Low", df["close"])
        df["volume"] = df.get("Mock_HSH_Sell_Volume", 0)
    else:
        df["close"] = df.get("Sell", df.get("close", 0))

    return df

def _load_and_merge_external(df_main: pd.DataFrame, external_csv: str) -> pd.DataFrame:
    ext_path = Path(external_csv)
    if not ext_path.exists():
        logger.warning(f"⚠ ไม่พบไฟล์ External: {external_csv} -> ข้ามการดึง Premium/Spread")
        return df_main

    logger.info(f"▶ เริ่มโหลดข้อมูล External จาก: {external_csv}")
    df_ext = pd.read_csv(external_csv)
    
    time_col_ext = _find_column(df_ext, "timestamp", ["datetime", "datetime_th", "date", "timestamp"])
    if not time_col_ext:
        return df_main

    df_ext["timestamp"] = pd.to_datetime(df_ext[time_col_ext], errors="coerce")
    if df_ext["timestamp"].dt.tz is None:
        df_ext["timestamp"] = df_ext["timestamp"].dt.tz_localize("Asia/Bangkok", ambiguous="NaT", nonexistent="shift_forward")
    else:
        df_ext["timestamp"] = df_ext["timestamp"].dt.tz_convert("Asia/Bangkok")
    
    cols_to_drop = [c for c in ["Buy", "Sell", "close", "open", "high", "low"] if c in df_ext.columns]
    df_ext = df_ext.drop(columns=cols_to_drop, errors="ignore")
    
    df_merged = pd.merge(df_main, df_ext, on="timestamp", how="inner")
    return df_merged

def _find_column(df: pd.DataFrame, expected_name: str, candidates: list[str]) -> str | None:
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_cols:
            return lower_cols[cand.lower()]
    return None

# ══════════════════════════════════════════════════════════════════════
# Indicator Calculation Helpers
# ══════════════════════════════════════════════════════════════════════

def _calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Master function สำหรับรวบรวม Indicators และทำ Shift(1)"""
    d = df.copy()
    
    # 1. เรียกใช้งานฟังก์ชันย่อยทีละตัว
    d = _calc_rsi(d)
    d = _calc_ema_and_trend(d)
    d = _calc_macd(d)
    d = _calc_bollinger_bands(d)
    d = _calc_atr(d)
    
    # 2. การ Shift (1) เพื่อป้องกัน Look-ahead bias ทำทีเดียวตรงนี้
    indicator_cols = ['rsi', 'rsi_signal', 'ema_20', 'ema_50', 'trend_signal', 
                      'macd_line', 'macd_signal', 'macd_hist', 
                      'bb_mid', 'bb_upper', 'bb_lower', 'atr']
    d[indicator_cols] = d[indicator_cols].shift(1)
    
    return d

def _calc_rsi(d: pd.DataFrame) -> pd.DataFrame:
    """คำนวณ RSI และสร้าง Signal (Overbought/Oversold)"""
    delta = d['close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    d['rsi'] = 100 - (100 / (1 + rs))
    d['rsi_signal'] = np.where(d['rsi'] > 70, 'overbought', np.where(d['rsi'] < 30, 'oversold', 'neutral'))
    return d

def _calc_ema_and_trend(d: pd.DataFrame) -> pd.DataFrame:
    """คำนวณ EMA 20/50 และตรวจสอบ Trend"""
    d['ema_20'] = d['close'].ewm(span=EMA_FAST, adjust=False).mean()
    d['ema_50'] = d['close'].ewm(span=EMA_SLOW, adjust=False).mean()
    d['trend_signal'] = np.where(d['ema_20'] > d['ema_50'], 'uptrend', np.where(d['ema_20'] < d['ema_50'], 'downtrend', 'sideways'))
    return d

def _calc_macd(d: pd.DataFrame) -> pd.DataFrame:
    """คำนวณ MACD Line, Signal Line และ Histogram"""
    ema_12 = d['close'].ewm(span=MACD_FAST, adjust=False).mean()
    ema_26 = d['close'].ewm(span=MACD_SLOW, adjust=False).mean()
    d['macd_line'] = ema_12 - ema_26
    d['macd_signal'] = d['macd_line'].ewm(span=MACD_SIGNAL, adjust=False).mean()
    d['macd_hist'] = d['macd_line'] - d['macd_signal']
    return d

def _calc_bollinger_bands(d: pd.DataFrame) -> pd.DataFrame:
    """คำนวณ Bollinger Bands (Upper, Mid, Lower)"""
    d['bb_mid'] = d['close'].rolling(window=BB_PERIOD).mean()
    bb_std = d['close'].rolling(window=BB_PERIOD).std()
    d['bb_upper'] = d['bb_mid'] + (BB_STD * bb_std)
    d['bb_lower'] = d['bb_mid'] - (BB_STD * bb_std)
    return d

def _calc_atr(d: pd.DataFrame) -> pd.DataFrame:
    """คำนวณ Average True Range (ATR) สำหรับวัดความผันผวน"""
    high_low = d['high'] - d['low']
    high_close = np.abs(d['high'] - d['close'].shift())
    low_close = np.abs(d['low'] - d['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    d['atr'] = tr.rolling(window=ATR_PERIOD).mean()
    return d

# ══════════════════════════════════════════════════════════════════════
# Self-test Block
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    
    gold_path = sys.argv[1] if len(sys.argv) > 1 else "Mock_HSH_OHLC.csv"
    ext_path  = sys.argv[2] if len(sys.argv) > 2 else "Premium_Calculated_Feb_Apr.csv"

    print("=" * 70)
    print("🚀 CSV Loader — Fully Modular Version Test")
    print("=" * 70)

    try:
        df = load_gold_csv(gold_csv=gold_path, external_csv=ext_path)

        print(f"\n📊 สรุปข้อมูล (Shape): {df.shape}")
        print(f"📅 ช่วงเวลา: {df['timestamp'].min()} → {df['timestamp'].max()}")
        print(f"💰 ช่วงราคา (Sell Close): {df['close'].min():,} → {df['close'].max():,} THB")
            
    except Exception as e:
        logger.error(f"\n❌ การทดสอบล้มเหลว: {e}")