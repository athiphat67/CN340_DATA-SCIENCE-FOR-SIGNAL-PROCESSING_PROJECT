import logging

logger = logging.getLogger(__name__)


def get_deep_news_by_category(category: str) -> dict:
    """
    🔄 WRAPPER: ดึงข่าวเจาะลึกตามหมวดหมู่ (Backward compatible)
    
    THIS IS NOW A WRAPPER that calls merged fetch_news() from data_engine/tools
    
    Categories ที่รองรับ: "gold_price", "usd_thb", "fed_policy", "inflation", 
    "geopolitics", "dollar_index", "thai_economy", "thai_gold_market"
    
    ✅ Maintains the same input/output as before
    ✅ But now uses shared merged fetch_news() underneath
    """
    logger.info(f"🔍 [TOOL] get_deep_news_by_category: {category}")
    
    # ─────────────────────────────────────────────────────────────
    # Import merged fetch_news from data_engine
    # ─────────────────────────────────────────────────────────────
    try:
        from data_engine.tools.fetch_news import fetch_news as fetch_news_merged
    except ImportError:
        logger.error("[TOOL] Failed to import merged fetch_news from data_engine.tools")
        return {
            "status": "error",
            "message": "Could not load news fetcher - import failed"
        }
    
    # ─────────────────────────────────────────────────────────────
    # Call merged fetch_news with deep dive parameters
    # ─────────────────────────────────────────────────────────────
    try:
        result = fetch_news_merged(
            max_per_category=5,
            category_filter=category,
            detail_level="deep"
        )
        
        # ─────────────────────────────────────────────────────────────
        # Transform result to maintain backward compatibility
        # ─────────────────────────────────────────────────────────────
        if "deep_news" in result and result.get("error") is None:
            return {
                "status": "success",
                "category": category,
                "articles": result["deep_news"].get("articles", []),
                "count": result["deep_news"].get("count", 0)
            }
        elif "deep_news_error" in result:
            return {
                "status": "error",
                "message": result.get("deep_news_error", "Unknown error")
            }
        else:
            # Fallback if structure is different
            return {
                "status": "success",
                "category": category,
                "articles": [],
                "count": 0,
                "note": "No articles found for this category"
            }
            
    except Exception as e:
        logger.error(f"Error in get_deep_news_by_category: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


def check_upcoming_economic_calendar(hours_ahead: int = 24) -> dict:
    """
    เช็คปฏิทินเศรษฐกิจ (Economic Calendar) ล่วงหน้า
    เพื่อหา "ข่าวกล่องแดง" (High Impact) เช่น Non-Farm (NFP), CPI, การประชุม FOMC
    เหตุผลที่ LLM ควรใช้: หากใกล้เวลาข่าวออก เอเจนต์ควรหลีกเลี่ยงการเข้าเทรด หรือตัดสินใจปิดออเดอร์เพื่อลดความเสี่ยง
    """
    return {"status": "not_implemented", "message": "รอการพัฒนาเพิ่มเติม"}


def get_intermarket_correlation() -> dict:
    """
    ตรวจสอบความสัมพันธ์ข้ามตลาด (Intermarket Analysis)
    ดึงข้อมูลดัชนีดอลลาร์ (DXY) และผลตอบแทนพันธบัตรรัฐบาลสหรัฐอายุ 10 ปี (US10Y)
    เหตุผลที่ LLM ควรใช้: ทองคำมักวิ่งสวนทางกับ DXY และ US10Y ถ้าราคาทองขึ้นแต่ DXY ก็ขึ้นด้วย แสดงว่ามีความผิดปกติ
    """
    return {"status": "not_implemented", "message": "รอการพัฒนาเพิ่มเติม"}


def check_fed_speakers_schedule() -> dict:
    """
    ตรวจสอบตารางการให้สัมภาษณ์ของคณะกรรมการธนาคารกลางสหรัฐ (Fed Speakers) ประจำวัน
    เหตุผลที่ LLM ควรใช้: คำพูดหลุดกรอบ (Hawkish/Dovish) นอกตาราง มักทำให้ทองคำสวิงรุนแรงโดยไม่มีกราฟเตือนล่วงหน้า
    """
    return {"status": "not_implemented", "message": "รอการพัฒนาเพิ่มเติม"}


def get_institutional_positioning() -> dict:
    """
    ดึงข้อมูล COT Report (Commitments of Traders) ที่ออกรายสัปดาห์
    ดูว่ากองทุนและสถาบันใหญ่ๆ มีสถานะ Net Long หรือ Net Short ทองคำอยู่เท่าไหร่
    เหตุผลที่ LLM ควรใช้: ใช้ประเมินเทรนด์ระยะกลาง-ยาว เพื่อดูว่าตลาดมีมุมมอง (Bias) ไปทางไหน
    """
    return {"status": "not_implemented", "message": "รอการพัฒนาเพิ่มเติม"}