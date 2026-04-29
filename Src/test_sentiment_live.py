import asyncio
from dotenv import load_dotenv
load_dotenv()
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_engine.analysis_tools.fundamental_tools import (
    _fetch_from_apify,
    _fetch_from_alpha_vantage,
    _analyze_sentiment_router,
)

async def main():
    print("=" * 55)
    print("TEST: Sentiment บนข่าวจริง")
    print("=" * 55)

    # ── Google News RSS ──────────────────────────────────────
    print("\n📡 ดึงข่าวจาก Google News RSS...")
    rss_articles = await _fetch_from_apify("gold")
    print(f"   ได้ {len(rss_articles)} ข่าว")
    for a in rss_articles:
        print(f"   📰 {a['title'][:60]}")

    print("\n🧠 วิเคราะห์ Sentiment (Google News RSS)...")
    rss_score = await _analyze_sentiment_router(rss_articles)
    label = "🟢 Bullish" if rss_score > 0.1 else ("🔴 Bearish" if rss_score < -0.1 else "⚪ Neutral")
    print(f"   {label} | Score: {rss_score:+.4f}")

    print("\n" + "=" * 55)

    # ── Alpha Vantage ─────────────────────────────────────────
    print("\n📡 ดึงข่าวจาก Alpha Vantage...")
    try:
        av_articles = await _fetch_from_alpha_vantage("gold_price")
        print(f"   ได้ {len(av_articles)} ข่าว")
        for a in av_articles[:5]:
            print(f"   📰 {a['title'][:60]}")

        print("\n🧠 วิเคราะห์ Sentiment (Alpha Vantage)...")
        av_score = await _analyze_sentiment_router(av_articles)
        label = "🟢 Bullish" if av_score > 0.1 else ("🔴 Bearish" if av_score < -0.1 else "⚪ Neutral")
        print(f"   {label} | Score: {av_score:+.4f}")
    except Exception as e:
        print(f"   ❌ {e}")

    print("\n" + "=" * 55)
    print("✅ ทดสอบเสร็จ")

asyncio.run(main())