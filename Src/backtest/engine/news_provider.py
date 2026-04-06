"""
backtest/engine/news_provider.py
══════════════════════════════════════════════════════════════════════
NewsProvider interface — plug-in system สำหรับ news sentiment

3 implementations:
  NullNewsProvider  → neutral sentiment (ใช้ตอนนี้ — ยังไม่มี news data)
  CSVNewsProvider   → อ่านจาก CSV historical (ใช้เมื่อ data team ส่งมา)
  LiveNewsProvider  → ต่อ GoldNewsFetcher จริง (forward test / live)

ทำไมต้องเป็น Interface:
  backtest pipeline รับ news_provider เป็น parameter ตัวเดียว
  → เปลี่ยน source ได้โดยไม่แก้โค้ด pipeline แม้แต่บรรทัดเดียว
  → ตอนนี้ใช้ Null ไปก่อน พอมีข้อมูลแค่ swap class เดียว

Usage:
  from backtest.engine.news_provider import create_news_provider

  provider = create_news_provider("null")
  provider = create_news_provider("csv", csv_path="news.csv")
  provider = create_news_provider("live")

  news = provider.get(candle_timestamp)
  # → {"overall_sentiment": 0.0, "news_count": 0, "top_headlines_summary": "..."}
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

NewsDict = dict

_NEUTRAL: NewsDict = {
    "overall_sentiment":     0.0,
    "news_count":            0,
    "top_headlines_summary": "No news data available.",
}


class NewsProvider(ABC):
    @abstractmethod
    def get(self, candle_ts: pd.Timestamp) -> NewsDict: ...

    @property
    def source_name(self) -> str:
        return self.__class__.__name__


class NullNewsProvider(NewsProvider):
    """Return neutral (0.0) เสมอ — LLM จะพึ่ง technical indicators อย่างเดียว"""

    def __init__(self, log: bool = True):
        if log:
            logger.info("NullNewsProvider: sentiment=0.0 for all candles")

    def get(self, candle_ts: pd.Timestamp) -> NewsDict:
        return dict(_NEUTRAL)


class CSVNewsProvider(NewsProvider):
    """
    โหลด news sentiment จาก CSV pre-processed
    คืน sentiment ใน lookback window ก่อน candle timestamp
    """

    def __init__(self, csv_path: str, window_hours: int = 4,
                 timestamp_col: str = "published_at"):
        self.window_hours   = window_hours
        self._window        = pd.Timedelta(hours=window_hours)
        self._timestamp_col = timestamp_col
        self.df: Optional[pd.DataFrame] = None

        if csv_path and os.path.exists(csv_path):
            self._load(csv_path)
        else:
            logger.warning(f"CSVNewsProvider: '{csv_path}' not found → fallback neutral")

    def _load(self, path: str):
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
            df.columns = df.columns.str.strip()
            if self._timestamp_col not in df.columns:
                for alias in ("timestamp", "time", "date", "published"):
                    if alias in df.columns:
                        df = df.rename(columns={alias: self._timestamp_col})
                        break
            df[self._timestamp_col] = pd.to_datetime(
                df[self._timestamp_col], utc=True, errors="coerce"
            )
            df = df.dropna(subset=[self._timestamp_col])
            self.df = df.sort_values(self._timestamp_col).reset_index(drop=True)
            logger.info(f"✓ CSVNewsProvider: {len(df):,} rows | window={self.window_hours}h")
        except Exception as e:
            logger.error(f"CSVNewsProvider load failed: {e}")

    def get(self, candle_ts: pd.Timestamp) -> NewsDict:
        if self.df is None:
            return dict(_NEUTRAL)

        ts_utc = _to_utc(candle_ts)
        mask   = (
            (self.df[self._timestamp_col] >= ts_utc - self._window) &
            (self.df[self._timestamp_col] <= ts_utc)
        )
        subset = self.df[mask]
        if subset.empty:
            earlier = self.df[self.df[self._timestamp_col] <= ts_utc]
            if earlier.empty:
                return dict(_NEUTRAL)
            subset = earlier.tail(1)

        row      = subset.iloc[-1]
        sentiment = float(row.get("overall_sentiment", 0.0))
        count    = int(row.get("news_count", 0))
        headline = str(row.get("top_headlines_summary", "")).strip()
        if not headline or headline.lower() == "nan":
            headline = f"Sentiment: {sentiment:+.4f} ({count} articles)"
        return {
            "overall_sentiment":     round(sentiment, 4),
            "news_count":            count,
            "top_headlines_summary": headline[:300],
        }

    @property
    def source_name(self) -> str:
        return f"CSVNewsProvider(window={self.window_hours}h)"


class LiveNewsProvider(NewsProvider):
    """
    ดึง sentiment จาก GoldNewsFetcher production
    ถ้า import ไม่ได้ → fallback neutral อัตโนมัติ
    """

    def __init__(self, cache_minutes: int = 30):
        self._cache_minutes = cache_minutes
        self._fetcher       = None
        self._cached:    Optional[NewsDict]     = None
        self._cached_ts: Optional[pd.Timestamp] = None

        try:
            from data_engine.newsfetcher import GoldNewsFetcher
            self._fetcher = GoldNewsFetcher()
            logger.info(f"✓ LiveNewsProvider ready (cache={cache_minutes}min)")
        except ImportError:
            logger.warning("LiveNewsProvider: GoldNewsFetcher not found → neutral fallback")

    def get(self, candle_ts: pd.Timestamp) -> NewsDict:
        if self._fetcher is None:
            return dict(_NEUTRAL)
        if self._cached and self._cached_ts:
            age = abs((pd.Timestamp.now(tz="UTC") - self._cached_ts).total_seconds())
            if age < self._cache_minutes * 60:
                return dict(self._cached)
        try:
            raw = self._fetcher.fetch_news_sentiment()
            result: NewsDict = {
                "overall_sentiment":     float(raw.get("overall_sentiment", 0.0)),
                "news_count":            int(raw.get("news_count", 0)),
                "top_headlines_summary": str(raw.get("top_headlines_summary", ""))[:300],
            }
            self._cached    = result
            self._cached_ts = pd.Timestamp.now(tz="UTC")
            return dict(result)
        except Exception as e:
            logger.error(f"LiveNewsProvider.get() error: {e}")
            return dict(_NEUTRAL)

    @property
    def source_name(self) -> str:
        ok = self._fetcher is not None
        return f"LiveNewsProvider({'active' if ok else 'fallback-neutral'})"


def create_news_provider(
    mode: str = "null",
    csv_path: str = "",
    window_hours: int = 4,
    live_cache_minutes: int = 30,
) -> NewsProvider:
    """
    Factory สร้าง NewsProvider
    mode: "null" | "csv" | "live"
    """
    mode = mode.lower().strip()
    if mode == "null":
        return NullNewsProvider()
    elif mode == "csv":
        if not csv_path:
            logger.warning("create_news_provider: mode=csv ไม่มี csv_path → NullNewsProvider")
            return NullNewsProvider(log=False)
        return CSVNewsProvider(csv_path, window_hours)
    elif mode == "live":
        return LiveNewsProvider(live_cache_minutes)
    else:
        logger.warning(f"create_news_provider: unknown mode '{mode}' → NullNewsProvider")
        return NullNewsProvider(log=False)


def _to_utc(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
