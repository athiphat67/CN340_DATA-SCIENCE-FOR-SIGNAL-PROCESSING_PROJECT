import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Generator

# โหลดค่าจากไฟล์ .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Nakkhutthong API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# 1. สร้าง Dependency สำหรับจัดการ Database Connection
# -------------------------------------------------------------
def get_db() -> Generator:
    """ฟังก์ชันนี้จะเปิด Connection ส่งให้ API และปิดให้อัตโนมัติเมื่อ API ทำงานเสร็จ"""
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        yield conn  # ส่ง conn ไปให้ API ที่เรียกใช้
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")
    finally:
        if conn:
            conn.close() # การันตีว่าปิดแน่ๆ ไม่ว่าจะเกิด Error อะไรใน API

# -------------------------------------------------------------
# 2. นำ Dependency ไปใช้ใน API
# -------------------------------------------------------------

@app.get("/api/latest-signal")
def get_latest_signal(conn = Depends(get_db)): # <--- เรียกใช้ตรงนี้
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = "SELECT *, 'AI AGENT' as provider FROM llm_logs WHERE signal IS NOT NULL ORDER BY id DESC LIMIT 1;"
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                return result
            raise HTTPException(status_code=404, detail="No signals found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/signals/{signal_id}")
def get_signal_detail(signal_id: int, conn = Depends(get_db)): # <--- เรียกใช้ตรงนี้
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM llm_logs WHERE id = %s", (signal_id,))
            result = cursor.fetchone()
            
            if result:
                return result
            raise HTTPException(status_code=404, detail="Signal not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
def get_portfolio_data(conn = Depends(get_db)): # <--- เรียกใช้ตรงนี้
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT cash_balance, gold_grams, cost_basis_thb, unrealized_pnl, trades_today 
                FROM portfolio WHERE id = 1;
            """)
            result = cursor.fetchone()
            
            if not result:
                return {
                    "available_cash": 1500.0, "unrealized_pnl": 0.0,
                    "pnl_percent": 0.0, "trades_today": 0
                }
            
            cost_basis = float(result.get('cost_basis_thb') or 0.0)
            gold_grams = float(result.get('gold_grams') or 0.0)
            unrealized_pnl = float(result.get('unrealized_pnl') or 0.0)
            
            total_cost = cost_basis * gold_grams
            pnl_percent = round((unrealized_pnl / total_cost) * 100, 2) if total_cost > 0 else 0.0

            return {
                "available_cash": float(result['cash_balance']),
                "unrealized_pnl": unrealized_pnl,
                "pnl_percent": pnl_percent,
                "trades_today": int(result['trades_today'])
            }
    except Exception as e:
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
    
@app.get("/api/recent-signals")
def get_recent_signals(limit: int = 20, conn = Depends(get_db)):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # ดึงข้อมูลจาก llm_logs เรียงจากใหม่ไปเก่า
            cursor.execute("""
                SELECT 
                    id, 
                    logged_at, 
                    interval_tf, 
                    entry_price, 
                    take_profit, 
                    stop_loss, 
                    signal, 
                    confidence
                FROM llm_logs 
                WHERE signal IS NOT NULL 
                ORDER BY id DESC 
                LIMIT %s;
            """, (limit,))
            
            results = cursor.fetchall()
            return results
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))