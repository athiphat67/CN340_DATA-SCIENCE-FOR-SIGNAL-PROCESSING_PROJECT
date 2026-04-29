import asyncio
import os
from dotenv import load_dotenv

# โหลด API Keys จากไฟล์ .env ของเธอ
load_dotenv()

# ดึงฟังก์ชันมาจากไฟล์ fundamental_tools ที่เราเขียนไว้
from data_engine.analysis_tools.fundamental_tools import _fetch_from_apify, _fetch_from_alpha_vantage

async def run_tests():
    print("=== 🚀 เริ่มทดสอบดึงข่าว 2 ระบบ ===")
    test_category = "gold_price" # ลองเทสด้วยหมวดราคาทองคำ

    # ---------------------------------------------------------
    # 🧪 เทสที่ 1: Apify (ก๊อก 1)
    # ---------------------------------------------------------
    print("\n🔵 กำลังทดสอบก๊อกที่ 1: Apify...")
    try:
        apify_result = await _fetch_from_apify(test_category)
        if apify_result:
            print(f"✅ [SUCCESS] Apify ผ่าน! ดึงข่าวมาได้ {len(apify_result)} หัวข้อ")
            print(f"📰 ตัวอย่างข่าวแรก: {apify_result[0].get('title', '')[:100]}...")
        else:
            print("⚠️ ดึงได้ 0 ข่าว (อาจจะต้องเช็ก search_terms)")
    except Exception as e:
        print(f"❌ [FAILED] Apify พัง! สาเหตุ: {e}")

    # ---------------------------------------------------------
    # 🧪 เทสที่ 2: Alpha Vantage (ก๊อก 2)
    # ---------------------------------------------------------
    print("\n🟠 กำลังทดสอบก๊อกที่ 2: Alpha Vantage...")
    try:
        av_result = await _fetch_from_alpha_vantage(test_category)
        if av_result:
            print(f"✅ [SUCCESS] Alpha Vantage ผ่าน! ดึงข่าวมาได้ {len(av_result)} หัวข้อ")
            print(f"📰 ตัวอย่างข่าวแรก: {av_result[0].get('title', '')[:100]}...")
        else:
            print("⚠️ ดึงได้ 0 ข่าว (อาจจะชน Limit 25 ครั้ง/วัน)")
    except Exception as e:
        print(f"❌ [FAILED] Alpha Vantage พัง! สาเหตุ: {e}")
        
    print("\n=== ✨ จบการทดสอบ ===")

if __name__ == "__main__":
    asyncio.run(run_tests())