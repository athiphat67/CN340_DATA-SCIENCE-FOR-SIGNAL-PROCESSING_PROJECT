"""
ui/dashboard.py — Gradio Dashboard for goldtrader Agent
Wires together: Data → Indicators → Agent → Risk Manager → Results
"""

import os
import json
import traceback
import gradio as gr
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────
# Imports (assuming correct module paths exist)
# ─────────────────────────────────────────────────────────────────────

try:
    from data_engine.fetcher import GoldDataFetcher  # ✅ Correct class name
    from data_engine.indicators import TechnicalIndicators  # ✅ Correct class name
    from agent_core.llm.client import LLMClientFactory  # ✅ Use factory
    from agent_core.core.react import ReactOrchestrator, ReactConfig
    from agent_core.core.prompt import PromptBuilder, RoleRegistry, SkillRegistry, AIRole
except ImportError as e:
    print(f"⚠️  Import error: {e}")
    print("Make sure you're running from Src/ directory")
    raise

load_dotenv()

# ─────────────────────────────────────────────────────────────────────
# Global Components (initialized once)
# ─────────────────────────────────────────────────────────────────────

# Load config registries
skill_registry = SkillRegistry()
skill_registry.load_from_json("agent_core/config/skills.json")

role_registry = RoleRegistry(skill_registry)
role_registry.load_from_json("agent_core/config/roles.json")

# Fetcher (reusable)
fetcher = GoldDataFetcher()


# ─────────────────────────────────────────────────────────────────────
# Core Function: Strategy Cycle
# ─────────────────────────────────────────────────────────────────────

def run_strategy_cycle(provider: str, period: str, interval: str) -> tuple[str, str, str]:
    """
    Full pipeline: Fetch → Indicators → LLM Agent → Risk Validation → Results

    Args:
        provider: LLM provider (gemini, claude, openai, groq, deepseek, mock)
        period: Data period (1d, 5d, 7d, 1mo)
        interval: Candle interval (15m, 30m, 1h, 4h, 1d)

    Returns:
        (market_summary, agent_trace, final_verdict): 3-tuple for display
    """
    try:
        # ── Step 1: Fetch Market Data ───────────────────────────────────
        market_summary = "📡 Fetching market data...\n"
        try:
            raw = fetcher.fetch_all(
                include_news=False,
                history_days=90,
                interval=interval,
            )
            ohlcv_df = raw.get("ohlcv_df")
            spot_data = raw.get("spot_price", {})
            forex_data = raw.get("forex", {})
            thai_gold = raw.get("thai_gold", {})

            if ohlcv_df is None or ohlcv_df.empty:
                return "❌ No OHLCV data returned from fetcher.", "", ""
        except Exception as e:
            return f"❌ Data fetch error: {e}\n{traceback.format_exc()}", "", ""

        # ── Step 2: Calculate Indicators ────────────────────────────────
        market_summary += "🔢 Calculating technical indicators...\n"
        try:
            indicators = TechnicalIndicators(ohlcv_df)
            indicators_dict = indicators.to_dict()
        except Exception as e:
            return f"❌ Indicator calculation error: {e}", "", ""

        # Format market summary for display
        spot = spot_data.get("price_usd_per_oz", "N/A")
        rsi = indicators_dict.get("rsi", {}).get("value", "N/A")
        macd = indicators_dict.get("macd", {})
        macd_line = macd.get("macd_line", "N/A")
        signal_line = macd.get("signal_line", "N/A")

        market_summary = (
            f"💰 Gold Price (USD/oz) : ${spot}\n"
            f"📊 RSI (14)            : {rsi}\n"
            f"📈 MACD Line           : {macd_line}\n"
            f"📉 Signal Line         : {signal_line}\n"
            f"⏱️  Interval            : {interval}\n"
            f"📅 Period              : {period}"
        )

        # ── Step 3: Create Market State JSON ────────────────────────────
        market_state = {
            "market_data": {
                "spot_price_usd": spot_data,
                "forex": forex_data,
                "thai_gold_thb": thai_gold,
            },
            "technical_indicators": indicators_dict,
            "news": {"summary": {}, "by_category": {}},  # Simplified for UI
        }

        # ── Step 4: Create LLM Client & Run Agent ──────────────────────
        market_summary += "\n\n🤖 Running AI Agent (ReAct)...\n"
        try:
            llm_client = LLMClientFactory.create(provider)
            
            prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)
            
            react_config = ReactConfig(
                max_iterations=5,
                max_tool_calls=0,  # Data pre-loaded
                timeout_seconds=None,
            )
            
            # Empty tool registry (no tool calls in this demo)
            tool_registry = {}
            
            orchestrator = ReactOrchestrator(
                llm_client=llm_client,
                prompt_builder=prompt_builder,
                tool_registry=tool_registry,
                config=react_config,
            )
            
            result = orchestrator.run(market_state)
        except Exception as e:
            return (
                market_summary,
                f"❌ Agent error: {e}\n{traceback.format_exc()}",
                "",
            )

        # ── Step 5: Format Agent Trace ──────────────────────────────────
        agent_trace_lines = []
        for trace_entry in result.get("react_trace", []):
            step = trace_entry.get("step", "?")
            iteration = trace_entry.get("iteration", "?")
            response = trace_entry.get("response", {})

            agent_trace_lines.append(f"\n── {step} (Iteration {iteration}) ──")
            
            # Show relevant response fields
            if response:
                action = response.get("action", "?")
                thought = response.get("thought", "")
                agent_trace_lines.append(f"Action: {action}")
                if thought:
                    agent_trace_lines.append(f"Thought: {thought[:200]}...")  # Truncate for UI
            
            if "observation" in trace_entry:
                agent_trace_lines.append(f"Observation: {trace_entry['observation']}")

        agent_trace = "\n".join(agent_trace_lines) if agent_trace_lines else "No trace available."

        # ── Step 6: Format Final Decision ───────────────────────────────
        final_decision = result.get("final_decision", {})
        
        signal = final_decision.get("signal", "HOLD")
        confidence = final_decision.get("confidence", 0.0)
        entry_price = final_decision.get("entry_price")
        stop_loss = final_decision.get("stop_loss")
        take_profit = final_decision.get("take_profit")
        rationale = final_decision.get("rationale", "No rationale provided")

        # Status icon
        signal_icon = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"

        # ✅ Fix: Separate the variables before formatting the string
        entry_str = f"${entry_price:.2f}" if entry_price else "N/A"
        sl_str = f"${stop_loss:.2f}" if stop_loss else "N/A"
        tp_str = f"${take_profit:.2f}" if take_profit else "N/A"

        verdict = (
            f"{signal_icon} DECISION      : {signal}\n"
            f"   Confidence   : {confidence:.2%}\n"
            f"   Entry Price  : {entry_str}\n"
            f"   Stop Loss    : {sl_str}\n"
            f"   Take Profit  : {tp_str}\n"
            f"\n💬 Rationale:\n{rationale}\n"
            f"\n📊 Stats:\n"
            f"   Iterations   : {result.get('iterations_used', 0)}\n"
            f"   Tool Calls   : {result.get('tool_calls_used', 0)}"
        )

        market_summary += " ✅"
        return market_summary, agent_trace, verdict

    except Exception as e:
        err_msg = f"❌ Unexpected error: {e}\n{traceback.format_exc()}"
        return err_msg, err_msg, err_msg


