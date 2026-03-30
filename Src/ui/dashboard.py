"""
ui/dashboard.py v3.2 (REFACTORED)
Pure Gradio UI layer — Business logic moved to core/services.py

Responsibilities:
✅ Gradio component definitions
✅ Event wiring (callbacks)
✅ Rendering results via core/renderers.py
✅ User input/output handling

NOT responsible for:
❌ Business logic (→ core/services.py)
❌ HTML formatting (→ core/renderers.py)
❌ Configuration (→ core/config.py)
❌ Utilities (→ core/utils.py)
"""

import os
import gradio as gr
from dotenv import load_dotenv

import sys
from ui.navbar import NavbarBuilder, AppContext  # also triggers page registration

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_setup import sys_logger, log_method

# ✅ Import from refactored modules
from core import (
    init_services,
    UI_CONFIG,
    PROVIDER_CHOICES,
    PERIOD_CHOICES,
    INTERVAL_CHOICES,
    AUTO_RUN_INTERVALS,
    DEFAULT_AUTO_RUN,
)
from core.renderers import (
    TraceRenderer,
    HistoryRenderer,
    PortfolioRenderer,
    StatsRenderer,
    StatusRenderer,
)

from core.chart_renderer import ChartTabRenderer      
from core.chart_service  import chart_service

from core.utils import (
    format_voting_summary,
    format_error_message,
)

try:
    from data_engine.orchestrator import GoldTradingOrchestrator
    from agent_core.core.prompt import RoleRegistry, SkillRegistry
    from database import RunDatabase
except ImportError as e:
    sys_logger.error(f"⚠️  Import error: {e}")
    raise

load_dotenv()

# ─────────────────────────────────────────────
# Global Initialization
# ─────────────────────────────────────────────

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Registries
skill_registry = SkillRegistry()
skill_registry.load_from_json(
    os.path.join(base_dir, "agent_core", "config", "skills.json")
)

role_registry = RoleRegistry(skill_registry)
role_registry.load_from_json(
    os.path.join(base_dir, "agent_core", "config", "roles.json")
)

print("Registered roles:", list(role_registry.roles.keys()))
print("Registered skills:", list(skill_registry.skills.keys()))

# Data + Database
orchestrator = GoldTradingOrchestrator()
db = RunDatabase()

# Services (business logic)
services = init_services(skill_registry, role_registry, orchestrator, db)

ctx = AppContext(services=services, orchestrator=orchestrator, db=db)

sys_logger.info("Dashboard initialized")

# ─────────────────────────────────────────────
# Event Handlers (Callbacks)
# ─────────────────────────────────────────────


@log_method(sys_logger)
def handle_run_analysis(provider: str, period: str, interval: str):
    """Handle 'Run Analysis' button click - calls AnalysisService"""
    try:
        result = services["analysis"].run_analysis(provider, period, [interval])

        # Handle error response
        if result["status"] == "error":
            error_msg = format_error_message(result)
            error_badge = StatusRenderer.error_badge(
                error_msg, is_validation=(result.get("error_type") == "validation")
            )
            return ("", "", error_msg, error_badge, "", "", "", error_badge)

        # Extract successful data
        voting_result = result["voting_result"]
        interval_results = result["data"]["interval_results"]

        # Format outputs
        market_txt = str(result["data"]["market_state"])[:1000]
        voting_summary = format_voting_summary(voting_result)

        final_decision_txt = f"""{voting_summary}

        Final Signal: {voting_result['final_signal']}
        Confidence: {voting_result['weighted_confidence']:.1%}

        Per-Interval Details:
        """
        for iv, ir in interval_results.items():
            icon = {"BUY": "🟢", "SELL": "🔴"}.get(ir["signal"], "🟡")
            final_decision_txt += (
                f"  {iv:5s} → {icon} {ir['signal']:4s} ({ir['confidence']:.0%})\n"
            )

        # Get trace from highest confidence interval
        best_interval = max(interval_results.items(), key=lambda x: x[1]["confidence"])[
            0
        ]
        explain_html = TraceRenderer.format_trace_html(
            interval_results.get(best_interval, {}).get("trace", [])
        )

        # Get history and stats
        history_html = HistoryRenderer.format_history_html(
            services["history"].get_recent_runs(limit=20)
        )
        stats = services["history"].get_statistics()
        stats_html = StatsRenderer.format_stats_html(stats)

        # Create summary card
        summary_html = f"""
        <div style="background:linear-gradient(135deg, #e3f2fd, #f3e5f5);border:2px solid #4c84af;border-radius:12px;padding:20px;">
            <h3 style="margin-top:0;color:#1a4a7a;">📊 Multi-Interval Weighted Voting</h3>
            {voting_summary}
        </div>
        """

        success_badge = StatusRenderer.success_badge(
            f"Analysis complete - {voting_result['final_signal']} signal"
        )

        return (
            market_txt,
            f"Trace from {best_interval} interval ({len(interval_results.get(best_interval, {}).get('trace', []))} steps)",
            final_decision_txt,
            explain_html,
            history_html,
            stats_html,
            summary_html,
            success_badge,
        )

    except Exception as e:
        sys_logger.error(f"Error in analysis: {e}")
        error_badge = StatusRenderer.error_badge(f"Unexpected error: {str(e)}")
        return ("", "", f"❌ {str(e)}", error_badge, "", "", "", error_badge)


