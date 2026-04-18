# --- START OF FILE main.py ---
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sys # <--- เพิ่มตรงนี้
import os
from dotenv import load_dotenv

# 1. หาตำแหน่งของไฟล์ (ตอนนี้คือ /Src/frontend/api/)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 2. ย้อนขึ้นไป 2 ชั้นเพื่อให้ถึง /Src/
project_root = os.path.dirname(os.path.dirname(current_dir)) 

# --- [หัวใจสำคัญ] เพิ่มตรงนี้เข้าไปครับ ---
if project_root not in sys.path:
    sys.path.append(project_root)
# --------------------------------------

# 3. โหลด .env
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path)

# หลังจากทำ sys.path.append(project_root) แล้ว
# Python จะสามารถมองเห็นโฟลเดอร์ 'database' ที่อยู่ใน 'Src/' ได้ทันที

import sys
import os

# Debug: ปริ้นท์ตำแหน่งปัจจุบันและ Path ทั้งหมด
print("--- DEBUG PATH ---")
print("Current Working Directory:", os.getcwd())
print("File Path:", __file__)
print("Current sys.path:", sys.path)

# ทำการ Add Path
current_dir = os.path.dirname(os.path.abspath(__file__))
# ต้องมั่นใจว่า path ที่ add คือโฟลเดอร์ที่ครอบ 'database' อยู่
project_root = os.path.abspath(os.path.join(current_dir, '..', '..')) 
sys.path.append(project_root)

print("Added Path:", project_root)
print("--- END DEBUG ---")


from database.database import RunDatabase
db = RunDatabase()

from psycopg2.extras import RealDictCursor
import supabase

app = FastAPI(title="Nakkhutthong API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# API Endpoints (ใช้ db instance โดยตรง)
# -------------------------------------------------------------

@app.get("/api/latest-signal")
def get_latest_signal():
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = "SELECT *, 'AI AGENT' as provider FROM llm_logs WHERE signal IS NOT NULL ORDER BY id DESC LIMIT 1;"
                cursor.execute(query)
                result = cursor.fetchone()
                if result:
                    return result
                raise HTTPException(status_code=404, detail="No signals found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/signals/{signal_id}")
def get_signal_detail(signal_id: int):
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM llm_logs WHERE id = %s", (signal_id,))
                result = cursor.fetchone()
                if result:
                    return result
                raise HTTPException(status_code=404, detail="Signal not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
def get_portfolio_data():
    try:
        # ใช้ Method ที่มีอยู่แล้วใน RunDatabase
        result = db.get_portfolio()
        
        # คำนวณ PnL เปอร์เซ็นต์ (ย้าย logic มาที่นี่เพื่อให้ส่งค่าครบ)
        cost_basis = float(result.get('cost_basis_thb') or 0.0)
        gold_grams = float(result.get('gold_grams') or 0.0)
        unrealized_pnl = float(result.get('unrealized_pnl') or 0.0)
        
        total_cost = cost_basis * gold_grams
        pnl_percent = round((unrealized_pnl / total_cost) * 100, 2) if total_cost > 0 else 0.0

        return {
            "available_cash": float(result.get('cash_balance', 0)),
            "unrealized_pnl": unrealized_pnl,
            "pnl_percent": pnl_percent,
            "trades_today": int(result.get('trades_today', 0))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/gold-prices")
def get_gold_prices():
    try:
        # 1. สั่ง Sync ข้อมูลก่อนดึงค่าเสมอ (ให้ข้อมูลสดใหม่ตลอดเวลาที่คนกดเข้ามาดู)
        sync_latest_price() 
        
        # 2. ดึงจาก Render Postgres
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM gold_prices_ig ORDER BY timestamp DESC LIMIT 1")
                data = cursor.fetchone()
        
        if data:
            return {
                "hsh_sell": data.get("ask_96"), 
                "hsh_buy": data.get("bid_96"),
                "spot_price": data.get("spot_price"),
                "usd_thb": data.get("usd_thb"),
            }
        raise HTTPException(status_code=404, detail="No gold data found in Postgres")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/recent-signals")
def get_recent_signals(limit: int = 20):
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, logged_at, interval_tf, entry_price, take_profit, stop_loss, signal, confidence
                    FROM llm_logs 
                    WHERE signal IS NOT NULL 
                    ORDER BY id DESC LIMIT %s;
                """, (limit,))
                return cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/market-state")
def get_market_state():
    try:
        # ดึงจากตาราง gold_prices_ig ใน Render Postgres
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM gold_prices_ig ORDER BY timestamp DESC LIMIT 1")
                data = cursor.fetchone()
        
        if not data:
            raise HTTPException(status_code=404, detail="No market data")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def sync_latest_price():
    try:
        # ดึงแค่แถวเดียวล่าสุดจาก Supabase
        response = supabase.table("gold_prices_ig").select("*").order("timestamp", desc=True).limit(1).execute()
        if response.data:
            row = response.data[0]
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # อัปเดตข้อมูลล่าสุดลง Render
                    cursor.execute("""
                        INSERT INTO gold_prices_ig (timestamp, ask_96, bid_96, spot_price, usd_thb)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (timestamp) DO NOTHING;
                    """, (row['timestamp'], row['ask_96'], row['bid_96'], row['spot_price'], row['usd_thb']))
                conn.commit()
    except Exception as e:
        print(f"Sync failed: {e}")