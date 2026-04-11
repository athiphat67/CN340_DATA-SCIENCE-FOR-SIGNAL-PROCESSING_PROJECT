"""
tools/fetch_news.py — Tool: ดึงข่าวทองคำ
ใช้ NewsFetcher (FinBERT sentiment + RSS) แล้วจัดรูปแบบสำหรับ LLM
"""

import logging

from data_engine.newsfetcher import GoldNewsFetcher

logger = logging.getLogger(__name__)

TOOL_NAME = "fetch_news"
TOOL_DESCRIPTION = (
    "ดึงข่าวทองคำล่าสุดจาก RSS feeds พร้อม sentiment analysis (FinBERT) "
    "แยกตาม category และสรุป overall sentiment score"
)

_news_fetcher_cache: dict[int, GoldNewsFetcher] = {}


def fetch_news(max_per_category: int = 5) -> dict:
    """
    ดึงข่าวทองคำและวิเคราะห์ sentiment

    Args:
        max_per_category: จำนวนข่าวสูงสุดต่อ category (default 5)

    Returns:
        dict: summary (total_articles, overall_sentiment, token_estimate), by_category, error
    """
    logger.info(f"[fetch_news] Fetching news (max_per_category={max_per_category})...")

    if max_per_category not in _news_fetcher_cache:
        _news_fetcher_cache[max_per_category] = GoldNewsFetcher(max_per_category=max_per_category)
    fetcher = _news_fetcher_cache[max_per_category]

    try:
        raw = fetcher.to_dict()
    except Exception as e:
        logger.error(f"[fetch_news] NewsFetcher failed: {e}")
        return {
            "summary":     {"total_articles": 0, "overall_sentiment": 0.0, "errors": [str(e)]},
            "by_category": {},
            "error":       str(e),
        }

    logger.info(
        f"[fetch_news] ✅ Done — {raw.get('total_articles', 0)} articles, "
        f"sentiment={raw.get('overall_sentiment', 0.0):.3f}"
    )

    return {
        "summary": {
            "total_articles":    raw.get("total_articles", 0),
            "token_estimate":    raw.get("token_estimate", 0),
            "overall_sentiment": raw.get("overall_sentiment", 0.0),
            "fetched_at":        raw.get("fetched_at", ""),
            "errors":            raw.get("errors", []),
        },
        "by_category": raw.get("by_category", {}),
        "error": None,
    }
