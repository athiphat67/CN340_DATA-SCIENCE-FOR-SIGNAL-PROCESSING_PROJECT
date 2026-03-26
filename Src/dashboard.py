"""
dashboard.py — Goldtrader Dashboard v2
Adds: Run History (SQLite) + Explainability Panel (full ReAct trace)
Token cost: +0 API calls — trace reuses data already in result dict
"""

import os
import json
import traceback
import gradio as gr
from dotenv import load_dotenv

try:
    from data_engine.fetcher import GoldDataFetcher
    from data_engine.indicators import TechnicalIndicators
    from agent_core.llm.client import LLMClientFactory
    from agent_core.core.react import ReactOrchestrator, ReactConfig
    from agent_core.core.prompt import PromptBuilder, RoleRegistry, SkillRegistry, AIRole
    from database import RunDatabase
except ImportError as e:
    print(f"⚠️  Import error: {e}")
    raise

load_dotenv()

# ─────────────────────────────────────────────
# Global init
# ─────────────────────────────────────────────

skill_registry = SkillRegistry()
skill_registry.load_from_json("agent_core/config/skills.json")

role_registry = RoleRegistry(skill_registry)
role_registry.load_from_json("agent_core/config/roles.json")

fetcher = GoldDataFetcher()
db = RunDatabase("runs/history.db")

# ─────────────────────────────────────────────
# Trace formatter helpers — zero API cost
# ─────────────────────────────────────────────

def _signal_icon(signal: str) -> str:
    return {"BUY": "🟢", "SELL": "🔴"}.get(signal, "🟡")


def format_trace_html(react_trace: list) -> str:
    """
    Convert react_trace list → rich HTML for gr.HTML component.
    No LLM call — just format existing data.
    """
    if not react_trace:
        return "<p style='color:#888'>No trace data available.</p>"

    parts = []
    for entry in react_trace:
        step      = entry.get("step", "?")
        iteration = entry.get("iteration", "?")
        response  = entry.get("response", {})
        note      = entry.get("note", "")

        # Step header colour
        if "FINAL" in step:
            hdr_color = "#1a7a4a"
            bg_color  = "#f0faf4"
            border    = "#4caf7d"
        elif step == "TOOL_EXECUTION":
            hdr_color = "#7a5c1a"
            bg_color  = "#fdfaf0"
            border    = "#c9a84c"
        else:
            hdr_color = "#1a4a7a"
            bg_color  = "#f0f6fa"
            border    = "#4c84af"

        action  = response.get("action", entry.get("tool_name", ""))
        thought = response.get("thought", "")

        # Build card
        card = f"""
        <div style="
            margin: 10px 0;
            border-left: 4px solid {border};
            border-radius: 8px;
            background: {bg_color};
            padding: 12px 16px;
            font-family: monospace;
            font-size: 13px;
        ">
            <div style="
                color: {hdr_color};
                font-weight: bold;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 6px;
            ">
                {step} · iteration {iteration}
                {"&nbsp;— " + note if note else ""}
            </div>
        """

        if action:
            card += f"<div style='margin-bottom:4px'><b>Action:</b> <code>{action}</code></div>"

        if thought:
            card += f"<div style='margin-bottom:4px'><b>Thought:</b> {thought}</div>"

        # FINAL_DECISION fields
        if response.get("signal"):
            sig  = response["signal"]
            conf = response.get("confidence", 0)
            card += f"""
            <div style="margin-top:8px; padding:8px; background:rgba(0,0,0,0.04); border-radius:6px;">
                <span style="font-weight:bold">{_signal_icon(sig)} {sig}</span>
                &nbsp;· confidence: <b>{conf:.0%}</b>
                {f" · entry: ${response.get('entry_price')}" if response.get('entry_price') else ""}
            </div>
            """

        # TOOL_EXECUTION observation
        if "observation" in entry:
            obs = entry["observation"]
            status = obs.get("status", "?")
            status_color = "#1a7a4a" if status == "success" else "#b22222"
            card += f"""
            <div style="margin-top:6px">
                <b>Observation:</b>
                <span style="color:{status_color}; font-weight:bold">[{status}]</span>
                {str(obs.get("data") or obs.get("error", ""))[:300]}
            </div>
            """

        card += "</div>"
        parts.append(card)

    return "\n".join(parts)


