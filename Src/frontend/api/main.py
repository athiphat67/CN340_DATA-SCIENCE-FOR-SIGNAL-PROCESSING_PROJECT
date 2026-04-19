# --- START OF FILE main.py ---
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime, timezone  # เพิ่ม timezone เข้าไปตรงนี้

import os
from dotenv import load_dotenv

# 1. หาตำแหน่งของไฟล์ .env ให้แน่ชัด
# ย้อนออกจาก /Src/frontend/api/ ไปที่ /Src/
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir)) # ย้อน 2 ชั้น
dotenv_path = os.path.join(project_root, '.env')

# 2. โหลดด้วย path ที่ระบุ
load_dotenv(dotenv_path)

# 3. ลอง Print เช็คดูว่าเจอค่าไหม (กันพลาด)
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print(f"❌ Error: ไม่พบ DATABASE_URL ในไฟล์ที่ {dotenv_path}")
else:
    print(f"✅ โหลด DATABASE_URL เรียบร้อยแล้ว")

# หลังจากนั้นค่อย Initialize RunDatabase()
from database.database import RunDatabase
db = RunDatabase()
from psycopg2.extras import RealDictCursor
from supabase import create_client, Client

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

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
        result = db.get_portfolio()
        
        cost_basis = float(result.get('cost_basis_thb') or 0.0)
        gold_grams = float(result.get('gold_grams') or 0.0)
        unrealized_pnl = float(result.get('unrealized_pnl') or 0.0)
        available_cash = float(result.get('cash_balance', 0))
        
        total_cost = cost_basis * gold_grams
        pnl_percent = round((unrealized_pnl / total_cost) * 100, 2) if total_cost > 0 else 0.0
        
        # คำนวณ Total Equity ส่งไปให้ Frontend
        total_equity = available_cash + total_cost + unrealized_pnl

        return {
            "available_cash": available_cash,
            "unrealized_pnl": unrealized_pnl,
            "pnl_percent": pnl_percent,
            "trades_today": int(result.get('trades_today', 0)),
            "total_equity": total_equity # <--- เพิ่มบรรทัดนี้
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
        
from datetime import datetime

@app.get("/api/performance-chart")
def get_performance_chart(limit: int = 50):
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # ✨ แก้ไข SQL ตรงนี้ ใช้ WITH (CTE) ดึงข้อมูลใหม่สุดก่อน แล้วค่อยเรียงเวลาใหม่
                cursor.execute("""
                    WITH latest_data AS (
                        SELECT 
                            run_at as timestamp,
                            id as "signalId",
                            signal as action,
                            gold_price_thb as price
                        FROM runs
                        WHERE gold_price_thb IS NOT NULL
                        ORDER BY run_at DESC
                        LIMIT %s
                    )
                    SELECT * FROM latest_data 
                    ORDER BY timestamp ASC;
                """, (limit,))
                
                rows = cursor.fetchall()
                formatted_data = []

                for r in rows:
                    dt_str = r['timestamp'].replace('Z', '+00:00')
                    try:
                        dt = datetime.fromisoformat(dt_str)
                        time_display = dt.strftime('%d %b %H:%M')
                    except Exception:
                        time_display = r['timestamp']
                    
                    formatted_data.append({
                        "time": time_display,
                        "price": float(r['price']),
                        "signalId": r['signalId'],
                        "action": r['action'] if r['action'] in ['BUY', 'SELL', 'HOLD'] else None
                    })
                    
                return formatted_data
    except Exception as e:
        print(f"Error in /api/performance-chart: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chart data")
    
from datetime import datetime, timezone

@app.get("/api/agent-health")
def get_agent_health():
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # ดึงข้อมูลรอบล่าสุดจาก logs หรือ runs
                cursor.execute("""
                    SELECT run_at, execution_time_ms, confidence 
                    FROM runs 
                    ORDER BY run_at DESC 
                    LIMIT 1
                """)
                last_run = cursor.fetchone()
                
                # ตรวจสอบการอัปเดตราคาทองล่าสุด
                cursor.execute("""
                    SELECT timestamp 
                    FROM gold_prices_ig 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                last_price = cursor.fetchone()

        # คำนวณความใหม่ของข้อมูลราคา (Data Freshness)
        now = datetime.now(timezone.utc)
        api_status = "Stable"
        quality_score = 98

        last_update_str = "Just now"
        if last_price and last_price['timestamp']:
            price_time = last_price['timestamp']
            
            # 1. ถ้าเป็น String ให้แปลงเป็น Datetime ก่อน
            if isinstance(price_time, str):
                 price_time = datetime.fromisoformat(price_time.replace('Z', '+00:00'))
            
            # 2. ✨ [เพิ่มตรงนี้] ถ้าเป็น Datetime แต่ไม่มี Timezone ให้เติม UTC เข้าไป
            if isinstance(price_time, datetime) and price_time.tzinfo is None:
                 price_time = price_time.replace(tzinfo=timezone.utc)
            
            if isinstance(price_time, str):
                 price_time = datetime.fromisoformat(price_time.replace('Z', '+00:00'))
            diff_seconds = (now - price_time).total_seconds()
            
            if diff_seconds > 300: # ถ้าราคาไม่อัปเดตเกิน 5 นาที
                api_status = "Warning"
                quality_score = 65
                last_update_str = f"{int(diff_seconds // 60)}m ago"
            elif diff_seconds > 60:
                last_update_str = f"{int(diff_seconds // 60)}m ago"
            else:
                last_update_str = f"{int(diff_seconds)}s ago"

        return {
            "latency": last_run['execution_time_ms'] if last_run and 'execution_time_ms' in last_run else 1200,
            "iterations": 3, # ถ้ามีการเก็บ Step ReAct ใน DB สามารถดึงมาแทนเลข 3 ได้
            "api_status": api_status,
            "accuracy": last_run['confidence'] if last_run and 'confidence' in last_run else 95,
            "last_update": last_update_str,
            "quality_score": quality_score
        }

    except Exception as e:
        print(f"Health API Error: {e}")
        # Mock Response กรณี Database มีปัญหา
        return {
            "latency": 0, "iterations": 0, "api_status": "Offline", "accuracy": 0, "last_update": "-", "quality_score": 0
        }
        
from datetime import datetime
@app.get("/api/active-positions")
def get_active_positions():
    try:
        # ดึง 2 Signal ล่าสุดที่ AI แนะนำให้ BUY หรือ SELL
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        id, 
                        logged_at as open_time,
                        signal as type,
                        entry_price as entry,
                        take_profit as tp,
                        stop_loss as sl,
                        confidence
                    FROM llm_logs 
                    WHERE signal IN ('BUY', 'SELL')
                    ORDER BY id DESC 
                    LIMIT 2;
                """)
                rows = cursor.fetchall()

        formatted_positions = []
        for row in rows:
            # แปลงเวลาให้สวยงาม
            dt = row['open_time']
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            
            # จำลองข้อมูลส่วนที่ยังไม่มีใน DB เช่น size และ pnl (ใช้สุ่มหรือค่าคงที่ไปก่อน)
            formatted_positions.append({
                "id": f"POS-{row['id']}",
                "asset": "XAU/THB (96.5%)",
                "type": row['type'],
                "size": "5 Grams", # ค่าจำลอง
                "entry": float(row['entry'] or 0),
                "current": float(row['entry'] or 0) * 1.002, # จำลองราคาปัจจุบันให้กำไรนิดหน่อย
                "tp": float(row['tp'] or 0),
                "sl": float(row['sl'] or 0),
                "openTime": dt.strftime('%d %b, %H:%M'),
                "pnl": 450, # ค่าจำลอง
                "pnlPercent": 0.15 # ค่าจำลอง
            })

        return formatted_positions

    except Exception as e:
        print(f"Error fetching active positions: {e}")
        # ถ้า Error ให้ส่ง Array ว่างกลับไป หน้าเว็บจะได้ไม่ค้าง
        return []

@app.get("/api/market-bias")
def get_market_bias():
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # แก้ชื่อคอลัมน์เป็น 'rationale' ตาม Schema ในรูปภาพครับ
                cursor.execute("""
                    SELECT signal, confidence, rationale 
                    FROM runs 
                    WHERE signal IS NOT NULL
                    ORDER BY id DESC LIMIT 1
                """)
                result = cursor.fetchone()
        
        if result:
            sig = result.get('signal', 'HOLD')
            direction = "Neutral"
            if sig == "BUY": direction = "Bullish"
            elif sig == "SELL": direction = "Bearish"

            return {
                "direction": direction,
                "conviction": result.get('confidence') or 0,
                "reason": result.get('rationale') or "Analysis in progress..."
            }
        return {"direction": "Neutral", "conviction": 0, "reason": "No recent runs found."}
    except Exception as e:
        print(f"Market Bias Error: {e}")
        return {"direction": "Neutral", "conviction": 0, "reason": "System synchronization..."}

@app.get("/api/agent-health")
def get_agent_health():
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # ใช้ 'execution_time_ms' จากตาราง runs และ 'iterations_used' ตาม Schema จริง
                cursor.execute("""
                    SELECT run_at, execution_time_ms, confidence, iterations_used 
                    FROM runs 
                    ORDER BY id DESC LIMIT 1
                """)
                last_run = cursor.fetchone()
                
                cursor.execute("SELECT timestamp FROM gold_prices_ig ORDER BY timestamp DESC LIMIT 1")
                last_price = cursor.fetchone()

        now = datetime.now(timezone.utc)
        # ตรวจสอบ API Status จากความสดใหม่ของราคาทอง
        api_status = "Stable"
        last_update_str = "Just now"
        
        if last_price and last_price['timestamp']:
            p_time = last_price['timestamp']
            if isinstance(p_time, str):
                p_time = datetime.fromisoformat(p_time.replace('Z', '+00:00'))
            if p_time.tzinfo is None:
                p_time = p_time.replace(tzinfo=timezone.utc)
            
            diff = (now - p_time).total_seconds()
            if diff > 300: api_status = "Warning"
            last_update_str = f"{int(diff//60)}m ago" if diff > 60 else f"{int(diff)}s ago"

        return {
            "latency": last_run.get('execution_time_ms') or 0,
            "iterations": last_run.get('iterations_used') or 0,
            "api_status": api_status,
            "accuracy": last_run.get('confidence') or 0,
            "last_update": last_update_str,
            "quality_score": 95 if api_status == "Stable" else 60
        }
    except Exception as e:
        print(f"Health API Error: {e}")
        return {"latency": 0, "iterations": 0, "api_status": "Offline", "accuracy": 0, "last_update": "-", "quality_score": 0}