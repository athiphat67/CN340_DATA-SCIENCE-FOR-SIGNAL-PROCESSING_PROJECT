import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from supabase import create_client, Client

# โหลดค่าจากไฟล์ .env (URL ของฐานข้อมูล)
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Nakkhutthong API")

# ตั้งค่า CORS อนุญาตให้หน้าเว็บ React (Frontend) เรียกใช้ API นี้ได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # อนุญาตหมดทุกที่
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ฟังก์ชันสำหรับเชื่อมต่อ Database
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return None

# สร้าง Endpoint (URL) สำหรับดึง Signal ล่าสุด
@app.get("/api/latest-signal")
def get_latest_signal():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # ใช้ RealDictCursor เพื่อให้ผลลัพธ์ที่ดึงออกมาเป็น JSON Object (key: value)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # คำสั่ง SQL ดึงข้อมูลจากตาราง llm_logs ล่าสุด 1 อัน
        query = """
            SELECT 
                id, 
                logged_at, 
                signal, 
                confidence, 
                entry_price, 
                stop_loss, 
                take_profit, 
                rationale 
            FROM llm_logs 
            WHERE signal IS NOT NULL
            ORDER BY id DESC 
            LIMIT 1;
        """
        cursor.execute(query)
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()

        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="No signals found")

    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/signals/{signal_id}")
def get_signal_detail(signal_id: int):
    conn = get_db_connection()
    
    # 1. ตรวจสอบก่อนว่า conn ไม่ใช่ None (แก้ Error: cursor is not a known attribute of "None")
    if conn is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM llm_logs WHERE id = %s", (signal_id,))
        result = cur.fetchone()
        
        cur.close()
        # 2. ปิดการเชื่อมต่อภายในบล็อกที่มั่นใจว่ามี conn แน่นอน
        conn.close() 
        
        if result:
            return result
        raise HTTPException(status_code=404, detail="Signal not found")

    except Exception as e:
        # ตรวจสอบอีกครั้งในส่วน exception เพื่อความปลอดภัยตอนปิด
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/gold-prices")
async def get_gold_prices():
    try:
        # 1. เปลี่ยนชื่อตารางเป็น gold_prices_ig
        response = supabase.table("gold_prices_ig") \
            .select("ask_96, bid_96, spot_price, usd_thb") \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()
        
        if response.data:
            data = response.data[0]
            return {
                "hsh_sell": data.get("ask_96"), 
                "hsh_buy": data.get("bid_96"),
                "spot_price": data.get("spot_price"), # ตัวนี้มีแล้วใน ig
                "usd_thb": data.get("usd_thb"),      # ตัวนี้ก็มีแล้วใน ig
            }
        raise HTTPException(status_code=404, detail="No data found")
    except Exception as e:
        # ถ้าพังจะบอกรายละเอียด error มาใน detail
        raise HTTPException(status_code=500, detail=str(e))