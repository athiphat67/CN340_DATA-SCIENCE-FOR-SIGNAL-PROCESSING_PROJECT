"""
gold_interceptor_lite.py
ดักข้อมูลราคาทองคำผ่านท่อ WebSocket (Hybrid: curl_cffi ขอตั๋วผ่านด่าน + websocket ดึงข้อมูล)
"""
from curl_cffi import requests
import websocket
import json
import time
from datetime import datetime

LATEST_DATA_FILE = "latest_gold_price.json"
WS_URL = "wss://ws.intergold.co.th:3000/socket.io/?EIO=4&transport=websocket"

def start_interceptor():
    print("🚀 กำลังเตรียมจำลองเบราว์เซอร์เพื่อขอ Cookie...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.intergold.co.th",
        "Referer": "https://www.intergold.co.th/"
    }
    
    try:
        # 1. ใช้ curl_cffi หลอกระบบป้องกันเพื่อเอา Cookie
        session = requests.Session(impersonate="chrome120", headers=headers)
        print("1. กำลังโหลดหน้าแรกเพื่อรับ Cookie ป้องกันบอท...")
        resp = session.get("https://www.intergold.co.th/", timeout=15)
        
        # ดึง Cookie ที่ได้มาแปลงเป็นข้อความเตรียมไว้
        cookies_dict = session.cookies.get_dict()
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
        print(f"✅ ได้รับ Cookie แล้ว (Status: {resp.status_code})")
        
        time.sleep(2)
        
        # 2. ใช้ websocket-client (Python แท้ ปลอดภัยจากบั๊ก C pointer) ต่อท่อเข้าเซิร์ฟเวอร์
        print("2. กำลังมุดท่อ WebSocket ตัวจริง...")
        ws = websocket.WebSocket()
        ws.connect(
            WS_URL,
            header=[
                f"User-Agent: {headers['User-Agent']}",
                f"Origin: {headers['Origin']}",
                f"Referer: {headers['Referer']}"
            ],
            cookie=cookie_str
        )
        print("🟢 WebSocket Connected! มุดท่อสำเร็จแล้ว")
        
        # ลูปรับข้อมูลอย่างมีเสถียรภาพ
        while True:
            msg_str = ws.recv()
            
            # ถ้าไม่มีข้อความตอบกลับแปลว่าโดนตัดสาย
            if not msg_str:
                print("⚠️ เซิร์ฟเวอร์ตัดการเชื่อมต่อ")
                break
                
            if msg_str.startswith("0"):
                print("🤝 ได้รับ Welcome Message (0) กำลังส่งรหัส 40 ขอเข้าห้อง...")
                ws.send("40")
                print("✅ ส่งคำขอเข้าห้องเรียบร้อย รอรับราคา...")
                
            elif msg_str == "2":
                ws.send("3")  # ตอบ Ping กลับไปเพื่อรักษาการเชื่อมต่อ
                
            elif msg_str.startswith("42"):
                try:
                    data_list = json.loads(msg_str[2:])
                    event_name = data_list[0]
                    
                    if event_name == "updateGoldRateData":
                        gold = data_list[1]
                        bid_96 = float(gold.get("bidPrice96", 0))
                        ask_96 = float(gold.get("offerPrice96", 0))
                        spot = float(gold.get("AUXBuy", 0))
                        fx = float(gold.get("usdBuy", 0))
                        
                        if bid_96 > 0 and ask_96 > 0:
                            payload = {
                                "source": "intergold_hybrid_ws",
                                "price_thb_per_baht_weight": round((bid_96 + ask_96) / 2, 2),
                                "sell_price_thb": ask_96,
                                "buy_price_thb": bid_96,
                                "spread_thb": ask_96 - bid_96,
                                "gold_spot_usd": spot,
                                "usd_thb_live": fx,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            # บันทึกเป็น JSON เบาๆ สำหรับเทรด
                            with open(LATEST_DATA_FILE, "w", encoding="utf-8") as f:
                                json.dump(payload, f, ensure_ascii=False)
                            
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🇹🇭 THAI 96.5% | Buy: ฿{bid_96:,.0f} | Sell: ฿{ask_96:,.0f}")
                except json.JSONDecodeError:
                    pass
                    
    except Exception as e:
        print(f"❌ สายหลุด หรือ เกิดข้อผิดพลาด: {e}")

if __name__ == '__main__':
    while True:
        start_interceptor()
        print("🔄 ระบบกำลังจะเชื่อมต่อใหม่ใน 5 วินาที...")
        time.sleep(5)