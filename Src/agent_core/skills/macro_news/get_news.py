"""
agent_core/skills/macro_news/get_news.py

Tool function: get_macro_news(topic)

Design rules:
- Loaded lazily — import cost only paid when the agent actually calls it.
- Returns a plain-text string (not JSON) so the LLM can read it directly.
- Never raises; always returns a usable string so the ReAct loop continues.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# Simple keyword → sentiment mapping used for the summary line
_BULLISH_KEYWORDS = {
    "rate cut", "dovish", "quantitative easing", "qe", "war", "conflict",
    "tension", "sanction", "recession", "risk-off", "safe haven",
    "central bank buying", "geopolit",
}
_BEARISH_KEYWORDS = {
    "rate hike", "hawkish", "strong dollar", "ceasefire", "deal",
    "strong jobs", "gdp beat", "risk-on", "sell-off",
}


def get_macro_news(topic: str) -> str:
    """
    Fetch top macro headlines for `topic` and return a human-readable
    summary with a sentiment label for each headline.

    Called by the orchestrator's ReAct loop via AVAILABLE_TOOLS.
    """
    articles = _fetch_articles(topic)

    if not articles:
        return (
            f"No live news found for '{topic}'. "
            "Assume neutral macro backdrop; rely on technical indicators only."
        )

    lines = [f"📰 Macro news for: '{topic}'\n"]
    bull, bear, neutral = 0, 0, 0

    for i, art in enumerate(articles, 1):
        title     = art.get("title", "")
        source    = art.get("source", {}).get("name", "Unknown")
        published = art.get("publishedAt", "")[:10]  # date only

        sentiment, label = _classify(title)
        if sentiment == 1:
            bull += 1
        elif sentiment == -1:
            bear += 1
        else:
            neutral += 1

        lines.append(f"{i}. [{label}] {title}  ({source}, {published})")

    # Overall bias
    if bull > bear:
        overall = "🟢 BULLISH — macro environment favours higher gold prices."
    elif bear > bull:
        overall = "🔴 BEARISH — macro environment may pressure gold lower."
    else:
        overall = "⚪ NEUTRAL — mixed signals; rely on technicals."

    lines.append(f"\nOverall sentiment: {overall}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_articles(topic: str) -> list[dict]:
    if not NEWS_API_KEY:
        logger.warning("[get_macro_news] NEWS_API_KEY not set — returning mock data")
        return _mock_articles(topic)

    try:
        resp = requests.get(
            NEWS_API_URL,
            params={
                "q": topic,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 5,
                "apiKey": NEWS_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("articles", [])
    except Exception as e:
        logger.error(f"[get_macro_news] NewsAPI request failed: {e}")
        return _mock_articles(topic)


def _classify(title: str) -> tuple[int, str]:
    """Returns (sentiment_score, label): +1=Bullish, -1=Bearish, 0=Neutral."""
    lower = title.lower()
    if any(k in lower for k in _BULLISH_KEYWORDS):
        return 1, "BULLISH ↑"
    if any(k in lower for k in _BEARISH_KEYWORDS):
        return -1, "BEARISH ↓"
    return 0, "NEUTRAL —"


def _mock_articles(topic: str) -> list[dict]:
    return [
        {
            "title": "Fed signals potential rate cuts amid cooling inflation",
            "source": {"name": "Reuters (mock)"},
            "publishedAt": "2025-01-01",
        },
        {
            "title": "Middle East tensions escalate, safe-haven demand rises",
            "source": {"name": "Bloomberg (mock)"},
            "publishedAt": "2025-01-01",
        },
        {
            "title": "Dollar weakens after disappointing jobs data",
            "source": {"name": "CNBC (mock)"},
            "publishedAt": "2025-01-01",
        },
    ]
