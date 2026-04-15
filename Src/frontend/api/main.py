import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env (URL ของฐานข้อมูล)
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="Nakkhutthong API")

# ตั้งค่า CORS อนุญาตให้หน้าเว็บ React (Frontend) เรียกใช้ API นี้ได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://cn240data-science-for-signal-processingproject-production-7972.up.railway.app"], # ตอนขึ้นโปรดักชันจริงควรเปลี่ยนเป็น URL เว็บ React ของคุณ เช่น ["https://myweb.com"]
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