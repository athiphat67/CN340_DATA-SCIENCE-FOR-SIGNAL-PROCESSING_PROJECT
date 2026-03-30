"""
ui/navbar/history_page.py
📜 Run History — navbar page
"""

import gradio as gr

from core.renderers import TraceRenderer, HistoryRenderer, StatsRenderer, StatusRenderer
from logger_setup import sys_logger, log_method

from .base import PageBase, PageComponents, AppContext, navbar_page


@navbar_page("📜 Run History")
class HistoryPage(PageBase):

    # ── Build ──────────────────────────────────────────────────────

    def build(self, ctx: AppContext) -> PageComponents:
        pc = PageComponents()

        with gr.Row():
            pc.register("stats_html", gr.HTML(elem_id="stats-bar"))

        with gr.Row():
            pc.register("search_box", gr.Textbox(
                placeholder="🔎 Search by signal / provider...",
                show_label=False,
                scale=2,
            ))
            pc.register("filter_signal", gr.Dropdown(
                choices=["ALL", "BUY", "SELL", "HOLD"],
                value="ALL",
                label="Signal",
                scale=1,
            ))
            pc.register("limit_dd", gr.Dropdown(
                choices=[10, 20, 50, 100],
                value=50,
                label="Limit",
                scale=1,
            ))
            pc.register("refresh_btn", gr.Button("🔄 Refresh", scale=0))

        pc.register("history_html", gr.HTML())

        with gr.Row():
            pc.register("export_btn", gr.Button("⬇️ Export CSV", scale=0))

        gr.Markdown("### 🔎 Load Run Detail")
        with gr.Row():
            pc.register("run_id_input", gr.Textbox(
                label="Run ID", placeholder="#42", scale=1,
            ))
            pc.register("load_btn", gr.Button("Load", scale=0))

        with gr.Row():
            pc.register("detail_trace", gr.HTML(label="Trace"))
            pc.register("detail_fd",    gr.Textbox(
                label="Decision", lines=8, interactive=False,
            ))

        return pc

    # ── Wire ───────────────────────────────────────────────────────

    def wire(self, demo: gr.Blocks, ctx: AppContext, pc: PageComponents) -> None:

        pc.refresh_btn.click(
            fn=self._handle_refresh(ctx),
            inputs=[pc.search_box, pc.filter_signal, pc.limit_dd],
            outputs=[pc.history_html, pc.stats_html],
        )

        pc.search_box.change(
            fn=self._handle_refresh(ctx),
            inputs=[pc.search_box, pc.filter_signal, pc.limit_dd],
            outputs=[pc.history_html, pc.stats_html],
        )

        pc.filter_signal.change(
            fn=self._handle_refresh(ctx),
            inputs=[pc.search_box, pc.filter_signal, pc.limit_dd],
            outputs=[pc.history_html, pc.stats_html],
        )

        pc.load_btn.click(
            fn=self._handle_detail(ctx),
            inputs=[pc.run_id_input],
            outputs=[pc.detail_trace, pc.detail_fd],
        )

        demo.load(
            fn=self._handle_refresh(ctx),
            inputs=[pc.search_box, pc.filter_signal, pc.limit_dd],
            outputs=[pc.history_html, pc.stats_html],
        )

        pc.export_btn.click(
            fn=lambda: ctx.services["history"].export_csv(),
            inputs=[],
            outputs=[],
        )

    # ── Handlers ───────────────────────────────────────────────────

    def _handle_refresh(self, ctx: AppContext):
        services = ctx.services

        @log_method(sys_logger)
        def _refresh(search: str, signal: str, limit: int):
            try:
                runs = services["history"].get_recent_runs(limit=limit)

                # filter
                if signal != "ALL":
                    runs = [r for r in runs if r.get("signal") == signal]

                if search:
                    s = search.lower()
                    runs = [
                        r for r in runs
                        if s in str(r.get("signal", "")).lower()
                        or s in str(r.get("provider", "")).lower()
                    ]

                history_html = HistoryRenderer.format_history_html(runs)
                stats      = services["history"].get_statistics()
                stats_html = StatsRenderer.format_stats_html(stats)
                return history_html, stats_html
            except Exception as exc:
                sys_logger.error(f"HistoryPage refresh error: {exc}")
                return StatusRenderer.error_badge(f"Failed to load history: {exc}"), ""

        return _refresh

    def _handle_detail(self, ctx: AppContext):
        services = ctx.services

        @log_method(sys_logger)
        def _detail(run_id_str: str):
            try:
                run_id = int(run_id_str.lstrip("#"))
                detail = services["history"].get_run_detail(run_id)

                if detail["status"] == "error":
                    return StatusRenderer.error_badge(detail["message"]), ""

                run        = detail["data"]
                trace_html = TraceRenderer.format_trace_html(run.get("trace", []))
                fd_txt = (
                    f"🆔 Run ID:        {run.get('id', '-')}\n"
                    f"📅 Time:          {run.get('run_at', '-')}\n"
                    f"🏢 Provider:      {run.get('provider', '-')}\n"
                    f"⏱ Interval:      {run.get('interval_tf', '-')}\n"
                    f"📊 Period:        {run.get('period', '-')}\n"
                    f"\n"
                    f"📈 Signal:        {run.get('signal', 'HOLD')}\n"
                    f"🎯 Confidence:    {run.get('confidence', 0):.2%}\n"
                    f"\n"
                    f"💰 Entry Price:   {run.get('entry_price', '-')}\n"
                    f"🛑 Stop Loss:     {run.get('stop_loss', '-')}\n"
                    f"🎯 Take Profit:   {run.get('take_profit', '-')}\n"
                    f"\n"
                    f"🥇 Gold Price:    {run.get('gold_price', '-')}\n"
                    f"📉 RSI:           {run.get('rsi', '-')}\n"
                    f"📊 MACD:          {run.get('macd_line', '-')}\n"
                    f"📊 Signal Line:   {run.get('signal_line', '-')}\n"
                    f"📊 Trend:         {run.get('trend', '-')}\n"
                    f"\n"
                    f"🔁 Iterations:    {run.get('iterations_used', '-')}\n"
                    f"🛠 Tool Calls:    {run.get('tool_calls_used', '-')}\n"
                    f"\n"
                    f"🧠 Rationale:\n{run.get('rationale', '-')}\n"
                )
                return trace_html, fd_txt

            except Exception as exc:
                return StatusRenderer.error_badge(f"Failed to load run: {exc}"), ""

        return _detail