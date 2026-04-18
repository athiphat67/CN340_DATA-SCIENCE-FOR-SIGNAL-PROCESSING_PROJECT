import os
import sys
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# ─── 1. จัดการ Path ให้มองเห็นโฟลเดอร์ Src (เพื่อดึง Database มาใช้) ───
# โครงสร้าง: Src/frontend/api/main.py -> ถอยไป 2 ระดับจะเจอ Src/
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ดึงคลาส RunDatabase มาจาก Src/database/database.py อย่างปลอดภัย
try:
    from database.database import RunDatabase
except ImportError as e:
    print(f"Error: Cannot find database folder at {project_root}. Details: {e}")
    RunDatabase = None
# ──────────────────────────────────────────────────────────────────────

# โหลดค่าจากไฟล์ .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="Nakkhutthong API")

# สร้าง Instance ของ RunDatabase สำหรับ Endpoint ใหม่ (ถ้า import สำเร็จ)
db = RunDatabase() if RunDatabase else None

# ตั้งค่า CORS (อิงตามค่าเดิมของโปรเจกต์ 100%)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # อนุญาตหมดทุกที่
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ฟังก์ชันสำหรับเชื่อมต่อ Database แบบเดิม (เก็บไว้เพื่อความปลอดภัยของโค้ดเก่า)
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return None

# ==========================================
# 🟢 ENDPOINTS เดิมของเพื่อน (คงไว้ 100% ปลอดภัยแน่นอน)
# ==========================================

@app.get("/api/latest-signal")
def get_latest_signal():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT id, logged_at, signal, confidence, entry_price, stop_loss, take_profit, rationale FROM llm_logs WHERE signal IS NOT NULL ORDER BY id DESC LIMIT 1;"
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result: return result
        raise HTTPException(status_code=404, detail="No signals found")
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/signals/{signal_id}")
def get_signal_detail(signal_id: int):
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM llm_logs WHERE id = %s", (signal_id,))
        result = cur.fetchone()
        cur.close()
        conn.close() 
        if result: return result
        raise HTTPException(status_code=404, detail="Signal not found")
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 🟢 ENDPOINTS ใหม่ (สำหรับหน้า History และ Market ของคุณ)
# ==========================================

@app.get("/api/archive/history")
def get_history_data():
    """ ดึงข้อมูลประวัติการเทรด (History Page) """
    if not db:
        raise HTTPException(status_code=500, detail="RunDatabase system not initialized")
    try:
        trades = db.get_trade_history(limit=100)
        summary = db.get_pnl_summary()
        growth = db.get_monthly_growth()
        
        summary['growth_pct'] = growth.get('growth_pct', 0)
        summary['sync_status'] = "Verified & Locked"

        return {
            "status": "success",
            "summary": summary,
            "trades": trades
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/data")
def get_market_data(timeframe: str = Query("1W")):
    """ ดึงข้อมูลสำหรับการแสดงกราฟ (Market Page) """
    if not db:
        raise HTTPException(status_code=500, detail="RunDatabase system not initialized")
    try:
        recent_runs = db.get_recent_runs(limit=100)
        return {
            "status": "success",
            "timeframe": timeframe,
            "runs_count": len(recent_runs),
            "data": recent_runs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))