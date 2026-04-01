"""
ui/navbar/analysis_page.py
📊 Live Analysis — navbar page

v2: เพิ่ม LLM Call Logs section — แสดง prompt/response/token stats
    จาก react_trace ของ run ปัจจุบัน
"""

import gradio as gr

from ui.core.renderers import TraceRenderer, HistoryRenderer, StatsRenderer, StatusRenderer
from ui.core.utils import format_voting_summary, format_error_message
from ui.core import (
    PROVIDER_CHOICES,  # <--- อันเดิม 
    PERIOD_CHOICES, 
    INTERVAL_CHOICES, 
    AUTO_RUN_INTERVALS, 
    DEFAULT_AUTO_RUN
)
from ui.core.config import get_all_llm_choices
from logs.logger_setup import sys_logger, log_method

from .base import PageBase, PageComponents, AppContext, navbar_page


# ─────────────────────────────────────────────────────────────────
# LLM Log renderer (inline — ไม่ depend on DB, render จาก trace โดยตรง)
# ─────────────────────────────────────────────────────────────────

def _render_llm_logs_from_trace(trace: list) -> str:
    """
    Render LLM call logs จาก react_trace list เป็น HTML dark-terminal style

    แต่ละ step ที่มี prompt_text / response_raw จะแสดง:
      - step label + iteration badge
      - signal / confidence (ถ้ามี)
      - token stats (input / output / total) + model
      - full prompt (collapsible)
      - full response raw (collapsible)
    """
    if not trace:
        return "<div style='color:#888;padding:16px'>ยังไม่มี LLM log — กด ▶ Run Analysis ก่อน</div>"

    # กรองเฉพาะ step ที่มี LLM call (มี prompt_text หรือ response_raw)
    llm_steps = [
        s for s in trace
        if s.get("step", "").startswith("THOUGHT") or s.get("prompt_text")
    ]

    if not llm_steps:
        return "<div style='color:#888;padding:16px'>ไม่พบ LLM call ใน trace</div>"

    # Signal colour mapping
    SIG_COLOR = {"BUY": "#4caf50", "SELL": "#f44336", "HOLD": "#ff9800"}

    rows_html = ""
    for idx, step in enumerate(llm_steps):
        step_label   = step.get("step", f"STEP_{idx}")
        iteration    = step.get("iteration", "—")
        response     = step.get("response", {})
        prompt_text  = step.get("prompt_text",  "")
        response_raw = step.get("response_raw", "")
        token_in     = step.get("token_input",  0)
        token_out    = step.get("token_output", 0)
        token_total  = step.get("token_total",  0)
        model        = step.get("model", "—")
        provider     = step.get("provider", "—")
        note         = step.get("note", "")

        # Signal badge (ถ้ามี)
        sig    = response.get("signal", "")
        conf   = response.get("confidence", None)
        action = response.get("action", "")

        sig_badge = ""
        if sig:
            color = SIG_COLOR.get(sig, "#999")
            sig_badge = f"""
            <span style="background:{color};color:#fff;
                         border-radius:4px;padding:2px 8px;
                         font-weight:bold;font-size:0.85em;margin-left:8px">
                {sig}
            </span>"""
            if conf is not None:
                try:
                    sig_badge += f"""<span style="color:#aaa;font-size:0.82em;margin-left:6px">{float(conf):.0%}</span>"""
                except (TypeError, ValueError):
                    pass
        elif action:
            sig_badge = f"""
            <span style="background:#5c6bc0;color:#fff;
                         border-radius:4px;padding:2px 8px;
                         font-size:0.82em;margin-left:8px">
                {action}
            </span>"""

        # Step label colour
        label_color = (
            "#4caf50" if "FINAL" in step_label
            else "#42a5f5" if step_label.startswith("THOUGHT")
            else "#ff9800"
        )

        # Token stats bar
        token_html = ""
        if token_total > 0:
            token_html = f"""
            <div style="display:flex;gap:12px;align-items:center;
                        margin:8px 0;font-size:0.82em;color:#90caf9;">
                <span>📥 {token_in:,} in</span>
                <span>📤 {token_out:,} out</span>
                <span style="color:#fff;font-weight:bold">🔢 {token_total:,} total</span>
                <span style="color:#78909c">· {model} ({provider})</span>
            </div>"""
        else:
            token_html = f"""
            <div style="font-size:0.78em;color:#546e7a;margin:4px 0">
                · {model} ({provider}) · tokens N/A
            </div>"""

        # Note badge
        note_html = ""
        if note:
            note_html = f"""
            <div style="color:#ffd54f;font-size:0.78em;margin-top:4px">⚠️ {note}</div>"""

        # Unique ID สำหรับ collapsible
        uid = f"llmlog_{idx}"

        # Prompt collapsible
        prompt_section = ""
        if prompt_text:
            safe_prompt = (prompt_text
                           .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            prompt_section = f"""
            <details style="margin-top:10px">
                <summary style="cursor:pointer;color:#80cbc4;
                                font-size:0.85em;user-select:none">
                    📋 Full Prompt ({len(prompt_text):,} chars)
                </summary>
                <pre style="background:#0d1117;border:1px solid #30363d;
                            border-radius:6px;padding:12px;margin-top:6px;
                            font-size:0.75em;color:#c9d1d9;
                            white-space:pre-wrap;word-break:break-all;
                            max-height:300px;overflow-y:auto">{safe_prompt}</pre>
            </details>"""

        # Response collapsible
        response_section = ""
        if response_raw:
            safe_resp = (response_raw
                         .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            response_section = f"""
            <details style="margin-top:6px">
                <summary style="cursor:pointer;color:#ce93d8;
                                font-size:0.85em;user-select:none">
                    💬 Raw Response ({len(response_raw):,} chars)
                </summary>
                <pre style="background:#0d1117;border:1px solid #30363d;
                            border-radius:6px;padding:12px;margin-top:6px;
                            font-size:0.75em;color:#c9d1d9;
                            white-space:pre-wrap;word-break:break-all;
                            max-height:300px;overflow-y:auto">{safe_resp}</pre>
            </details>"""

        rows_html += f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                    padding:14px;margin-bottom:10px">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <span style="font-family:monospace;font-weight:bold;
                             color:{label_color};font-size:0.9em">
                    {step_label}
                </span>
                <span style="background:#21262d;color:#8b949e;
                             border-radius:12px;padding:1px 8px;font-size:0.78em">
                    iter {iteration}
                </span>
                {sig_badge}
            </div>
            {token_html}
            {note_html}
            {prompt_section}
            {response_section}
        </div>"""

    # Summary token totals
    total_in  = sum(s.get("token_input",  0) for s in llm_steps)
    total_out = sum(s.get("token_output", 0) for s in llm_steps)
    total_all = sum(s.get("token_total",  0) for s in llm_steps)
    providers_used = list(dict.fromkeys(
        s.get("provider", "") for s in llm_steps if s.get("provider")
    ))

    summary_html = f"""
    <div style="background:#1c2128;border:1px solid #30363d;border-radius:8px;
                padding:12px 16px;margin-bottom:14px;
                display:flex;gap:24px;align-items:center;flex-wrap:wrap">
        <span style="color:#fff;font-weight:bold">🧠 {len(llm_steps)} LLM calls</span>
        <span style="color:#90caf9">📥 {total_in:,} in</span>
        <span style="color:#90caf9">📤 {total_out:,} out</span>
        <span style="color:#fff;font-weight:bold">🔢 {total_all:,} total tokens</span>
        <span style="color:#78909c;font-size:0.85em">via {', '.join(providers_used) or '—'}</span>
    </div>"""

    return f"""
    <div style="font-family:'JetBrains Mono',Consolas,monospace;
                background:#0d1117;border-radius:12px;padding:16px">
        {summary_html}
        {rows_html}
    </div>"""


# ─────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────

@navbar_page("📊 Live Analysis")
class AnalysisPage(PageBase):
    """
    Renders the Live Analysis tab and wires all its events.
    Handles: Run Analysis button, Auto-run timer, controls row.
    """

    # ── Build ──────────────────────────────────────────────────────

    def build(self, ctx: AppContext) -> PageComponents:
        pc = PageComponents()

        gr.HTML("""
                <style>
                    .gradio-container .form {
                        background-image: none !important;
                        background-color: transparent !important;
                        border: none !important;
                        box-shadow: none !important;
                    }
                    .gradio-container .block.gradio-dropdown,
                    .gradio-container .block.gradio-textbox {
                        background-color: transparent !important;
                        border: none !important;
                    }
                    .gradio-container label {
                        background-color: transparent !important;
                    }
                </style>
                """)

        # ── Controls (Card Layout) ────────────────────────────────
        with gr.Row():
            with gr.Column(elem_classes="card shadow p-4 bg-white"):
                gr.Markdown("### 🤖 Model Settings")
                pc.register("provider_dd", gr.Dropdown(
                    get_all_llm_choices(), value="gemini",
                    label="LLM Provider",
                    elem_classes="custom-input"
                ))
                pc.register("period_dd", gr.Dropdown(
                    PERIOD_CHOICES, value="7d",
                    label="Data Period",
                    elem_classes="custom-input"
                ))

            with gr.Column(elem_classes="card shadow p-4 bg-white"):
                gr.Markdown("### ⚙️ Execution")
                pc.register("interval_dd", gr.Dropdown(
                    choices=INTERVAL_CHOICES, value="1h",
                    label="Candle Interval",
                    elem_classes="custom-input"
                ))
                pc.register("auto_interval_dd", gr.Dropdown(
                    list(AUTO_RUN_INTERVALS.keys()),
                    value=DEFAULT_AUTO_RUN,
                    label="Auto-run Every (minutes)",
                    elem_classes="custom-input"
                ))

            with gr.Column(elem_classes="card shadow p-4 bg-white"):
                gr.Markdown("### 🚀 Controls")
                pc.register("run_btn", gr.Button(
                    "▶ Run Analysis", variant="primary",
                ))
                pc.register("auto_check", gr.Checkbox(
                    label="⏰ Auto-run", value=False,
                ))
                pc.register("auto_status", gr.HTML(
                    value=StatusRenderer.info_badge("⏸️ Auto-run disabled")
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

        # ── LLM Call Logs (ใหม่) ──────────────────────────────────
        gr.Markdown("### 🪵 LLM Call Logs — Prompt · Response · Tokens")
        pc.register("llm_logs_html", gr.HTML(
            value="<div style='color:#888;padding:16px'>กด ▶ Run Analysis เพื่อดู LLM logs</div>"
        ))

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
            pc.llm_logs_html,     
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
            # เตรียม empty return tuple (9 outputs)
            _empty = ("", "", "", "", "", "", "", "", "")

            try:
                result = services["analysis"].run_analysis(provider, period, [interval])

                if result["status"] == "error":
                    error_msg = format_error_message(result)
                    badge = StatusRenderer.error_badge(
                        error_msg,
                        is_validation=(result.get("error_type") == "validation"),
                    )
                    return ("", "", error_msg, badge, "", "", "", badge, "")

                voting_result    = result["voting_result"]
                interval_results = result["data"]["interval_results"]

                market_txt     = str(result["data"]["market_state"])[:1000]
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
                best_trace = interval_results.get(best_iv, {}).get("trace", [])

                explain_html = TraceRenderer.format_trace_html(best_trace)

                # ── LLM Call Logs: render จาก trace โดยตรง ──────
                llm_logs_html = _render_llm_logs_from_trace(best_trace)

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
                    f"Trace from {best_iv} ({len(best_trace)} steps)",
                    decision_txt,
                    explain_html,
                    history_html,
                    stats_html,
                    summary_html,
                    badge,
                    llm_logs_html,     
                )

            except Exception as exc:
                sys_logger.error(f"AnalysisPage error: {exc}")
                badge = StatusRenderer.error_badge(f"Unexpected error: {exc}")
                return ("", "", f"❌ {exc}", badge, "", "", "", badge, "")

        return _run

    def _handle_auto_run(self, ctx: AppContext):
        _run = self._handle_run(ctx)

        def _auto(enabled, provider, period, interval, interval_minutes):
            if not enabled:
                empty9 = ("",) * 9
                return list(empty9) + [StatusRenderer.info_badge("⏸️  Auto-run disabled")]
            result = list(_run(provider, period, interval))
            # replace auto_status (index 7) with running badge
            result[7] = StatusRenderer.success_badge(f"✅ Running every {interval_minutes} min")
            return result

        return _auto

    @staticmethod
    def _handle_timer_toggle(enabled: bool):
        return (
            StatusRenderer.success_badge("✅ Auto-run enabled")
            if enabled
            else StatusRenderer.info_badge("⏸️  Auto-run disabled")
        )