def format_history_html(rows: list[dict]) -> str:
    """Render run history as HTML table — loaded from DB, zero API cost."""
    if not rows:
        return "<p style='color:#888;padding:16px'>No runs recorded yet.</p>"

    header = """
    <table style="width:100%; border-collapse:collapse; font-size:13px; font-family:monospace">
    <thead>
    <tr style="background:#f4f4f4; border-bottom:2px solid #ddd">
        <th style="padding:8px;text-align:left">ID</th>
        <th style="padding:8px;text-align:left">Time (UTC)</th>
        <th style="padding:8px;text-align:left">Provider</th>
        <th style="padding:8px;text-align:left">TF</th>
        <th style="padding:8px;text-align:center">Signal</th>
        <th style="padding:8px;text-align:right">Conf</th>
        <th style="padding:8px;text-align:right">Price</th>
        <th style="padding:8px;text-align:right">RSI</th>
        <th style="padding:8px;text-align:right">Iter</th>
    </tr>
    </thead><tbody>
    """
    rows_html = []
    for r in rows:
        sig   = r.get("signal", "HOLD")
        icon  = _signal_icon(sig)
        conf  = r.get("confidence")
        conf_str  = f"{conf:.0%}" if conf is not None else "—"
        price_str = f"${r['gold_price']:.0f}" if r.get("gold_price") else "—"
        rsi_str   = f"{r['rsi']:.1f}" if r.get("rsi") else "—"
        ts    = (r.get("run_at") or "")[:19].replace("T", " ")

        rows_html.append(f"""
        <tr style="border-bottom:1px solid #eee">
            <td style="padding:6px 8px; color:#666">#{r['id']}</td>
            <td style="padding:6px 8px">{ts}</td>
            <td style="padding:6px 8px">{r.get('provider','')}</td>
            <td style="padding:6px 8px">{r.get('interval_tf','')}</td>
            <td style="padding:6px 8px; text-align:center">{icon} {sig}</td>
            <td style="padding:6px 8px; text-align:right">{conf_str}</td>
            <td style="padding:6px 8px; text-align:right">{price_str}</td>
            <td style="padding:6px 8px; text-align:right">{rsi_str}</td>
            <td style="padding:6px 8px; text-align:right">{r.get('iterations_used','')}</td>
        </tr>
        """)

    return header + "".join(rows_html) + "</tbody></table>"


def format_stats_html(stats: dict) -> str:
    total = stats["total"]
    if total == 0:
        return "<span style='color:#888'>No data yet</span>"
    buy_pct  = stats["buy_count"]  / total * 100
    sell_pct = stats["sell_count"] / total * 100
    hold_pct = stats["hold_count"] / total * 100
    return (
        f"<span style='font-family:monospace;font-size:13px'>"
        f"<b>{total}</b> runs &nbsp;·&nbsp; "
        f"🟢 BUY {stats['buy_count']} ({buy_pct:.0f}%) &nbsp; "
        f"🔴 SELL {stats['sell_count']} ({sell_pct:.0f}%) &nbsp; "
        f"🟡 HOLD {stats['hold_count']} ({hold_pct:.0f}%) &nbsp;·&nbsp; "
        f"avg conf <b>{stats['avg_confidence']:.0%}</b> &nbsp; "
        f"avg price <b>${stats['avg_price']:.0f}</b>"
        f"</span>"
    )


# ─────────────────────────────────────────────
# Core pipeline (unchanged logic, added DB save + trace HTML)
# ─────────────────────────────────────────────

