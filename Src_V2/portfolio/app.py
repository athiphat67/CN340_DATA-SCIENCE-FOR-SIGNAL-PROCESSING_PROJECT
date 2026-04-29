import gradio as gr
import os
from supabase import create_client, Client
from datetime import datetime

from dotenv import load_dotenv 
load_dotenv()


# 1. ดึงค่า Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ตรวจสอบว่าใส่ Key หรือยัง
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("กรุณาตั้งค่า SUPABASE_URL และ SUPABASE_KEY ใน Environment Variables")

# สร้าง Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ฟังก์ชันสำหรับดึงข้อมูลล่าสุด (Fetch)
def fetch_portfolio(port_id):
    try:
        response = supabase.table("portfolio").select("*").eq("id", port_id).execute()
        if response.data:
            data = response.data[0]
            return (
                data.get("cash_balance", 0.0),
                data.get("gold_grams", 0.0),
                data.get("cost_basis_thb", 0.0),
                data.get("current_value_thb", 0.0),
                data.get("unrealized_pnl", 0.0),
                data.get("trades_today", 0),
                data.get("trailing_stop_level_thb", 0.0),
                f"✅ โหลดข้อมูลสำเร็จ! (อัพเดตล่าสุดใน DB: {data.get('updated_at')})"
            )
        else:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, "⚠️ ไม่พบข้อมูล Portfolio ID นี้")
    except Exception as e:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, f"❌ Error: {str(e)}")

# ฟังก์ชันสำหรับอัพเดตข้อมูล (Update/Upsert)
def update_portfolio(port_id, cash, gold, cost, value, pnl, trades, trailing_stop):
    now_str = datetime.now().isoformat() # เวลาปัจจุบันแบบ ISO format สำหรับใส่ใน Text
    
    data_to_update = {
        "id": port_id, # ถ้ามี ID นี้อยู่แล้วจะ Update, ถ้าไม่มีจะ Insert ใหม่ (Upsert)
        "cash_balance": cash,
        "gold_grams": gold,
        "cost_basis_thb": cost,
        "current_value_thb": value,
        "unrealized_pnl": pnl,
        "trades_today": trades,
        "updated_at": now_str,
        "trailing_stop_level_thb": trailing_stop
    }
    
    try:
        response = supabase.table("portfolio").upsert(data_to_update).execute()
        return f"✅ อัพเดต Portfolio ID: {port_id} สำเร็จแล้วเมื่อ {now_str}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# 2. สร้างหน้าตา UI ด้วย Gradio
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📈 Portfolio Management System")
    gr.Markdown("ระบบอัพเดตสถานะพอร์ตโฟลิโอ บันทึกลง Supabase Database")
    
    with gr.Row():
        port_id = gr.Number(label="Portfolio ID (ใส่ 1 เพื่อดึงพอร์ตหลัก)", value=1, precision=0)
        btn_fetch = gr.Button("🔄 โหลดข้อมูลล่าสุดจาก DB")

    with gr.Row():
        cash = gr.Number(label="Cash Balance (THB)", value=1500.0)
        gold = gr.Number(label="Gold (Grams)", value=0.0)

    with gr.Row():
        cost = gr.Number(label="Cost Basis (THB)", value=0.0)
        value = gr.Number(label="Current Value (THB)", value=0.0)
        pnl = gr.Number(label="Unrealized PnL (THB)", value=0.0)

    with gr.Row():
        trades = gr.Number(label="Trades Today", value=0, precision=0)
        trailing_stop = gr.Number(label="Trailing Stop Level (THB)")

    btn_update = gr.Button("💾 บันทึก/อัพเดตข้อมูล", variant="primary")
    status_text = gr.Textbox(label="Status / ข้อความแจ้งเตือน", interactive=False)

    # ผูกปุ่มเข้ากับฟังก์ชัน
    btn_fetch.click(
        fn=fetch_portfolio,
        inputs=[port_id],
        outputs=[cash, gold, cost, value, pnl, trades, trailing_stop, status_text]
    )
    
    btn_update.click(
        fn=update_portfolio,
        inputs=[port_id, cash, gold, cost, value, pnl, trades, trailing_stop],
        outputs=[status_text]
    )

# 3. รัน Server (รองรับการ Deploy บน Railway ที่จะโยน PORT มาให้)
if __name__ == "__main__":
    # ดึงค่า Username / Password จาก Env ถ้าไม่มีให้ใช้ admin / admin123
    APP_USER = os.environ.get("APP_USER", "admin")
    APP_PASS = os.environ.get("APP_PASS", "admin123")
    
    port = int(os.environ.get("PORT", 7860))
    demo.launch(
        server_name="0.0.0.0", 
        server_port=port,
        auth=(APP_USER, APP_PASS) # ใส่รหัสผ่านก่อนเข้าเว็บ
    )