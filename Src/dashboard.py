"""
dashboard.py — Goldtrader Dashboard v4 (Refactored)
"""

import os
import traceback
from datetime import datetime, timedelta, timezone
import gradio as gr
from dotenv import load_dotenv

# ── [Import Custom Components] ──────────────────────────────────────────
from frontend.constants import *
from frontend.formatters import (
    format_trace_html, 
    format_history_html, 
    format_stats_html
)
from frontend.portfolio_mgr import create_portfolio_handlers, format_portfolio_html

# ── [Import Engine Modules] ─────────────────────────────────────────────
try:
    from data_engine.fetcher import GoldDataFetcher
    from data_engine.indicators import TechnicalIndicators
    from agent_core.core.react import ReactOrchestrator, ReactConfig
    from agent_core.core.prompt import PromptBuilder, RoleRegistry, SkillRegistry, AIRole
    from database import RunDatabase
except ImportError as e:
    print(f"⚠️  Import error: {e}")
    raise

try:
    from data_provider import gold_provider
except ImportError:
    gold_provider = None
from model_utils import model_registry, aggregate_signals, score_signal

load_dotenv()

# ─────────────────────────────────────────────
# Global init
# ─────────────────────────────────────────────
base_dir = os.path.dirname(os.path.abspath(__file__))

skill_registry = SkillRegistry()
skill_path = os.path.join(base_dir, "agent_core", "config", "skills.json")
skill_registry.load_from_json(skill_path)

role_registry = RoleRegistry(skill_registry)
role_path = os.path.join(base_dir, "agent_core", "config", "roles.json")
role_registry.load_from_json(role_path)

fetcher = GoldDataFetcher()
db = RunDatabase()

# สร้าง Portfolio Handlers จาก Module ใหม่
save_portfolio_fn, load_portfolio_to_form = create_portfolio_handlers(db)

# ─────────────────────────────────────────────
# UI Logic Functions
# ─────────────────────────────────────────────

def refresh_live_price() -> tuple[str, str]:
    try:
        price_data = gold_provider.get_spot_price()
        price_html = gold_provider.format_thai_display(price_data)
    except Exception as e:
        price_html = f"<p style='color:red'>❌ ดึงราคาไม่ได้: {e}</p>"

    try:
        model_html = model_registry.format_status_html()
    except Exception as e:
        model_html = f"<p style='color:red'>❌ โหลด model status ไม่ได้: {e}</p>"
    return price_html, model_html

