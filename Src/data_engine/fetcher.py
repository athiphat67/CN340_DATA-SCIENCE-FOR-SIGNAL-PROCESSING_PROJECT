"""
data_engine/fetcher.py
Fetches raw gold price data and macro news from external APIs.
"""

import os
import logging
import requests
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"


class DataFetcher:
    # ------------------------------------------------------------------
    # Price data
    # ------------------------------------------------------------------
    def get_gold_data(self, period: str = "7d", interval: str = "1h") -> pd.DataFrame:
        """
        Download OHLCV data for Gold Futures (GC=F) via yfinance.
        Falls back to XAU/USD spot if futures data is unavailable.
        """
        for ticker in ("GC=F", "XAUUSD=X"):
            try:
                df = yf.Ticker(ticker).history(period=period, interval=interval)
                if not df.empty:
                    logger.info(f"[Fetcher] Got {len(df)} candles from {ticker}")
                    df.index = pd.to_datetime(df.index, utc=True)
                    return df[["Open", "High", "Low", "Close", "Volume"]]
            except Exception as e:
                logger.warning(f"[Fetcher] {ticker} failed: {e}")

        logger.error("[Fetcher] All tickers failed — returning empty DataFrame")
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # News data
    # ------------------------------------------------------------------
    def get_macro_news(
        self,
        query: str = "gold price Fed interest rate inflation",
        page_size: int = 5,
    ) -> list[dict]:
        """
        Pull macro news headlines from NewsAPI.
        Falls back to mock data when the API key is absent or the call fails.
        """
        if not NEWS_API_KEY:
            logger.warning("[Fetcher] NEWS_API_KEY not set — using mock news")
            return self._mock_news()

        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": NEWS_API_KEY,
        }

        try:
            resp = requests.get(NEWS_API_URL, params=params, timeout=10)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            return [
                {
                    "title": a["title"],
                    "source": a["source"]["name"],
                    "published": a["publishedAt"],
                    "url": a["url"],
                }
                for a in articles
            ]
        except Exception as e:
            logger.error(f"[Fetcher] NewsAPI error: {e} — falling back to mock")
            return self._mock_news()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _mock_news() -> list[dict]:
        return [
            {
                "title": "Fed signals potential rate cuts amid cooling inflation",
                "source": "Reuters (mock)",
                "published": "2025-01-01T00:00:00Z",
                "url": "",
            },
            {
                "title": "Middle East tensions escalate, safe-haven demand rises",
                "source": "Bloomberg (mock)",
                "published": "2025-01-01T01:00:00Z",
                "url": "",
            },
            {
                "title": "Dollar weakens after disappointing jobs data",
                "source": "CNBC (mock)",
                "published": "2025-01-01T02:00:00Z",
                "url": "",
            },
        ]