@log_method(sys_logger)
def handle_refresh_history():
    """Handle 'Refresh' button in History tab"""
    try:
        history_html = HistoryRenderer.format_history_html(
            services["history"].get_recent_runs(limit=50)
        )
        stats = services["history"].get_statistics()
        stats_html = StatsRenderer.format_stats_html(stats)
        return history_html, stats_html
    except Exception as e:
        sys_logger.error(f"Error refreshing history: {e}")
        return StatusRenderer.error_badge(f"Failed to load history: {e}"), ""


@log_method(sys_logger)
def handle_load_run_detail(run_id_str: str):
    """Load detail for specific run from history"""
    try:
        run_id = int(run_id_str.lstrip("#"))
        detail = services["history"].get_run_detail(run_id)

        if detail["status"] == "error":
            return StatusRenderer.error_badge(detail["message"]), ""

        run = detail["data"]
        trace_html = TraceRenderer.format_trace_html(run.get("trace", []))
        fd_txt = f"""Signal: {run.get('signal', 'HOLD')}
        Confidence: {run.get('confidence', 0):.0%}
        Provider: {run.get('provider', '—')}
        Time: {run.get('run_at', '—')}"""

        return trace_html, fd_txt
    except Exception as e:
        return StatusRenderer.error_badge(f"Failed to load run: {e}"), ""


@log_method(sys_logger)
def handle_save_portfolio(cash, gold, cost, cur_val, pnl, trades):
    """Save portfolio to database"""
    try:
        result = services["portfolio"].save_portfolio(
            cash=cash,
            gold_grams=gold,
            cost_basis=cost,
            current_value=cur_val,
            pnl=pnl,
            trades_today=trades,
        )

        if result["status"] == "success":
            portfolio_html = PortfolioRenderer.format_portfolio_html(result["data"])
            status_msg = StatusRenderer.success_badge(result["message"])
            return status_msg, portfolio_html
        else:
            status_msg = StatusRenderer.error_badge(result["message"])
            return status_msg, ""

    except Exception as e:
        status_msg = StatusRenderer.error_badge(f"Save failed: {e}")
        return status_msg, ""


@log_method(sys_logger)
def handle_load_portfolio():
    """Load portfolio from database and fill form"""
    try:
        result = services["portfolio"].load_portfolio()
        pf = result["data"]

        portfolio_html = PortfolioRenderer.format_portfolio_html(pf)
        status_msg = StatusRenderer.success_badge("✅ Portfolio loaded")

        return (
            gr.update(value=float(pf.get("cash_balance", 0))),
            gr.update(value=float(pf.get("gold_grams", 0))),
            gr.update(value=float(pf.get("cost_basis_thb", 0))),
            gr.update(value=float(pf.get("current_value_thb", 0))),
            gr.update(value=float(pf.get("unrealized_pnl", 0))),
            gr.update(value=float(pf.get("trades_today", 0))),
            status_msg,
            portfolio_html,
        )

    except Exception as e:
        status_msg = StatusRenderer.error_badge(f"Load failed: {e}")
        return (
            gr.update(value=0),  # pf_cash
            gr.update(value=0),  # pf_gold
            gr.update(value=0),  # pf_cost
            gr.update(value=0),  # pf_curval
            gr.update(value=0),  # pf_pnl
            gr.update(value=0),  # pf_trade
            status_msg,  # pf_status
            "",  # pf_display
        )


