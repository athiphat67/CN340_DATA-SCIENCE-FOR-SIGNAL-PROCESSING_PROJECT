"""
ui/navbar/analysis_page.py
📊 Live Analysis — navbar page
"""

import gradio as gr

from core.renderers import TraceRenderer, HistoryRenderer, StatsRenderer, StatusRenderer
from core.utils import format_voting_summary, format_error_message
from core import PROVIDER_CHOICES, PERIOD_CHOICES, INTERVAL_CHOICES, AUTO_RUN_INTERVALS, DEFAULT_AUTO_RUN
from logger_setup import sys_logger, log_method

from .base import PageBase, PageComponents, AppContext, navbar_page


@navbar_page("📊 Live Analysis")
class AnalysisPage(PageBase):
    """
    Renders the Live Analysis tab and wires all its events.
    Handles: Run Analysis button, Auto-run timer, controls row.
    """

    # ── Build ──────────────────────────────────────────────────────

    def build(self, ctx: AppContext) -> PageComponents:
        pc = PageComponents()

        # ── Controls row (provider / period / run / auto) ──────────
        with gr.Row():
            pc.register("provider_dd", gr.Dropdown(
                PROVIDER_CHOICES, value="gemini",
                label="🤖 LLM Provider", scale=2,
            ))
            pc.register("period_dd", gr.Dropdown(
                PERIOD_CHOICES, value="7d",
                label="📅 Data Period", scale=1,
            ))
            pc.register("run_btn", gr.Button(
                "▶ Run Analysis", variant="primary", scale=1,
            ))
            pc.register("auto_check", gr.Checkbox(
                label="⏰ Auto-run", value=False, scale=0,
            ))

        # ── Interval + auto-run frequency ─────────────────────────
        pc.register("interval_dd", gr.Dropdown(
            choices=INTERVAL_CHOICES, value="1h",
            label="⏱️  Candle Interval",
        ))

        with gr.Row():
            pc.register("auto_interval_dd", gr.Dropdown(
                list(AUTO_RUN_INTERVALS.keys()),
                value=DEFAULT_AUTO_RUN,
                label="⏱️  Auto-run Every (minutes)",
                scale=2,
            ))

        pc.register("auto_status", gr.HTML(
            value=StatusRenderer.info_badge("⏸️  Auto-run disabled")
        ))

        # ── Results area ───────────────────────────────────────────
        gr.Markdown("### 📡 Analysis Result")
        pc.register("multi_summary", gr.HTML())

        with gr.Row():
            pc.register("market_box", gr.Textbox(
                label="Market State", lines=9, interactive=False,
            ))
            pc.register("trace_box", gr.Textbox(
                label="🧠 ReAct Trace", lines=15, interactive=False,
            ))
            pc.register("verdict_box", gr.Textbox(
                label="🎯 Final Decision", lines=12, interactive=False,
            ))

        gr.Markdown("### 🔍 Explainability — Step-by-Step Reasoning")
        pc.register("explain_html", gr.HTML(label="Step-by-step AI reasoning"))

        # History + stats output areas (updated after analysis)
        pc.register("history_html", gr.HTML(visible=False))
        pc.register("stats_html",   gr.HTML(visible=False))

        return pc

    # ── Wire ───────────────────────────────────────────────────────

    def wire(self, demo: gr.Blocks, ctx: AppContext, pc: PageComponents) -> None:

        run_outputs = [
            pc.market_box, pc.trace_box, pc.verdict_box,
            pc.explain_html, pc.history_html, pc.stats_html,
            pc.multi_summary, pc.auto_status,
        ]

        pc.run_btn.click(
            fn=self._handle_run(ctx),
            inputs=[pc.provider_dd, pc.period_dd, pc.interval_dd],
            outputs=run_outputs,
        )

        pc.auto_check.change(
            fn=self._handle_timer_toggle,
            inputs=[pc.auto_check],
            outputs=[pc.auto_status],
        )

        timer = gr.Timer(value=900, active=True)
        timer.tick(
            fn=self._handle_auto_run(ctx),
            inputs=[pc.auto_check, pc.provider_dd, pc.period_dd,
                    pc.interval_dd, pc.auto_interval_dd],
            outputs=run_outputs + [pc.auto_status],
        )

    # ── Private handlers ───────────────────────────────────────────

    def _handle_run(self, ctx: AppContext):
        """Return a closure that calls AnalysisService."""
        services = ctx.services

        @log_method(sys_logger)
        def _run(provider: str, period: str, interval: str):
            try:
                result = services["analysis"].run_analysis(provider, period, [interval])

                if result["status"] == "error":
                    error_msg = format_error_message(result)
                    badge = StatusRenderer.error_badge(
                        error_msg,
                        is_validation=(result.get("error_type") == "validation"),
                    )
                    return ("", "", error_msg, badge, "", "", "", badge)

                voting_result    = result["voting_result"]
                interval_results = result["data"]["interval_results"]

                market_txt    = str(result["data"]["market_state"])[:1000]
                voting_summary = format_voting_summary(voting_result)

                decision_txt = (
                    f"{voting_summary}\n\n"
                    f"Final Signal: {voting_result['final_signal']}\n"
                    f"Confidence:   {voting_result['weighted_confidence']:.1%}\n\n"
                    "Per-Interval Details:\n"
                )
                for iv, ir in interval_results.items():
                    icon = {"BUY": "🟢", "SELL": "🔴"}.get(ir["signal"], "🟡")
                    decision_txt += f"  {iv:5s} → {icon} {ir['signal']:4s} ({ir['confidence']:.0%})\n"

                best_iv = max(interval_results.items(), key=lambda x: x[1]["confidence"])[0]
                explain_html = TraceRenderer.format_trace_html(
                    interval_results.get(best_iv, {}).get("trace", [])
                )

                history_html = HistoryRenderer.format_history_html(
                    services["history"].get_recent_runs(limit=20)
                )
                stats      = services["history"].get_statistics()
                stats_html = StatsRenderer.format_stats_html(stats)

                summary_html = f"""
                <div style="background:linear-gradient(135deg,#e3f2fd,#f3e5f5);
                            border:2px solid #4c84af;border-radius:12px;padding:20px;">
                    <h3 style="margin-top:0;color:#1a4a7a;">📊 Multi-Interval Weighted Voting</h3>
                    {voting_summary}
                </div>"""

                badge = StatusRenderer.success_badge(
                    f"Analysis complete — {voting_result['final_signal']} signal"
                )

                return (
                    market_txt,
                    f"Trace from {best_iv} ({len(interval_results.get(best_iv,{}).get('trace',[]))} steps)",
                    decision_txt, explain_html,
                    history_html, stats_html,
                    summary_html, badge,
                )

            except Exception as exc:
                sys_logger.error(f"AnalysisPage error: {exc}")
                badge = StatusRenderer.error_badge(f"Unexpected error: {exc}")
                return ("", "", f"❌ {exc}", badge, "", "", "", badge)

        return _run

    def _handle_auto_run(self, ctx: AppContext):
        _run = self._handle_run(ctx)

        def _auto(enabled, provider, period, interval, interval_minutes):
            if not enabled:
                return [gr.update()] * 8 + [StatusRenderer.info_badge("⏸️  Auto-run disabled")]
            result = _run(provider, period, interval)
            return list(result[:-1]) + [
                StatusRenderer.success_badge(f"✅ Running every {interval_minutes} min")
            ]

        return _auto

    @staticmethod
    def _handle_timer_toggle(enabled: bool):
        return (
            StatusRenderer.success_badge("✅ Auto-run enabled")
            if enabled
            else StatusRenderer.info_badge("⏸️  Auto-run disabled")
        )