def run_strategy_cycle(
    provider: str, period: str, interval: str
) -> tuple[str, str, str, str, str, str]:
    """
    Returns 6 outputs:
      market_text, trace_html, verdict_text,
      explain_html, history_html, stats_html
    """
    market_state = {}
    result = {}

    try:
        # ── Step 1: Fetch ──────────────────────────────────────────────
        raw = fetcher.fetch_all(include_news=False, history_days=90, interval=interval)
        ohlcv_df   = raw.get("ohlcv_df")
        spot_data  = raw.get("spot_price", {})
        forex_data = raw.get("forex", {})
        thai_gold  = raw.get("thai_gold", {})

        if ohlcv_df is None or ohlcv_df.empty:
            err = "❌ No OHLCV data returned."
            return err, "", "", "", "", ""

        # ── Step 2: Indicators ─────────────────────────────────────────
        indicators = TechnicalIndicators(ohlcv_df)
        indicators_dict = indicators.to_dict()

        spot = spot_data.get("price_usd_per_oz", "N/A")
        rsi  = indicators_dict.get("rsi", {}).get("value", "N/A")
        macd = indicators_dict.get("macd", {})

        market_text = (
            f"💰 Gold (USD/oz)  : ${spot}\n"
            f"📊 RSI(14)         : {rsi}\n"
            f"📈 MACD Line       : {macd.get('macd_line', 'N/A')}\n"
            f"📉 Signal Line     : {macd.get('signal_line', 'N/A')}\n"
            f"⏱️  Interval         : {interval}\n"
            f"📅 Period          : {period}\n\n"
            f"🤖 Running AI Agent (ReAct)... ✅"
        )

        market_state = {
            "market_data": {
                "spot_price_usd": spot_data,
                "forex":          forex_data,
                "thai_gold_thb":  thai_gold,
            },
            "technical_indicators": indicators_dict,
            "news": {"summary": {}, "by_category": {}},
        }

        # ── Step 3: Agent ──────────────────────────────────────────────
        llm_client     = LLMClientFactory.create(provider)
        prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)
        orchestrator   = ReactOrchestrator(
            llm_client=llm_client,
            prompt_builder=prompt_builder,
            tool_registry={},
            config=ReactConfig(max_iterations=5, max_tool_calls=0),
        )
        result = orchestrator.run(market_state)

    except Exception as e:
        err = f"❌ Error: {e}\n{traceback.format_exc()}"
        return err, "", "", "", "", ""

    # ── Step 4: Save to DB ─────────────────────────────────────────────
    # try:
    #     db.save_run(provider, result, market_state, interval_tf=interval, period=period)
    # except Exception as e:
    #     print(f"[DB] Save failed: {e}")

    # ── Step 5: Format outputs ─────────────────────────────────────────
    fd         = result.get("final_decision", {})
    trace_list = result.get("react_trace", [])

    # Simple text trace (existing panel)
    simple_trace_lines = []
    for entry in trace_list:
        step       = entry.get("step", "?")
        iteration  = entry.get("iteration", "?")
        response   = entry.get("response", {})
        simple_trace_lines.append(f"\n── {step} (Iteration {iteration}) ──")
        if response:
            simple_trace_lines.append(f"Action: {response.get('action','?')}")
            thought = response.get("thought", "")
            if thought:
                simple_trace_lines.append(f"Thought: {thought[:300]}")
    trace_text = "\n".join(simple_trace_lines) or "No trace."

    # Verdict text
    signal      = fd.get("signal", "HOLD")
    confidence  = fd.get("confidence", 0.0)
    entry_price = fd.get("entry_price")
    stop_loss   = fd.get("stop_loss")
    take_profit = fd.get("take_profit")
    rationale   = fd.get("rationale", "")

    entry_str = f"${entry_price:.2f}" if entry_price else "N/A"
    sl_str    = f"${stop_loss:.2f}"   if stop_loss   else "N/A"
    tp_str    = f"${take_profit:.2f}" if take_profit else "N/A"

    verdict_text = (
        f"{_signal_icon(signal)} DECISION    : {signal}\n"
        f"   Confidence  : {confidence:.2%}\n"
        f"   Entry Price : {entry_str}\n"
        f"   Stop Loss   : {sl_str}\n"
        f"   Take Profit : {tp_str}\n"
        f"\n💬 Rationale:\n{rationale}\n"
        f"\n📊 Stats:\n"
        f"   Iterations  : {result.get('iterations_used', 0)}\n"
        f"   Tool Calls  : {result.get('tool_calls_used', 0)}"
    )

    # Rich HTML trace (Explainability tab)
    explain_html = format_trace_html(trace_list)

    # Updated history + stats
    history_html = format_history_html(db.get_recent_runs(50))
    stats_html   = format_stats_html(db.get_signal_stats())

    return market_text, trace_text, verdict_text, explain_html, history_html, stats_html