def run_strategy_cycle(provider: str, period: str, interval: str) -> tuple:
    market_state = {}
    try:
        raw = fetcher.fetch_all(include_news=False, history_days=90, interval=interval)
        ohlcv_df = raw.get("ohlcv_df")
        if ohlcv_df is None or ohlcv_df.empty:
            return ("❌ No OHLCV data returned.",) + ("",) * 5

        indicators = TechnicalIndicators(ohlcv_df)
        indicators_dict = indicators.to_dict()
        spot = raw.get("spot_price", {}).get("price_usd_per_oz", "N/A")
        rsi = indicators_dict.get("rsi", {}).get("value", "N/A")
        macd = indicators_dict.get("macd", {})

        market_text = (
            f"💰 Gold (USD/oz)  : ${spot}\n📊 RSI(14)         : {rsi}\n"
            f"📈 MACD Line       : {macd.get('macd_line', 'N/A')}\n"
            f"📉 Signal Line     : {macd.get('signal_line', 'N/A')}\n"
            f"⏱️  Interval         : {interval}\n📅 Period          : {period}\n\n"
            f"🤖 Running AI Agent (ReAct)... ✅"
        )

        market_state = {
            "market_data": {"spot_price_usd": raw.get("spot_price", {}), "forex": raw.get("forex", {}), "thai_gold_thb": raw.get("thai_gold", {})},
            "technical_indicators": indicators_dict,
            "news": {"summary": {}, "by_category": {}},
            "portfolio": db.get_portfolio()
        }

        # ── [เพิ่มใหม่] Step 2.5: ดึง portfolio แล้วรวมเข้า market_state ──
        sys_logger.info("Step 2.5/5: Merging Portfolio Data...")

        portfolio = db.get_portfolio()
        market_state["portfolio"] = portfolio

        # ── Step 3: Agent ──────────────────────────────────────────────
        sys_logger.info(
            f"Step 3/5: Initializing ReAct Agent with provider '{provider}'..."
        )

        llm_client = LLMClientFactory.create(provider)
        prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)
        orchestrator = ReactOrchestrator(
            llm_client=llm_client, prompt_builder=prompt_builder, tool_registry={},
            config=ReactConfig(max_iterations=5, max_tool_calls=0)
        )
        result = orchestrator.run(market_state)

    except Exception as e:
        sys_logger.error(f"❌ Pipeline Error: {e}", exc_info=True)

        err = f"❌ Error: {e}\n{traceback.format_exc()}"
        return err, "", "", "", "", ""

    # ── Step 4: Save to DB ─────────────────────────────────────────────
    sys_logger.info("Step 4/5: Saving run history and results to Database...")

    try:
        db.save_run(provider, result, market_state, interval_tf=interval, period=period)

        fd = result.get("final_decision", {})
        trace_list = result.get("react_trace", [])
        signal = fd.get("signal", "HOLD")
        confidence = fd.get("confidence", 0.0)
        scored = score_signal(signal, confidence)

        verdict_text = (
            f"{SIGNAL_ICONS.get(signal, '🟡')} DECISION    : {signal}\n"
            f"   Confidence  : {confidence:.2%}\n   Strength    : {scored['strength']}\n"
            f"   Entry Price : ฿{fd.get('entry_price', 0):,.2f}\n"
            f"   Stop Loss   : ฿{fd.get('stop_loss', 0):,.2f}\n"
            f"   Take Profit : ฿{fd.get('take_profit', 0):,.2f}\n"
            f"\n💬 Rationale:\n{fd.get('rationale', '')}\n"
            f"\n📊 Stats:\n   Iterations  : {result.get('iterations_used', 0)}\n"
            f"   Tool Calls  : {result.get('tool_calls_used', 0)}"
        )

        return market_text, "", verdict_text, format_trace_html(trace_list), \
               format_history_html(db.get_recent_runs(50)), format_stats_html(db.get_signal_stats())
    except Exception as e:
        return (f"❌ Error: {e}\n{traceback.format_exc()}",) + ("",) * 5

# ใน dashboard.py มองหาฟังก์ชัน run_multi_interval

