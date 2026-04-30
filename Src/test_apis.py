import asyncio
import os
from dotenv import load_dotenv

# โหลด .env ก่อน
load_dotenv()

# ดึงพนักงานจัดกล่องพัสดุ (Smart Engine) ของเรามาเทส
from data_engine.tools.fetch_news import fetch_news

async def test_smart_engine():
    print("🚀 เริ่มทดสอบ Smart News Engine (Radar + Sniper)...")
    
    # จำลองสถานการณ์ว่าระบบหลัก (Orchestrator) สั่งขอข่าวทองคำแบบ Deep
    result = await fetch_news(
        max_per_category=5, 
        category_filter="gold", 
        detail_level="deep"
    )
    
    print("\n📊 --- สรุปผลที่ได้ ---")
    if result.get("error"):
        print(f"❌ มีเออเร่อเกิดขึ้น: {result['error']}")
        return

    print(f"✅ จำนวนข่าวทั้งหมดที่ดึงได้: {result['summary']['total_articles']} ข่าว")
    
    if 'deep_news' in result and 'articles' in result['deep_news']:
        print("\n📰 --- ตัวอย่างข่าว (เช็ก Source) ---")
        for i, article in enumerate(result['deep_news']['articles'][:5], 1):
            source = article.get('source', 'Unknown')
            title = article.get('title', 'No Title')
            
            # โชว์ให้เห็นเลยว่าข่าวมาจากก๊อกไหน!
            if "Alpha" in source:
                score = article.get('alpha_score', 0)
                print(f"{i}. 🎯 [SNIPER: {source}] (Sentiment: {score}) | {title}")
            else:
                print(f"{i}. 📡 [RADAR: {source}] | {title}")
    else:
        print("⚠️ ไม่พบข้อมูลข่าวในกล่อง deep_news")

if __name__ == "__main__":
    asyncio.run(test_smart_engine())