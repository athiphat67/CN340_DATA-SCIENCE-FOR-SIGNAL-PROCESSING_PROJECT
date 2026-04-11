import logging
from data_engine.newsfetcher import GoldNewsFetcher

logger = logging.getLogger(__name__)

def get_deep_news_by_category(category: str) -> dict:
    """
    ใช้เมื่อต้องการเจาะลึกดูหัวข้อข่าวและรายละเอียดของหมวดหมู่นั้นๆ 
    (เนื่องจากข้อมูลตั้งต้นมีแค่สรุป Sentiment)
    
    Categories ที่รองรับ: "gold_price", "usd_thb", "fed_policy", "inflation", 
    "geopolitics", "dollar_index", "thai_economy", "thai_gold_market"
    """
    logger.info(f"🔍 [TOOL] LLM ร้องขอข้อมูลข่าวเจาะลึกหมวด: {category}")
    
    try:
        # สร้าง Instance ของ Fetcher
        fetcher = GoldNewsFetcher(max_per_category=5)
        
        # เรียกใช้ฟังก์ชัน fetch_category ที่มีอยู่แล้วใน newsfetcher.py
        articles = fetcher.fetch_category(category)
        
        if not articles:
            return {"status": "success", "message": f"ไม่มีข่าวใหม่ในหมวด {category} วันนี้"}
            
        # สกัดเอาเฉพาะข้อมูลที่ LLM ควรอ่านเพื่อวิเคราะห์เจาะลึก
        deep_news_data = []
        for a in articles:
            deep_news_data.append({
                "title": a.title,
                "source": a.source,
                "impact_level": a.impact_level,
                # ไม่ต้องส่ง URL หรือ Token estimate ไปให้ LLM มันรก
            })
            
        return {
            "status": "success",
            "category": category,
            "articles": deep_news_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching deep news for {category}: {e}")
        return {"status": "error", "message": str(e)}

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