def load_run_detail(run_id_str: str) -> tuple[str, str]:
    """
    Load full trace + rationale for a specific run_id.
    Zero API cost — reads from SQLite only.
    """
    try:
        run_id = int(run_id_str.strip().lstrip("#"))
    except ValueError:
        return "<p style='color:red'>Invalid run ID</p>", ""

    detail = db.get_run_detail(run_id)
    if not detail:
        return f"<p style='color:red'>Run #{run_id} not found</p>", ""

    trace_html = format_trace_html(detail.get("react_trace") or [])
    fd_text = (
        f"Run #{detail['id']} · {detail.get('run_at','')} · {detail.get('provider','')}\n\n"
        f"{_signal_icon(detail.get('signal','HOLD'))} {detail.get('signal','HOLD')} "
        f"| Conf: {(detail.get('confidence') or 0):.0%} "
        f"| Gold: ${detail.get('gold_price') or 0:.0f} "
        f"| RSI: {detail.get('rsi') or 'N/A'}\n\n"
        f"Rationale:\n{detail.get('rationale','')}"
    )
    return trace_html, fd_text


def refresh_history() -> tuple[str, str]:
    """Reload history table from DB — no API call."""
    return format_history_html(db.get_recent_runs(50)), format_stats_html(db.get_signal_stats())


# ─────────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────────

PROVIDER_CHOICES = ["gemini", "groq", "mock"]
PERIOD_CHOICES   = ["1d", "5d", "7d", "1mo"]
INTERVAL_CHOICES = ["15m", "30m", "1h", "4h", "1d"]

CSS = """
.tab-nav button { font-size: 14px !important; }
.trace-card { font-family: monospace; }
#stats-bar { padding: 8px 12px; background: #f8f8f8; border-radius: 8px; }
"""

with gr.Blocks(title="🟡 AI Gold Trading Agent", theme=gr.themes.Soft(), css=CSS) as demo:
    gr.Markdown("# 🟡 AI Gold Trading Agent Dashboard\n**ReAct LLM loop — real-time gold analysis**")

    # ── Controls ───────────────────────────────────────────────────────
    with gr.Row():
        provider_dd  = gr.Dropdown(PROVIDER_CHOICES, value="gemini",  label="🤖 LLM Provider")
        period_dd    = gr.Dropdown(PERIOD_CHOICES,   value="7d",      label="📅 Data Period")
        interval_dd  = gr.Dropdown(INTERVAL_CHOICES, value="1h",      label="⏱️ Candle Interval")
        run_btn      = gr.Button("▶ Run Analysis", variant="primary")

    # ── Tabs ───────────────────────────────────────────────────────────
    with gr.Tabs():

        # Tab 1 — Live Analysis (existing layout + explain panel)
        with gr.TabItem("📊 Live Analysis"):
            with gr.Row():
                market_box  = gr.Textbox(label="Market State",         lines=9,  interactive=False)
                trace_box   = gr.Textbox(label="🧠 ReAct Trace",       lines=15, interactive=False)
                verdict_box = gr.Textbox(label="🎯 Final Decision",    lines=12, interactive=False)

            gr.Markdown("### 🔍 Explainability — Full ReAct Reasoning")
            explain_html = gr.HTML(label="Step-by-step AI reasoning")

        # Tab 2 — Run History
        with gr.TabItem("📜 Run History"):
            with gr.Row():
                stats_html   = gr.HTML(elem_id="stats-bar")
                refresh_btn  = gr.Button("🔄 Refresh", scale=0)

            history_html = gr.HTML()

            gr.Markdown("### 🔎 Load Run Detail")
            with gr.Row():
                run_id_input  = gr.Textbox(label="Run ID (e.g. #42)", placeholder="#42", scale=1)
                load_btn      = gr.Button("Load", scale=0)

            with gr.Row():
                detail_trace  = gr.HTML(label="Trace for selected run")
                detail_fd     = gr.Textbox(label="Decision summary", lines=8, interactive=False)

    # ── Wire events ────────────────────────────────────────────────────
    run_outputs = [market_box, trace_box, verdict_box, explain_html, history_html, stats_html]

    run_btn.click(
        fn=run_strategy_cycle,
        inputs=[provider_dd, period_dd, interval_dd],
        outputs=run_outputs,
        api_name="analyze",
    )

    load_btn.click(
        fn=load_run_detail,
        inputs=[run_id_input],
        outputs=[detail_trace, detail_fd],
    )

    refresh_btn.click(
        fn=refresh_history,
        inputs=[],
        outputs=[history_html, stats_html],
    )

    # Load history on startup
    demo.load(
        fn=refresh_history,
        outputs=[history_html, stats_html],
    )

# ─────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # ใช้ os.environ.get เพื่อดึง PORT จาก Render (ถ้าไม่มีให้ใช้ 7860)
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, show_error=True)