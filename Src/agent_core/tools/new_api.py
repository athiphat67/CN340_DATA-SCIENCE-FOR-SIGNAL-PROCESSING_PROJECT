import json
import random
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# Mock news database — จำลอง API response ที่สมจริง
# ---------------------------------------------------------------------------

_MOCK_NEWS_POOL = [
    # Bullish news
    {
        "headline": "Fed signals potential rate cut in Q3 amid cooling inflation",
        "source": "Reuters",
        "sentiment": "bullish",
        "theme": "monetary_policy",
        "summary": "Federal Reserve officials hinted at easing monetary policy as inflation data improved.",
        "impact_score": 0.85,
    },
    {
        "headline": "Gold ETF inflows hit 6-month high as investors seek safe haven",
        "source": "Bloomberg",
        "sentiment": "bullish",
        "theme": "supply_demand",
        "summary": "Capital flow into gold-backed ETFs surged to highest level since September.",
        "impact_score": 0.72,
    },
    {
        "headline": "Middle East tensions escalate, boosting demand for safe-haven assets",
        "source": "AP",
        "sentiment": "bullish",
        "theme": "geopolitical",
        "summary": "Geopolitical risk premium rising as conflict in the region intensifies.",
        "impact_score": 0.78,
    },
    {
        "headline": "Dollar weakens after disappointing US jobs report",
        "source": "Financial Times",
        "sentiment": "bullish",
        "theme": "fx_macro",
        "summary": "DXY fell 0.6% after non-farm payrolls missed expectations significantly.",
        "impact_score": 0.80,
    },
    {
        "headline": "Central banks globally increase gold reserves for third consecutive quarter",
        "source": "World Gold Council",
        "sentiment": "bullish",
        "theme": "central_bank",
        "summary": "Net buying from central banks reached 228 tonnes in Q1 2025.",
        "impact_score": 0.90,
    },
    # Bearish news
    {
        "headline": "Fed chair signals no rate cuts until inflation sustainably hits 2%",
        "source": "WSJ",
        "sentiment": "bearish",
        "theme": "monetary_policy",
        "summary": "Hawkish Fed stance dampens gold outlook as real yields remain elevated.",
        "impact_score": -0.88,
    },
    {
        "headline": "Dollar surges to 3-month high on strong US economic data",
        "source": "Reuters",
        "sentiment": "bearish",
        "theme": "fx_macro",
        "summary": "DXY climbed sharply after GDP beat expectations, pressuring commodities.",
        "impact_score": -0.75,
    },
    {
        "headline": "Gold ETF outflows accelerate as risk appetite returns",
        "source": "Bloomberg",
        "sentiment": "bearish",
        "theme": "supply_demand",
        "summary": "Investors rotate out of defensive assets into equities amid stock market rally.",
        "impact_score": -0.65,
    },
    # Neutral news
    {
        "headline": "Gold price steady ahead of key US inflation data release",
        "source": "MarketWatch",
        "sentiment": "neutral",
        "theme": "other",
        "summary": "Traders cautious ahead of CPI print expected Thursday.",
        "impact_score": 0.05,
    },
    {
        "headline": "Analysts divided on gold outlook for H2 2025",
        "source": "Kitco",
        "sentiment": "neutral",
        "theme": "other",
        "summary": "Major banks split between bullish and bearish targets ranging $2,800–$3,200.",
        "impact_score": 0.0,
    },
]

# Keyword → theme mapping
_KEYWORD_THEME_MAP = {
    "fed":          "monetary_policy",
    "rate":         "monetary_policy",
    "interest":     "monetary_policy",
    "inflation":    "monetary_policy",
    "cpi":          "monetary_policy",
    "dollar":       "fx_macro",
    "dxy":          "fx_macro",
    "currency":     "fx_macro",
    "gold":         "supply_demand",
    "etf":          "supply_demand",
    "demand":       "supply_demand",
    "war":          "geopolitical",
    "conflict":     "geopolitical",
    "geopolitical": "geopolitical",
    "central bank": "central_bank",
    "reserve":      "central_bank",
}

_SENTIMENT_WEIGHTS = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _match_keywords(news_item: dict, keywords: list[str]) -> bool:
    """คืน True ถ้าข่าวนี้เกี่ยวข้องกับ keywords ที่ค้นหา"""
    text = (news_item["headline"] + " " + news_item["summary"]).lower()
    for kw in keywords:
        if kw.lower() in text:
            return True
    # ถ้า keyword map กับ theme ให้ match theme ด้วย
    for kw in keywords:
        mapped_theme = _KEYWORD_THEME_MAP.get(kw.lower())
        if mapped_theme and mapped_theme == news_item.get("theme"):
            return True
    return False


def _compute_composite_sentiment(results: list[dict]) -> float:
    """คำนวณ composite sentiment จากน้ำหนัก impact_score"""
    if not results:
        return 0.0
    total_impact = sum(r["impact_score"] for r in results)
    normalised = max(-1.0, min(1.0, total_impact / (len(results) * 0.9)))
    return round(normalised, 4)


def _get_dominant_theme(results: list[dict]) -> str:
    from collections import Counter
    if not results:
        return "other"
    themes = [r.get("theme", "other") for r in results]
    return Counter(themes).most_common(1)[0][0]


