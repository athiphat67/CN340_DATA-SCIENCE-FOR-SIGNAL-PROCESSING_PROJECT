from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel   
import argparse                  
import sys                      

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request 

from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# 1. หาตำแหน่งของไฟล์ .env ให้แน่ชัด
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir)) # ย้อน 2 ชั้น
dotenv_path = os.path.join(project_root, '.env')

if project_root not in sys.path:
    sys.path.insert(0, project_root)
import main as agent_cli # Import ไฟล์ main.py หลักของคุณมาใช้งาน
# --------------------------------------------------------------------

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

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


origins = [
    "https://cn-240-data-science-for-signal-processing-project-d4qh8pszz.vercel.app",
    "http://localhost:3000", # แนะนำให้ใส่ localhost เผื่อไว้ตอนรันทดสอบในเครื่องตัวเองด้วยครับ
    "http://localhost:5173", # ถ้าใช้ Vite
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [🔥 ส่วนที่ต้องเพิ่มใหม่] โหลด Runtime ของ AI Agent เตรียมไว้ตอนเปิด Server
print("Loading Agent Runtime...")
runtime = agent_cli.build_runtime(no_save=False) # ใช้ no_save=False เพื่อให้มันเซฟลง DB คุณได้
print("Agent Runtime Loaded!")

@app.get("/")
def read_root():
    return {"message": "CORS should be fixed now!"}

# -------------------------------------------------------------
# API Endpoints (ใช้ db instance โดยตรง)
# -------------------------------------------------------------

# [🔥 ส่วนที่ต้องเพิ่มใหม่] Schema และ Endpoint สำหรับให้หน้าเว็บกดยิง Agent
class AnalyzeRequest(BaseModel):
    provider: str
    period: str = "7d"
    intervals: list[str] = ["15m"]
    
@app.post("/api/analyze")
def trigger_analysis(req: AnalyzeRequest): # ✅ ลบ async ออกแล้ว (เหลือแค่ def)
    args = argparse.Namespace(
        provider=req.provider,
        period=req.period,
        intervals=req.intervals,
        skip_fetch=False,
        no_save=False 
    )
    # พอไม่มี async, FastAPI จะโยนงานนี้ไปทำใน Worker Thread 
    # ทำให้ Agent ของคุณสามารถเรียก asyncio.run() ข้างในได้อย่างอิสระครับ
    result = agent_cli.run_analysis_once(args, runtime["services"], emit_logs=False)
    return result

@app.get("/api/models")
async def get_models():
    # ส่ง List โมเดลไปให้ Dropdown บนหน้าเว็บ (จัดหมวดหมู่ให้สวยงาม)
    return {
        "models": [
            # 🟢 Google Gemini Family
            {"id": "openrouter:gemini-3-1-flash-lite-preview", "name": "Gemini 3.1 Flash Lite Preview (Default)"},
            {"id": "openrouter:gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview"},
            {"id": "openrouter:gemini-2-5-flash-lite", "name": "Gemini 2.5 Flash Lite"},
            {"id": "openrouter:gemini-2-0-flash-lite", "name": "Gemini 2.0 Flash Lite"},

            # 🟣 Anthropic Claude Family
            {"id": "openrouter:claude-opus-4.7", "name": "Claude 4.7 Opus"},
            {"id": "openrouter:claude-sonnet-4-6", "name": "Claude 4.6 Sonnet"},
            {"id": "openrouter:claude-haiku-4-5", "name": "Claude 4.5 Haiku"},
            {"id": "openrouter:claude-haiku-3-5", "name": "Claude 3.5 Haiku"},

            # 🔵 OpenAI GPT Family
            {"id": "openrouter:gpt-5-3-codex", "name": "GPT-5.3 Codex"},
            {"id": "openrouter:gpt-5-2-chat", "name": "GPT-5.2 Chat"},
            {"id": "openrouter:gpt-5.1-codex-mini", "name": "GPT-5.1 Codex Mini"},
            {"id": "openrouter:gpt-5-mini", "name": "GPT-5 Mini"},
            {"id": "openrouter:gpt-4o-mini", "name": "GPT-4o Mini"},

            # 🟠 Other State-of-the-Art Models
            {"id": "openrouter:deepseek-v-3-2", "name": "DeepSeek v3.2"},
            {"id": "openrouter:llama-70b", "name": "Llama 3.3 70B Instruct"},
            {"id": "openrouter:grok-mini", "name": "Grok 3 Mini"},
            {"id": "openrouter:mistral-small", "name": "Mistral Small 3.2"},
            {"id": "openrouter:nemotron-super", "name": "Nemotron 3 Super"}
        ]
    }

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
    
# ─────────────────────────────────────────────────────────────────────────────
# เพิ่ม 2 endpoints นี้ลงใน main.py ต่อท้าย endpoints เดิมได้เลย
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/backtest/summary")
def get_backtest_summary(model: str = None):
    """
    ดึง backtest summary ล่าสุด (หรือ filter ตาม model_name)
    ส่งกลับ: object ที่มีทุก field จาก backtest_summary
    """
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                if model:
                    cursor.execute("""
                        SELECT * FROM backtest_summary
                        WHERE model_name = %s
                        ORDER BY run_date DESC LIMIT 1
                    """, (model,))
                else:
                    cursor.execute("""
                        SELECT * FROM backtest_summary
                        ORDER BY run_date DESC LIMIT 1
                    """)
                row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No backtest summary found")

        return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── endpoint ต่อไปนี้ ───────────────────────────────────────────────────────

@app.get("/api/backtest/trades")
def get_backtest_trades(model: str = None, limit: int = 500, signal: str = None):
    """
    ดึงรายการ trade ทั้งหมดที่มี final_signal เป็น BUY หรือ SELL
    Fields: timestamp, final_signal, final_confidence, net_pnl_thb,
            position_size_thb, stop_loss, take_profit,
            llm_rationale, llm_confidence, llm_signal,
            final_correct, final_profitable, rejection_reason,
            portfolio_value, close_thai
    """
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                conditions = ["final_signal IN ('BUY', 'SELL')"]
                params = []

                if model:
                    conditions.append("model_name = %s")
                    params.append(model)
                if signal and signal.upper() in ("BUY", "SELL"):
                    conditions.append("final_signal = %s")
                    params.append(signal.upper())

                where = " AND ".join(conditions)
                params.append(limit)

                cursor.execute(f"""
                    SELECT
                        timestamp,
                        final_signal,
                        final_confidence,
                        net_pnl_thb,
                        position_size_thb,
                        stop_loss,
                        take_profit,
                        llm_rationale,
                        llm_confidence,
                        llm_signal,
                        final_correct,
                        final_profitable,
                        rejection_reason,
                        portfolio_value,
                        close_thai
                    FROM backtest_equity_curve
                    WHERE {where}
                    ORDER BY timestamp ASC
                    LIMIT %s
                """, params)

                rows = cursor.fetchall()

        if not rows:
            return []

        result = []
        for r in rows:
            ts = r["timestamp"]
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                label = dt.strftime("%d %b %H:%M")
            except Exception:
                label = str(ts)[:16]

            result.append({
                "timestamp":         label,
                "signal":            r["final_signal"] or "HOLD",
                "confidence":        round(float(r["final_confidence"] or 0), 2),
                "pnl":               round(float(r["net_pnl_thb"] or 0), 2),
                "position_size":     round(float(r["position_size_thb"] or 0), 2),
                "stop_loss":         round(float(r["stop_loss"] or 0), 2),
                "take_profit":       round(float(r["take_profit"] or 0), 2),
                "rationale":         r["llm_rationale"] or "—",
                "llm_signal":        r["llm_signal"] or "—",
                "llm_confidence":    round(float(r["llm_confidence"] or 0), 2),
                "correct":           bool(r["final_correct"]),
                "profitable":        bool(r["final_profitable"]),
                "rejection_reason":  r["rejection_reason"] or "",
                "portfolio_value":   round(float(r["portfolio_value"] or 0), 2),
                "price":             round(float(r["close_thai"] or 0), 2),
            })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ─── แทนที่ endpoint /api/backtest/equity-curve เดิมใน main.py ────────────────
# เพิ่ม 3 fields ใหม่: price (close_thai), raw_ts (ISO timestamp), profitable

@app.get("/api/backtest/equity-curve")
def get_backtest_equity_curve(model: str = None, limit: int = 2000):
    """
    ดึง equity curve สำหรับวาดกราฟ
    - ส่งกลับ: list ของ { date, value, signal, pnl, price, raw_ts, profitable }
    - เพิ่ม price (close_thai), raw_ts, profitable เพื่อให้ frontend filter timeframe
      และวาดกราฟราคาทองควบคู่กับ equity curve ได้
    """
    try:
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if model:
                    cursor.execute("""
                        SELECT
                            timestamp,
                            portfolio_value,
                            final_signal      AS signal,
                            net_pnl_thb       AS pnl,
                            close_thai        AS price,
                            final_profitable  AS profitable
                        FROM backtest_equity_curve
                        WHERE model_name = %s
                        ORDER BY timestamp ASC
                        LIMIT %s
                    """, (model, limit))
                else:
                    cursor.execute("""
                        SELECT
                            timestamp,
                            portfolio_value,
                            final_signal      AS signal,
                            net_pnl_thb       AS pnl,
                            close_thai        AS price,
                            final_profitable  AS profitable
                        FROM backtest_equity_curve
                        ORDER BY timestamp ASC
                        LIMIT %s
                    """, (limit,))

                rows = cursor.fetchall()

        if not rows:
            return []

        result = []
        for r in rows:
            ts = r["timestamp"]
            raw_ts_str = str(ts)  # เก็บ ISO string ไว้ให้ frontend filter timeframe

            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                label = dt.strftime("%-m/%-d %H:%M")   # "9/1 14:30"
            except Exception:
                label = raw_ts_str[:16]

            result.append({
                "date":       label,
                "value":      round(float(r["portfolio_value"] or 0), 2),
                "signal":     r["signal"] or "HOLD",
                "pnl":        round(float(r["pnl"] or 0), 2),
                "price":      round(float(r["price"] or 0), 2),   # ราคาทองตอนนั้น
                "raw_ts":     raw_ts_str,                          # ISO string สำหรับ filter
                "profitable": bool(r["profitable"]),
            })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))