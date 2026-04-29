import os
import asyncio
import httpx
from dotenv import load_dotenv
from apify_client import ApifyClient

# โหลดค่าคีย์ต่างๆ จากไฟล์ .env
load_dotenv()

async def test_apify():
    print("⏳ [1/2] กำลังทดสอบก๊อก 1: Apify (จำกัด 2 ข่าวเพื่อให้เทสเสร็จไว)...")
    try:
        token = os.getenv('APIFY_API_TOKEN')
        if not token:
            print("❌ ไม่พบ APIFY_API_TOKEN ในไฟล์ .env")
            return
            
        client = ApifyClient(token)
        run_input = {"searchTerms": ["Gold Price"], "maxItems": 2}
        
        # สั่งรัน Actor
        run = await asyncio.to_thread(client.actor("mscraper/investing-news-scraper").call, run_input=run_input)
        items = list(await asyncio.to_thread(client.dataset(run["defaultDatasetId"]).iterate_items))
        
        if items:
            title = items[0].get('title', 'No Title')[:40]
            print(f"✅ Apify รอด! ได้ข่าวมา {len(items)} ชิ้น (ตย. หัวข้อ: '{title}...')")
        else:
            print("⚠️ Apify ผ่าน แต่หาข่าวไม่เจอ ลองเช็กโควต้าในเว็บดูนะ")
    except Exception as e:
        print(f"❌ Apify พัง สาเหตุ: {e}")

async def test_alpha_vantage():
    print("⏳ [2/2] กำลังทดสอบก๊อก 2: Alpha Vantage (Fallback)...")
    try:
        av_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not av_key:
            print("❌ ไม่พบ ALPHA_VANTAGE_API_KEY ในไฟล์ .env")
            return
            
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&topics=financial_markets&limit=2&apikey={av_key}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            data = response.json()
            
        if "feed" in data:
            title = data['feed'][0].get('title', 'No Title')[:40]
            print(f"✅ Alpha Vantage รอด! ได้ข่าวมา {len(data['feed'])} ชิ้น (ตย. หัวข้อ: '{title}...')")
        else:
            msg = data.get('Information', data.get('Note', 'Error หรือโควต้าเต็ม'))
            print(f"❌ Alpha Vantage ตีกลับ: {msg}")
    except Exception as e:
        print(f"❌ Alpha Vantage พัง สาเหตุ: {e}")

async def main():
    print("🚀 เริ่มการทดสอบระบบ News Pipeline...")
    print("-" * 50)
    await test_apify()
    print("-" * 50)
    await test_alpha_vantage()
    print("-" * 50)
    print("🏁 จบการทดสอบ (ถ้าขึ้น ✅ ทั้งคู่ แปลว่าพร้อมลุย Phase 2!)")

if __name__ == "__main__":
    asyncio.run(main())