def _add_timestamp(news_item: dict, index: int) -> dict:
    """เพิ่ม published_at จำลอง (ล่าสุดก่อน)"""
    base = datetime.now(timezone.utc)
    offset = timedelta(hours=index * 2 + random.randint(0, 60))
    item = dict(news_item)
    item["published_at"] = (base - offset).strftime("%Y-%m-%dT%H:%M:%SZ")
    return item


# ---------------------------------------------------------------------------
# Main function — เรียกโดย orchestrator
# ---------------------------------------------------------------------------

def get_news(
    keywords: list[str],
    max_results: int = 5,
    language: str = "en",
    use_mock: bool = True,
) -> dict:
    """
    ดึงข่าวตาม keywords ที่กำหนด

    Args:
        keywords    : คำค้นหา เช่น ["FED", "gold price", "inflation"]
        max_results : จำนวนข่าวสูงสุดที่ต้องการ
        language    : "en" หรือ "th" (mock รองรับ "en" เท่านั้นตอนนี้)
        use_mock    : True = ใช้ mock data | False = ต่อ API จริง

    Returns:
        dict ที่มี results, composite_sentiment, dominant_theme
    """
    if use_mock:
        return _fetch_mock(keywords, max_results)
    else:
        return _fetch_live(keywords, max_results, language)


def _fetch_mock(keywords: list[str], max_results: int) -> dict:
    """Mock mode — กรองจาก _MOCK_NEWS_POOL ตาม keywords"""

    # กรองข่าวที่เกี่ยวข้อง
    matched = [
        news for news in _MOCK_NEWS_POOL
        if _match_keywords(news, keywords)
    ]

    # ถ้าไม่เจอเลย ใช้ข่าว neutral แทน
    if not matched:
        matched = [n for n in _MOCK_NEWS_POOL if n["sentiment"] == "neutral"]

    # จำกัดจำนวนและสุ่มให้ดูสมจริง (เรียงล่าสุดก่อน)
    random.shuffle(matched)
    selected = matched[:max_results]

    # เพิ่ม timestamp
    results = [_add_timestamp(item, i) for i, item in enumerate(selected)]

    # Statistics
    sentiments = [r["sentiment"] for r in results]
    bullish_count = sentiments.count("bullish")
    bearish_count = sentiments.count("bearish")
    neutral_count = sentiments.count("neutral")

    composite = _compute_composite_sentiment(results)
    dominant  = _get_dominant_theme(results)

    return {
        "tool":                "get_news",
        "status":              "success",
        "mode":                "mock",
        "keywords_used":       keywords,
        "results":             results,
        "composite_sentiment": composite,
        "dominant_theme":      dominant,
        "bullish_count":       bullish_count,
        "bearish_count":       bearish_count,
        "neutral_count":       neutral_count,
        "total_fetched":       len(results),
    }


def _fetch_live(keywords: list[str], max_results: int, language: str) -> dict:
    """
    Production mode — ต่อ NewsAPI จริง
    ต้องตั้ง environment variable: NEWS_API_KEY
    """
    import os
    import urllib.request
    import urllib.parse

    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        return {
            "tool":   "get_news",
            "status": "error",
            "error":  "NEWS_API_KEY environment variable not set",
        }

    query = " OR ".join(keywords)
    params = urllib.parse.urlencode({
        "q":        query,
        "language": language,
        "pageSize": max_results,
        "sortBy":   "publishedAt",
        "apiKey":   api_key,
    })
    url = f"https://newsapi.org/v2/everything?{params}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        articles = data.get("articles", [])
        results = []
        for art in articles:
            results.append({
                "headline":    art.get("title", ""),
                "source":      art.get("source", {}).get("name", "unknown"),
                "sentiment":   "neutral",   # ต้องส่งผ่าน nlp_signals.py เพื่อ classify
                "theme":       "other",
                "summary":     art.get("description", ""),
                "impact_score": 0.0,
                "published_at": art.get("publishedAt", ""),
            })

        return {
            "tool":                "get_news",
            "status":              "success",
            "mode":                "live",
            "keywords_used":       keywords,
            "results":             results,
            "composite_sentiment": 0.0,   # ต้อง run nlp_signals เพิ่มเติม
            "dominant_theme":      "other",
            "note":                "sentiment ยังไม่ได้ classify — ส่งผ่าน nlp_signals.py",
        }

    except Exception as exc:
        return {
            "tool":   "get_news",
            "status": "error",
            "error":  str(exc),
        }


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    keywords = sys.argv[1:] if len(sys.argv) > 1 else ["FED", "gold", "inflation"]
    print(f"[get_news] Searching for: {keywords}")

    result = get_news(keywords=keywords, max_results=5, use_mock=True)

    print(f"\n[get_news] Status           : {result['status']}")
    print(f"[get_news] Composite sentiment: {result['composite_sentiment']:+.4f}")
    print(f"[get_news] Dominant theme     : {result['dominant_theme']}")
    print(f"[get_news] Bullish/Bearish/Neutral: "
          f"{result['bullish_count']}/{result['bearish_count']}/{result['neutral_count']}")
    print(f"\n[get_news] Headlines:")
    for i, art in enumerate(result["results"], 1):
        icon = {"bullish": "▲", "bearish": "▼", "neutral": "—"}.get(art["sentiment"], "?")
        print(f"  {i}. [{icon}] {art['headline']} — {art['source']}")