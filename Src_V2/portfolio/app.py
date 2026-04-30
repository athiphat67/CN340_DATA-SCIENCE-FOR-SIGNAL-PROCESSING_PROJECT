import gradio as gr
import os

# โหลด .env สำหรับการรันบนเครื่อง Local
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

# ดึงค่า Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("กรุณาตั้งค่า SUPABASE_URL และ SUPABASE_KEY ใน Environment Variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ตั้งค่าโซนเวลาไทย (UTC+7)
tz_th = timezone(timedelta(hours=7))

# ฟังก์ชันสำหรับดึงข้อมูล "พอร์ตล่าสุด" ออกมาโชว์
def fetch_latest_portfolio():
    try:
        response = supabase.table("portfolio").select("*").order("id", desc=True).limit(1).execute()
        
        if response.data:
            data = response.data[0]
            # ต้องส่งค่าเป็น String ทั้งหมดเพราะใช้ Textbox
            return (
                str(data.get("cash_balance", 0.0)),
                str(data.get("gold_grams", 0.0)),
                str(data.get("cost_basis_thb", 0.0)),
                str(data.get("current_value_thb", 0.0)),
                str(data.get("unrealized_pnl", 0.0)),
                str(data.get("trades_today", 0)),
                str(data.get("trades_this_session", 0)), # ✅ [NEW]
                str(data.get("trailing_stop_level_thb", 0.0)),
                f"✅ โหลดข้อมูลล่าสุดสำเร็จ (คิว ID ล่าสุดคือ: {data.get('id')}) อัพเดตเมื่อ: {data.get('updated_at')}"
            )
        else:
            return ("1500.0", "0.0", "0.0", "0.0", "0.0", "0", "0", "0.0", "⚠️ ยังไม่มีประวัติในระบบ")
    except Exception as e:
        return ("0.0", "0.0", "0.0", "0.0", "0.0", "0", "0", "0.0", f"❌ Error: {str(e)}")

# ฟังก์ชันสำหรับสร้างประวัติพอร์ตใหม่
def insert_portfolio(cash, gold, cost, value, pnl, trades, trades_session, trailing_stop):
    # ตรวจสอบและแปลงค่าจาก String เป็น Number
    try:
        cash = float(cash) if cash else 0.0
        gold = float(gold) if gold else 0.0
        cost = float(cost) if cost else 0.0
        value = float(value) if value else 0.0
        pnl = float(pnl) if pnl else 0.0
        trades = int(trades) if trades else 0
        trades_session = int(trades_session) if trades_session else 0 # ✅ [NEW]
        trailing_stop = float(trailing_stop) if trailing_stop else 0.0
    except ValueError:
        return "❌ ข้อมูลไม่ถูกต้อง โปรดตรวจสอบตัวเลขให้ครบถ้วน"

    now_str = datetime.now(tz_th).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # 1. เช็คว่า ID ล่าสุดใน DB คืออะไร
        check_response = supabase.table("portfolio").select("id").order("id", desc=True).limit(1).execute()
        
        if check_response.data:
            latest_id = check_response.data[0]["id"]
            next_id = latest_id + 1
        else:
            next_id = 1
            
        # 2. เตรียมข้อมูล
        data_to_insert = {
            "id": next_id,
            "cash_balance": cash,
            "gold_grams": gold,
            "cost_basis_thb": cost,
            "current_value_thb": value,
            "unrealized_pnl": pnl,
            "trades_today": trades,
            "trades_this_session": trades_session, # ✅ [NEW]
            "updated_at": now_str,
            "trailing_stop_level_thb": trailing_stop
        }
        
        # 3. Insert
        supabase.table("portfolio").insert(data_to_insert).execute()
        
        return f"✅ บันทึกประวัติใหม่สำเร็จ! (บันทึกลง ID: {next_id} เมื่อเวลา {now_str})"
    
    except Exception as e:
        return f"❌ Error: {str(e)}"

# สร้างหน้าตา UI ด้วย Gradio
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📈 Portfolio History Logger")
    gr.Markdown("ระบบบันทึกประวัติพอร์ตโฟลิโอ (รองรับ Session Quota)")
    
    with gr.Row():
        btn_fetch = gr.Button("🔄 โหลดข้อมูลพอร์ตล่าสุดจาก DB")

    # เปลี่ยนเป็น gr.Textbox(type="number")
    with gr.Row():
        cash = gr.Textbox(label="Cash Balance (THB)", value="1500.0", interactive=True)
        gold = gr.Textbox(label="Gold (Grams)", value="0.0", interactive=True)

    with gr.Row():
        cost = gr.Textbox(label="Cost Basis (THB)", value="0.0", interactive=True)
        value = gr.Textbox(label="Current Value (THB)", value="0.0", interactive=True)
        pnl = gr.Textbox(label="Unrealized PnL (THB)", value="0.0", interactive=True)

    with gr.Row():
        trades = gr.Textbox(label="Trades Today", value="0", interactive=True)
        trades_session = gr.Textbox(label="Trades This Session", value="0", interactive=True) # ✅ [NEW]
        trailing_stop = gr.Textbox(label="Trailing Stop Level (THB)", value="0.0", interactive=True)

    btn_insert = gr.Button("💾 บันทึกประวัติใหม่ (เพิ่มแถวใหม่)", variant="primary")
    status_text = gr.Textbox(label="Status / ข้อความแจ้งเตือน", interactive=False)

    btn_fetch.click(
        fn=fetch_latest_portfolio,
        inputs=[],
        outputs=[cash, gold, cost, value, pnl, trades, trades_session, trailing_stop, status_text]
    )
    
    btn_insert.click(
        fn=insert_portfolio,
        inputs=[cash, gold, cost, value, pnl, trades, trades_session, trailing_stop],
        outputs=[status_text]
    )

# รัน Server
if __name__ == "__main__":
    APP_USER = os.environ.get("APP_USER", "admin")
    APP_PASS = os.environ.get("APP_PASS", "admin123")
    
    port = int(os.environ.get("PORT", 7860))
    demo.launch(
        server_name="0.0.0.0", 
        server_port=port,
        auth=(APP_USER, APP_PASS) 
    )