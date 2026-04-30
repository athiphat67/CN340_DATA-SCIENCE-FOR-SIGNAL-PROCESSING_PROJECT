"""
tools/fetch_news.py — Tool: ดึงข่าวทองคำ (SMART ENGINE)
อัปเกรด: ใช้ระบบ Radar (Finnhub+RSS) + Sniper (Alpha Vantage) ตามเวลาตลาด
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime

# 🟢 นำเข้าสมองกลผู้จัดการข่าวของเรา จาก fundamental_tools 
from data_engine.analysis_tools.fundamental_tools import fetch_all_news_smart

logger = logging.getLogger(__name__)

TOOL_NAME = "fetch_news"
TOOL_DESCRIPTION = (
    "ดึงข่าวทองคำล่าสุดแบบ Hybrid: ใช้ Finnhub (Real-time) ผสมผสานกับ Alpha Vantage (Deep Sentiment) "
    "ระบบจะดึงข่าวตามความสำคัญของ Market Sessions หากมี alpha_score มาด้วย ให้ Weight ข่าวนั้นสูงกว่าปกติ"
)

async def fetch_news(
    max_per_category: int = 5,
    category_filter: Optional[str] = None,
    detail_level: str = "summary",
) -> dict:
    """
    ดึงข่าวโดยใช้ระบบ fetch_all_news_smart ที่เราเพิ่งสร้างขึ้น
    """
    search_query = category_filter if category_filter else "gold"
    logger.info(f"[fetch_news] 🚀 ดึงข่าวแบบ Smart ASYNC (Target: {search_query})...")

    try:
        # 1. ปล่อยให้สมองกลของเราไปดึงข่าวมา (มันจะเช็กเวลาให้เองว่าจะใช้ Alpha ไหม)
        articles = await fetch_all_news_smart(search_query)
        total_articles = len(articles)

        # 2. ห่อกล่องพัสดุให้หน้าตาเหมือนเดิม (Orchestrator จะได้ไม่งง)
        result = {
            "summary": {
                "total_articles": total_articles,
                "overall_sentiment": 0.0, # เราจะปล่อยให้ Gemini เป็นคนชั่งน้ำหนักเอง
                "fetched_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "errors": [],
            },
            "by_category": {
                search_query: articles
            },
            "error": None,
        }

        # 3. ถ้าระบบหลักขอแบบเจาะลึก
        if detail_level == "deep":
            result["deep_news"] = {
                "category": search_query,
                "count": total_articles,
                "articles": articles
            }

        logger.info(f"[fetch_news] ✅ ดึงข่าวสำเร็จ — ได้มาทั้งหมด {total_articles} ข่าว")
        return result

    except Exception as e:
        logger.error(f"[fetch_news] ❌ Smart News Engine พัง: {e}")
        return {
            "summary": {
                "total_articles": 0,
                "overall_sentiment": 0.0,
                "errors": [str(e)],
            },
            "by_category": {},
            "error": str(e),
        }