# ─────────────────────────────────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────────────────────────────────

PROVIDER_CHOICES = ["gemini", "groq", "mock"]
PERIOD_CHOICES = ["1d", "5d", "7d", "1mo"]
INTERVAL_CHOICES = ["15m", "30m", "1h", "4h", "1d"]

with gr.Blocks(
    title="🟡 AI Gold Trading Agent",
    theme=gr.themes.Soft(
        font=[gr.themes.GoogleFont("Kanit"), "ui-sans-serif", "system-ui", "sans-serif"],
        font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "ui-monospace", "monospace"],
    ),
    css="""
    .header { text-align: center; margin: 20px 0; }
    .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
    """
) as demo:
    gr.Markdown(
        """
        # 🟡 AI Gold Trading Agent Dashboard
        **Real-time market analysis powered by ReAct LLM loop**
        
        *Fetch gold price data → Calculate indicators → Run multi-step reasoning → Output trading decision*
        """,
        elem_classes="header"
    )

    # Input row: Provider, Period, Interval, Run button
    with gr.Row():
        with gr.Column(scale=1):
            provider_dd = gr.Dropdown(
                choices=PROVIDER_CHOICES,
                value="gemini",
                label="🤖 LLM Provider",
                info="Select AI model for reasoning",
            )
        with gr.Column(scale=1):
            period_dd = gr.Dropdown(
                choices=PERIOD_CHOICES,
                value="7d",
                label="📅 Data Period",
                info="Historical lookback",
            )
        with gr.Column(scale=1):
            interval_dd = gr.Dropdown(
                choices=INTERVAL_CHOICES,
                value="1h",
                label="⏱️ Candle Interval",
                info="Timeframe",
            )
        with gr.Column(scale=0.8):
            run_btn = gr.Button(
                "▶ Run Analysis",
                variant="primary",
                scale=2,
            )

    gr.Markdown("---")

    # Output row: 3-panel display
    with gr.Row():
        with gr.Column(scale=1):
            market_box = gr.Textbox(
                label="📊 Market State",
                lines=8,
                interactive=False,
            )
        with gr.Column(scale=2):
            trace_box = gr.Textbox(
                label="🧠 ReAct Reasoning Trace",
                lines=15,
                interactive=False,
            )
        with gr.Column(scale=1):
            verdict_box = gr.Textbox(
                label="🎯 Final Decision",
                lines=12,
                interactive=False,
            )

    # Button click event
    run_btn.click(
        fn=run_strategy_cycle,
        inputs=[provider_dd, period_dd, interval_dd],
        outputs=[market_box, trace_box, verdict_box],
        api_name="analyze",
    )

    gr.Markdown(
        """
        ---
        **How to use:**
        1. Select an LLM provider (ensure API key is set in .env)
        2. Choose data period and candle interval
        3. Click "Run Analysis" to fetch data and execute ReAct loop
        4. View results in the 3-panel dashboard
        """,
        elem_classes="footer"
    )


# ─────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🟡 goldtrader Dashboard")
    print("="*60)
    print("📍 Access at: http://localhost:7860")
    print("⚠️  Make sure you're running from Src/ directory")
    print("⚠️  Ensure .env has LLM API keys set")
    print("="*60 + "\n")
    
    demo.launch(
        share=False,
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
    )