def handle_auto_run(
    enabled: bool, provider: str, period: str, interval: str, interval_minutes: str
):
    """Handle auto-run timer tick"""
    if not enabled:
        return [gr.update()] * 8 + [StatusRenderer.info_badge("⏸️  Auto-run disabled")]

    result = handle_run_analysis(provider, period, interval)
    interval_sec = AUTO_RUN_INTERVALS.get(interval_minutes, 900)

    return list(result[:-1]) + [
        StatusRenderer.success_badge(f"✅ Running every {interval_minutes} min")
    ]


def handle_timer_toggle(enabled: bool):
    """Toggle auto-run timer display"""
    return (
        StatusRenderer.success_badge("✅ Auto-run enabled")
        if enabled
        else StatusRenderer.info_badge("⏸️  Auto-run disabled")
    )

@log_method(sys_logger)
def handle_fetch_chart(interval: str = "1h"):
    """
    Fetch gold price จาก goldapi.io + render chart/card/table
    ใช้ใน: fetch_btn.click, chart_timer.tick, demo.load
 
    Returns: (chart_html, price_card_html, provider_table_html, status_html)
    """
    try:
        # 1. TradingView chart widget (ไม่ต้อง API — embed script)
        chart_html = ChartTabRenderer.tradingview_widget(interval=interval)
 
        # 2. Fetch gold price จาก goldapi.io
        price_data = chart_service.fetch_price(currency="THB")
        price_html = ChartTabRenderer.gold_price_card(price_data)
 
        # 3. Provider table
        providers  = chart_service.get_providers_info()
        table_html = ChartTabRenderer.provider_table(providers)
 
        # 4. Status badge
        if price_data.get("status") == "success":
            p    = price_data["price"]
            pct  = price_data["change_pct"]
            icon = "▲" if pct >= 0 else "▼"
            status_html = StatusRenderer.success_badge(
                f"XAU/THB: ฿{p:,.0f} {icon} {abs(pct):.2f}% · {price_data['fetched_at']}"
            )
        else:
            status_html = StatusRenderer.error_badge(
                price_data.get("error", "Fetch failed")
            )
 
        return chart_html, price_html, table_html, status_html
 
    except Exception as e:
        sys_logger.error(f"handle_fetch_chart error: {e}")
        err = StatusRenderer.error_badge(f"Error: {e}")
        return "", "", "", err
    

# ─────────────────────────────────────────────
# Gradio UI Definition
# ─────────────────────────────────────────────

from core.dashboard_css import DASHBOARD_CSS

with gr.Blocks(title=UI_CONFIG["title"],
               theme=gr.themes.Soft(),
               css=DASHBOARD_CSS) as demo:
    gr.Markdown(
        "# 🟡 AI Gold Trading Agent Dashboard\n"
        "**ReAct LLM loop with weighted voting — real-time gold analysis**"
    )
 
    # ↓ One call — builds all tabs + wires all events
    NavbarBuilder.build_all(demo, ctx)


# ─────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🟡 GoldTrader Dashboard v3.2 (Refactored)")
    print(f"   Services: ✅ AnalysisService | ✅ PortfolioService | ✅ HistoryService")
    print(f"   Config: ✅ core/config.py")
    print(f"   Renderers: ✅ core/renderers.py")
    print(f"   Utils: ✅ core/utils.py")
    print("=" * 70)
    port = UI_CONFIG["port"]
    demo.launch(server_name="0.0.0.0", server_port=port, show_error=True)