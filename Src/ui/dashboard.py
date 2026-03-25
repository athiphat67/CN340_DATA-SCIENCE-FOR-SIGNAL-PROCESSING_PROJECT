"""
ui/dashboard.py
Gradio dashboard — wires together the full pipeline end-to-end.
"""

import os
import json
import gradio as gr
from dotenv import load_dotenv

from data_engine.fetcher import DataFetcher
from data_engine.indicators import MathEngine
from agent_core.main.orchestrator import AgentOrchestrator
from execution.risk_manager import RiskManager
from execution.router import TradeRouter

load_dotenv()

# ------------------------------------------------------------------ #
# Component initialisation                                            #
# ------------------------------------------------------------------ #
fetcher   = DataFetcher()
math_eng  = MathEngine()
risk_mgr  = RiskManager(balance=100_000, max_pos_pct=0.10)
router    = TradeRouter(risk_manager=risk_mgr)


def run_strategy_cycle(period: str, interval: str) -> tuple[str, str, str]:
    """
    Full pipeline:
        fetch → indicators → agent → validate → return results
    Returns (market_summary, agent_trace, final_verdict)
    """
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return "❌ GOOGLE_API_KEY not set in .env", "", ""

    logs: list[str] = []

    # 1. Fetch market data
    logs.append("📡 Fetching market data...")
    try:
        df = fetcher.get_gold_data(period=period, interval=interval)
        if df.empty:
            return "❌ No price data returned from yfinance.", "", ""
    except Exception as e:
        return f"❌ Data fetch error: {e}", "", ""

    # 2. Calculate indicators
    logs.append("🔢 Calculating indicators (RSI, MACD)...")
    try:
        metrics = math_eng.calculate_metrics(df)
    except Exception as e:
        return f"❌ Indicator calculation error: {e}", "", ""

    # Update live price in risk manager
    risk_mgr.update_gold_price(metrics["price"])

    market_summary = (
        f"💰 Gold Price : ${metrics['price']:,.2f}\n"
        f"📊 RSI (14)   : {metrics['rsi']}\n"
        f"📈 MACD       : {metrics['macd']}\n"
        f"📉 Signal     : {metrics['signal']}\n"
        f"🎯 Max lots   : {risk_mgr.max_lots():.2f}"
    )
    logs.append(f"Market state built:\n{market_summary}")

    # 3. Run AI agent (ReAct loop)
    logs.append("🤖 Running AI Agent (ReAct)...")
    try:
        agent = AgentOrchestrator(api_key=api_key)
        raw_decision = agent.run_cycle(metrics)
    except Exception as e:
        return market_summary, f"❌ Agent error: {e}", ""

    # Build trace string
    trace_lines: list[str] = []
    for step in raw_decision.get("trace", []):
        trace_lines.append(f"── Step {step['step']} ──")
        trace_lines.append(step.get("llm_output", ""))
        if "tool" in step:
            trace_lines.append(f"  🔧 Tool: {step['tool']}")
            trace_lines.append(f"  👁 Observation: {step['observation']}")
    agent_trace = "\n".join(trace_lines) if trace_lines else "No trace available."

    # 4. Route & validate
    logs.append("🛡️ Validating trade via Risk Manager...")
    result = router.route(raw_decision)

    status_icon = "✅" if result["status"] == "APPROVED" else "🚫"
    decision    = result.get("decision", raw_decision)
    verdict = (
        f"{status_icon} Status   : {result['status']}\n"
        f"   Reason  : {result['reason']}\n\n"
        f"   Action  : {decision.get('action', 'N/A')}\n"
        f"   Quantity: {decision.get('quantity', 0)} lots\n\n"
        f"💬 Reasoning:\n{decision.get('reasoning', '')}"
    )

    return market_summary, agent_trace, verdict


# ------------------------------------------------------------------ #
# Gradio UI                                                           #
# ------------------------------------------------------------------ #
PERIOD_CHOICES   = ["1d", "5d", "7d", "1mo"]
INTERVAL_CHOICES = ["15m", "30m", "1h", "4h"]

with gr.Blocks(title="🟡 AI Gold Trading Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🟡 AI Gold Trading Agent
        *Powered by Gemini 1.5 Pro · RSI · MACD · ReAct Loop*
        """
    )

    with gr.Row():
        period_dd   = gr.Dropdown(PERIOD_CHOICES,   value="7d",  label="Data Period")
        interval_dd = gr.Dropdown(INTERVAL_CHOICES, value="1h",  label="Candle Interval")
        run_btn     = gr.Button("▶ Run Strategy Cycle", variant="primary")

    gr.Markdown("---")

    with gr.Row():
        with gr.Column(scale=1):
            market_box = gr.Textbox(label="📊 Market State", lines=7, interactive=False)
        with gr.Column(scale=2):
            trace_box  = gr.Textbox(label="🤖 Agent Reasoning Trace", lines=15, interactive=False)
        with gr.Column(scale=1):
            verdict_box = gr.Textbox(label="🎯 Final Decision", lines=10, interactive=False)

    run_btn.click(
        fn=run_strategy_cycle,
        inputs=[period_dd, interval_dd],
        outputs=[market_box, trace_box, verdict_box],
    )

if __name__ == "__main__":
    demo.launch(share=False)
