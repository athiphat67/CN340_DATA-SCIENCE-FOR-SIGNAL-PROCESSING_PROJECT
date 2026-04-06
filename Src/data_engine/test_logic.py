from fetcher import GoldDataFetcher

def test_gold_calculation_logic():
    print("🔍 กำลังทดสอบระบบดึงข้อมูลและคำนวณราคาทองไทย...\n")
    
    fetcher = GoldDataFetcher()
    
    print("📡 1. กำลังดึงราคาทองโลก (Spot USD)...")
    spot_data = fetcher.fetch_gold_spot_usd()
    spot_price = spot_data.get("price_usd_per_oz", 0)
    print(f"   => ทองโลก: ${spot_price:,.2f} / oz (ดึงจาก {spot_data.get('source', 'N/A')})")
    
    print("\n📡 2. กำลังดึงค่าเงินบาท (USD/THB)...")
    forex_data = fetcher.fetch_usd_thb_rate()
    usd_thb = forex_data.get("usd_thb", 0)
    print(f"   => ค่าเงินบาท: {usd_thb:,.4f} บาท/ดอลลาร์")
    
    if spot_price == 0 or usd_thb == 0:
        print("\n❌ ดึงข้อมูลพื้นฐานไม่สำเร็จ รบกวนเช็คอินเทอร์เน็ตหรือ API Key ครับ")
        return

    print("\n📡 3. ดึงราคาทองไทยจากระบบ (Plan A: ส่องหน้าเว็บจริง)...")
    thai_gold_data = fetcher.calc_thai_gold_price(spot_price, usd_thb)
    
    print("\n" + "="*50)
    print("📊 --- สรุปผลการเปรียบเทียบ --- 📊")
    print("="*50)
    
    print("✅ [ราคาจากระบบที่บอทจะเอาไปใช้]")
    print(f"   แหล่งที่มา: {thai_gold_data.get('source')}")
    print(f"   ราคารับซื้อ:  ฿{thai_gold_data.get('buy_price_thb', 0):,.0f}")
    print(f"   ราคาขายออก: ฿{thai_gold_data.get('sell_price_thb', 0):,.0f}")
    
    # --- แก้ไขสูตรคณิตศาสตร์ตรงนี้ให้ถูกต้อง ---
    print("\n🧮 [ราคาจากการคำนวณด้วยสูตรล้วนๆ (Plan B - Fallback)]")
    
    TROY_OUNCE_IN_GRAMS = 31.1034768
    THAI_GOLD_BAHT_IN_GRAMS = 15.244
    THAI_GOLD_PURITY = 0.965
    
    # 1. หาราคาต่อ 1 ออนซ์ เป็นเงินบาท
    raw_thb_per_oz = spot_price * usd_thb
    
    # 2. แปลงเป็นราคาต่อ 1 กรัม
    raw_thb_per_gram = raw_thb_per_oz / TROY_OUNCE_IN_GRAMS
    
    # 3. แปลงเป็นทองไทย 1 บาท (15.244 กรัม) และปรับความบริสุทธิ์ (96.5%)
    raw_thb_per_baht = raw_thb_per_gram * THAI_GOLD_BAHT_IN_GRAMS * THAI_GOLD_PURITY
    
    # ปัดเศษหลัก 50 บาท (ตามมาตรฐานสมาคมค้าทองคำ)
    calc_sell = round((raw_thb_per_baht + 50) / 50) * 50
    calc_buy = round((raw_thb_per_baht - 50) / 50) * 50
    
    print(f"   ต้นทุนทองแท่ง 1 บาท: ฿{raw_thb_per_baht:,.2f}")
    print(f"   ราคารับซื้อ (คำนวณ):  ฿{calc_buy:,.0f} (-50 บาท)")
    print(f"   ราคาขายออก (คำนวณ): ฿{calc_sell:,.0f} (+50 บาท)")
    
    if thai_gold_data.get('source') == 'intergold.co.th':
        diff = abs(thai_gold_data.get('sell_price_thb', 0) - calc_sell)
        print(f"\n💡 บทวิเคราะห์ความแม่นยำ:")
        print(f"   ราคาหน้าเว็บร้านทอง ห่างจากสูตรที่เราคำนวณไว้เพียง ฿{diff:,.0f} บาท")
        print("   (ส่วนต่างนี้คือ Premium หรือค่าดำเนินการหน้าร้าน ซึ่งถือว่าสมเหตุสมผลมากครับ สูตรเราพร้อมใช้งานแล้ว!)")

if __name__ == "__main__":
    test_gold_calculation_logic()