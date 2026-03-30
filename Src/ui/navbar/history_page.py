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
            pc.register("stats_html",   gr.HTML(elem_id="stats-bar"))
            pc.register("refresh_btn",  gr.Button("🔄 Refresh", scale=0))

        pc.register("history_html", gr.HTML())

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
            inputs=[],
            outputs=[pc.history_html, pc.stats_html],
        )

        pc.load_btn.click(
            fn=self._handle_detail(ctx),
            inputs=[pc.run_id_input],
            outputs=[pc.detail_trace, pc.detail_fd],
        )

        demo.load(
            fn=self._handle_refresh(ctx),
            outputs=[pc.history_html, pc.stats_html],
        )

    # ── Handlers ───────────────────────────────────────────────────

    def _handle_refresh(self, ctx: AppContext):
        services = ctx.services

        @log_method(sys_logger)
        def _refresh():
            try:
                history_html = HistoryRenderer.format_history_html(
                    services["history"].get_recent_runs(limit=50)
                )
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
                    f"Signal:     {run.get('signal', 'HOLD')}\n"
                    f"Confidence: {run.get('confidence', 0):.0%}\n"
                    f"Provider:   {run.get('provider', '—')}\n"
                    f"Time:       {run.get('run_at', '—')}"
                )
                return trace_html, fd_txt

            except Exception as exc:
                return StatusRenderer.error_badge(f"Failed to load run: {exc}"), ""

        return _detail