def run_multi_interval(provider: str, period: str, intervals: list[str]) -> tuple:
    """
    รันการวิเคราะห์ตามลำดับ Interval ที่เลือก และส่งค่ากลับไปยัง UI 
    รองรับ Output 7 ตำแหน่งตาม run_outputs ใน dashboard.py
    """
    if not intervals:
        # คืนค่าว่างให้ครบ 7 ตำแหน่ง (รวม multi_summary) เพื่อป้องกัน Gradio Error
        return ("⚠️ กรุณาเลือกอย่างน้อย 1 Interval", "", "", "", "", "", "<p style='color:red'>No intervals selected.</p>")

    summary_rows = []
    last_results = None

    for iv in intervals:
        try:
            # เรียกใช้ฟังก์ชันหลักของ v4
            # return: market_text, trace_text, verdict_text, explain_html, history_html, stats_html
            results = run_strategy_cycle(provider, period, iv)
            
            # ดึง Verdict มาแกะเพื่อทำตารางสรุป
            verdict = results[2]
            signal, conf, entry = "HOLD", "0%", "N/A"
            
            for line in verdict.splitlines():
                if "DECISION" in line:
                    signal = line.split(":")[-1].strip()
                elif "Confidence" in line:
                    conf = line.split(":")[-1].strip()
                elif "Entry Price" in line:
                    entry = line.split(":")[-1].strip()
            
            summary_rows.append({
                "interval": iv,
                "signal": signal,
                "conf": conf,
                "entry": entry,
                "ok": True
            })
            last_results = results  # เก็บผลลัพธ์รอบล่าสุดไว้โชว์ในช่องหลัก
            
        except Exception as e:
            sys_logger.error(f"Error during interval {iv}: {e}")
            summary_rows.append({
                "interval": iv,
                "signal": "ERROR",
                "conf": "-",
                "entry": str(e)[:30],
                "ok": False
            })

    # --- สร้าง HTML Table สำหรับ Multi-Interval Summary ---
    rows_html = []
    for r in summary_rows:
        sig_styled = r['signal'].replace("BUY", "🟢 BUY").replace("SELL", "🔴 SELL").replace("HOLD", "🟡 HOLD")
        row_bg = "#f0faf4" if "BUY" in r['signal'] else "#fff0f0" if "SELL" in r['signal'] else "#ffffff"
        
        rows_html.append(f"""
            <tr style="background:{row_bg}; border-bottom:1px solid #eee">
                <td style="padding:8px; font-weight:bold; font-family:monospace">{r['interval']}</td>
                <td style="padding:8px; font-weight:bold">{sig_styled}</td>
                <td style="padding:8px; text-align:right">{r['conf']}</td>
                <td style="padding:8px; text-align:right; font-family:monospace">{r['entry']}</td>
            </tr>
        """)

    now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%H:%M:%S")
    multi_html = f"""
    <div style="border:1px solid #ddd; border-radius:8px; padding:10px; background:#f9f9f9">
        <div style="font-size:12px; color:#666; margin-bottom:5px; font-family:monospace">
            🚀 Multi-scan Complete · {now} · {provider}
        </div>
        <table style="width:100%; border-collapse:collapse; font-size:13px">
            <tr style="background:#eee; text-align:left">
                <th style="padding:8px">TF</th>
                <th style="padding:8px">Signal</th>
                <th style="padding:8px; text-align:right">Confidence</th>
                <th style="padding:8px; text-align:right">Price</th>
            </tr>
            {"".join(rows_html)}
        </table>
    </div>
    """

    # --- การส่งค่ากลับ (CRITICAL) ---
    # ต้องมั่นใจว่า last_results มี 6 ค่า และบวก multi_html เข้าไปเป็นตัวที่ 7
    if last_results:
        return last_results + (multi_html,)
    
    return ("Error", "", "", "", "", "", multi_html)

def load_run_detail(run_id_str: str) -> tuple[str, str]:
    try:
        run_id = int(run_id_str.strip().lstrip("#"))
        detail = db.get_run_detail(run_id)
        if not detail: return "<p style='color:red'>Run not found</p>", ""
        return format_trace_html(detail.get("react_trace") or []), f"Run #{detail['id']} Detail"
    except: return "<p style='color:red'>Invalid ID</p>", ""

def refresh_history():
    return format_history_html(db.get_recent_runs(50)), format_stats_html(db.get_signal_stats())

def toggle_timer(enabled: bool): return STATUS_BADGE_ACTIVE if enabled else STATUS_BADGE_OFF

# ─────────────────────────────────────────────
# Gradio UI Construction
# ─────────────────────────────────────────────

