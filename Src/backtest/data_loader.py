"""
data_loader.py — Historical Data Loader for Backtesting
Loads XAUUSD + USDTHB from CSV or yfinance, computes Thai gold price (THB/gram).
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Constants (same as fetcher.py)
TROY_OUNCE_IN_GRAMS = 31.1034768
THAI_GOLD_BAHT_IN_GRAMS = 15.244
THAI_GOLD_PURITY = 0.965
SPREAD_HALF = 50  # สมาคมฯ ตั้งราคา ± 50 บาท


def _project_root() -> str:
    """Return absolute path to the project root (parent of Src/)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_csv_xauusd(path: Optional[str] = None) -> pd.DataFrame:
    """
    Load XAUUSD daily CSV.
    Returns DataFrame with DatetimeIndex and columns: open, high, low, close.
    """
    if path is None:
        path = os.path.join(
            _project_root(), "Data", "Raw",
            "XAUUSD_Daily_200406110000_202512310000.csv",
        )
    df = pd.read_csv(path, sep="\t")
    df.rename(columns={
        "<DATE>": "date", "<OPEN>": "open", "<HIGH>": "high",
        "<LOW>": "low", "<CLOSE>": "close",
    }, inplace=True)
    df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d")
    df.set_index("date", inplace=True)
    df = df[["open", "high", "low", "close"]].astype(float)
    return df


def load_csv_usdthb(path: Optional[str] = None) -> pd.DataFrame:
    """
    Load USDTHB daily CSV.
    Returns DataFrame with DatetimeIndex and column: usd_thb.
    """
    if path is None:
        path = os.path.join(
            _project_root(), "Data", "Raw",
            "USDTHB_Daily_201106020000_202512310000.csv",
        )
    df = pd.read_csv(path, sep="\t")
    df.rename(columns={"<DATE>": "date", "<CLOSE>": "usd_thb"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d")
    df.set_index("date", inplace=True)
    df = df[["usd_thb"]].astype(float)
    return df


def fetch_yfinance_data(
    start_date: str,
    end_date: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Fetch XAUUSD OHLCV + USDTHB from yfinance for a date range.
    Returns merged DataFrame with Thai gold prices.
    """
    import yfinance as yf

    # Gold futures
    gold = yf.Ticker("GC=F").history(start=start_date, end=end_date, interval=interval)
    if gold.empty:
        logger.warning("yfinance returned empty gold data")
        return pd.DataFrame()
    gold.columns = [c.lower() for c in gold.columns]
    gold = gold[["open", "high", "low", "close"]].copy()

    # USDTHB
    fx = yf.Ticker("THB=X").history(start=start_date, end=end_date, interval=interval)
    if fx.empty:
        logger.warning("yfinance returned empty USDTHB data")
        return pd.DataFrame()
    fx.columns = [c.lower() for c in fx.columns]
    fx = fx[["close"]].rename(columns={"close": "usd_thb"})

    # Merge on date
    gold.index = gold.index.normalize()
    fx.index = fx.index.normalize()
    merged = gold.join(fx, how="inner")
    return merged


def compute_thai_gold_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame with columns [open, high, low, close, usd_thb],
    compute Thai gold prices in THB per gram and per baht-weight.

    Adds columns:
    - price_thb_per_gram  : ราคาต่อกรัม (99.99% purity)
    - price_thb_per_baht  : ราคาต่อบาททอง (96.5%, 15.244g)
    - thai_gold_buy_thb   : ราคารับซื้อ (baht-weight)
    - thai_gold_sell_thb  : ราคาขายออก (baht-weight)
    - buy_per_gram        : ราคารับซื้อต่อกรัม (สำหรับ backtest ออม NOW)
    - sell_per_gram       : ราคาขายออกต่อกรัม
    """
    out = df.copy()

    # Price per troy ounce in THB
    price_thb_per_oz = out["close"] * out["usd_thb"]

    # Price per gram (99.99% purity)
    out["price_thb_per_gram"] = price_thb_per_oz / TROY_OUNCE_IN_GRAMS

    # Price per baht-weight (96.5%, 15.244g)
    out["price_thb_per_baht"] = (
        out["price_thb_per_gram"] * THAI_GOLD_BAHT_IN_GRAMS * THAI_GOLD_PURITY
    )

    # Buy / Sell prices (baht-weight, rounded to nearest 50)
    out["thai_gold_sell_thb"] = (
        np.round((out["price_thb_per_baht"] + SPREAD_HALF) / 50) * 50
    )
    out["thai_gold_buy_thb"] = (
        np.round((out["price_thb_per_baht"] - SPREAD_HALF) / 50) * 50
    )

    # Per-gram buy/sell for ออม NOW trading (96.5% purity gold)
    out["sell_per_gram"] = out["thai_gold_sell_thb"] / THAI_GOLD_BAHT_IN_GRAMS
    out["buy_per_gram"] = out["thai_gold_buy_thb"] / THAI_GOLD_BAHT_IN_GRAMS

    return out


def load_backtest_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source: str = "csv",
) -> pd.DataFrame:
    """
    Main entry point: load and prepare data for backtesting.

    Parameters
    ----------
    start_date : str, optional  — e.g. "2025-11-01"
    end_date   : str, optional  — e.g. "2025-12-01"
    source     : "csv" | "yfinance"

    Returns
    -------
    DataFrame with columns:
        open, high, low, close, usd_thb,
        price_thb_per_gram, price_thb_per_baht,
        thai_gold_buy_thb, thai_gold_sell_thb,
        buy_per_gram, sell_per_gram
    """
    if source == "yfinance":
        if not start_date or not end_date:
            raise ValueError("start_date and end_date required for yfinance source")
        df = fetch_yfinance_data(start_date, end_date)
        if df.empty:
            raise ValueError("No data returned from yfinance")
    else:
        xau = load_csv_xauusd()
        thb = load_csv_usdthb()
        df = xau.join(thb, how="inner")

    # Filter date range
    if start_date:
        df = df[df.index >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df.index <= pd.Timestamp(end_date)]

    if df.empty:
        raise ValueError(f"No data in range {start_date} — {end_date}")

    df = compute_thai_gold_prices(df)
    logger.info(f"Loaded {len(df)} rows ({df.index[0].date()} → {df.index[-1].date()})")
    return df
