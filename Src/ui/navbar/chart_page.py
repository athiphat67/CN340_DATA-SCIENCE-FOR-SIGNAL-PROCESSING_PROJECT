"""
ui/navbar/chart_page.py
📈 Live Chart — navbar page
"""

import gradio as gr

from core import INTERVAL_CHOICES
from core.renderers import StatusRenderer
from core.chart_renderer import ChartTabRenderer
from core.chart_service import chart_service
from logger_setup import sys_logger, log_method

from .base import PageBase, PageComponents, AppContext, navbar_page


@navbar_page("📈 Live Chart")
class ChartPage(PageBase):
    """
    Embeds TradingView widget + live gold price card.
    Auto-refreshes every 60 seconds.
    """

    # ── Build ──────────────────────────────────────────────────────

    def build(self, ctx: AppContext) -> PageComponents:
        pc = PageComponents()

        # Controls
        with gr.Row():
            pc.register("interval_dd", gr.Dropdown(
                choices=INTERVAL_CHOICES, value="1h",
                label="⏱️ Candle Interval", scale=2,
            ))
            pc.register("fetch_btn", gr.Button(
                "🔄 Refresh Live Price", variant="primary", scale=1,
            ))

        pc.register("chart_status", gr.HTML(
            value=StatusRenderer.info_badge("กด Refresh หรือรอ auto-fetch (60s)")
        ))

        # Main layout: chart left | info right
        with gr.Row():
            with gr.Column(scale=3):
                pc.register("chart_widget", gr.HTML())

            with gr.Column(scale=1, min_width=340):
                pc.register("price_card",     gr.HTML())
                pc.register("provider_table", gr.HTML())

        return pc

    # ── Wire ───────────────────────────────────────────────────────

    def wire(self, demo: gr.Blocks, ctx: AppContext, pc: PageComponents) -> None:
        _outputs = [pc.chart_widget, pc.price_card, pc.provider_table, pc.chart_status]

        pc.fetch_btn.click(fn=self._fetch, inputs=[pc.interval_dd], outputs=_outputs)
        pc.interval_dd.change(fn=self._fetch, inputs=[pc.interval_dd], outputs=_outputs)

        chart_timer = gr.Timer(value=60, active=True)
        chart_timer.tick(fn=self._fetch, inputs=[pc.interval_dd], outputs=_outputs)

        # Load on startup
        demo.load(
            fn=lambda: self._fetch("1h"),
            inputs=[],
            outputs=_outputs,
        )

    # ── Handler ────────────────────────────────────────────────────

    @log_method(sys_logger)
    def _fetch(self, interval: str = "1h"):
        try:
            chart_html = ChartTabRenderer.tradingview_widget(interval=interval)
            price_data = chart_service.fetch_price(currency="THB")
            price_html = ChartTabRenderer.gold_price_card(price_data)
            providers  = chart_service.get_providers_info()
            table_html = ChartTabRenderer.provider_table(providers)

            if price_data.get("status") == "success":
                p   = price_data["price"]
                pct = price_data["change_pct"]
                icon = "▲" if pct >= 0 else "▼"
                status_html = StatusRenderer.success_badge(
                    f"XAU/THB: ฿{p:,.0f} {icon} {abs(pct):.2f}% · {price_data['fetched_at']}"
                )
            else:
                status_html = StatusRenderer.error_badge(
                    price_data.get("error", "Fetch failed")
                )

            return chart_html, price_html, table_html, status_html

        except Exception as exc:
            sys_logger.error(f"ChartPage error: {exc}")
            err = StatusRenderer.error_badge(f"Error: {exc}")
            return "", "", "", err