with gr.Blocks(title="🟡 AI Gold Trading Agent") as demo:
    gr.Markdown("# 🟡 AI Gold Trading Agent Dashboard\n**ReAct LLM loop — real-time gold analysis**")
    gr.HTML(value=TRADINGVIEW_TICKER_HTML)

    with gr.Row():
        provider_dd = gr.Dropdown(PROVIDER_CHOICES, value="gemini", label="🤖 LLM Provider")
        period_dd = gr.Dropdown(PERIOD_CHOICES, value="7d", label="📅 Data Period")
        run_btn = gr.Button("▶ Run Analysis", variant="primary")
        auto_check = gr.Checkbox(label="⏰ Auto-run every 30 min", value=False)
 
    interval_cbs = gr.CheckboxGroup(choices=INTERVAL_CHOICES, value=["1h"], label="⏱️ Candle Intervals")
    auto_status = gr.HTML(value=STATUS_BADGE_OFF)
    timer = gr.Timer(value=900, active=True)

    with gr.Row():
        with gr.Column(scale=7): gr.HTML(TRADINGVIEW_CHART_HTML)
        with gr.Column(scale=3):
            live_price_html_dashboard = gr.HTML()
            model_status_html_dashboard = gr.HTML()
            price_refresh_btn_dashboard = gr.Button("🔄 Refresh Live Price", variant="secondary")
 
    with gr.Tabs():
        with gr.TabItem("📊 Live Analysis"):
            multi_summary = gr.HTML()
            with gr.Row():
                market_box = gr.Textbox(label="Market State", lines=9, interactive=False)
                trace_box = gr.Textbox(label="🧠 ReAct Trace", lines=15, interactive=False)
                verdict_box = gr.Textbox(label="🎯 Final Decision", lines=12, interactive=False)
            explain_html = gr.HTML(label="Step-by-step AI reasoning")

        with gr.TabItem("📜 Run History"):
            with gr.Row():
                stats_html, refresh_btn = gr.HTML(elem_id="stats-bar"), gr.Button("🔄 Refresh", scale=0)
            history_html = gr.HTML()
            run_id_input = gr.Textbox(label="Run ID", placeholder="#42")
            load_btn = gr.Button("Load")
            detail_trace, detail_fd = gr.HTML(), gr.Textbox(label="Decision summary", lines=8)

        with gr.TabItem("💼 Portfolio"):
            with gr.Row():
                pf_cash = gr.Number(label="💵 Cash Balance (฿)", value=1500.0)
                pf_gold = gr.Number(label="🥇 ทองคำคงเหลือ (กรัม)", value=0.0)
                pf_trade = gr.Number(label="🔄 Trades Today", value=0)
            with gr.Row():
                pf_cost, pf_curval, pf_pnl = gr.Number(label="📥 ต้นทุน"), gr.Number(label="📊 มูลค่าปัจจุบัน"), gr.Number(label="📈 PnL")
            with gr.Row():
                pf_save_btn, pf_reload_btn = gr.Button("💾 บันทึก Portfolio", variant="primary"), gr.Button("🔄 โหลดข้อมูล")
            pf_status, pf_display = gr.Textbox(label="Status"), gr.HTML()

    # ── [Events Wiring] ──────────────────────────────────────────────────
    run_btn.click(
    fn=run_multi_interval,
    inputs=[provider_dd, period_dd, interval_cbs],
    outputs=[
        market_box,    # 1
        trace_box,     # 2
        verdict_box,   # 3  <-- ตัวเจ้าปัญหา ต้องมั่นใจว่า last_results[2] คือ BUY/SELL
        explain_html,  # 4
        history_html,  # 5
        stats_html,    # 6
        multi_summary, # 7
        # ถ้ามี Live Price หรือตัวอื่นเพิ่มมาใน v4 ต้องใส่ให้ครบตำแหน่ง!
    ]
)
    
    auto_check.change(fn=toggle_timer, inputs=[auto_check], outputs=[auto_status])
    load_btn.click(fn=load_run_detail, inputs=[run_id_input], outputs=[detail_trace, detail_fd])
    refresh_btn.click(fn=refresh_history, outputs=[history_html, stats_html])
    price_refresh_btn_dashboard.click(fn=refresh_live_price, outputs=[live_price_html_dashboard, model_status_html_dashboard])
    
    pf_save_btn.click(fn=save_portfolio_fn, inputs=[pf_cash, pf_gold, pf_cost, pf_curval, pf_pnl, pf_trade], outputs=[pf_status, pf_display])
    pf_reload_btn.click(fn=load_portfolio_to_form, outputs=[pf_cash, pf_gold, pf_cost, pf_curval, pf_pnl, pf_trade, pf_display])

    demo.load(fn=refresh_history, outputs=[history_html, stats_html])
    demo.load(fn=lambda: format_portfolio_html(db.get_portfolio()), outputs=[pf_display])
    demo.load(fn=refresh_live_price, outputs=[live_price_html_dashboard, model_status_html_dashboard])

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0", 
        server_port=int(os.environ.get("PORT", 10000)),
        theme=gr.themes.Soft(),  
        css=CSS                
    )
