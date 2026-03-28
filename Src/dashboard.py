"""
dashboard.py — Goldtrader Dashboard v3
Adds: Portfolio Tab — กรอก portfolio → รวมกับ market_state → ส่งให้ LLM
"""

import os
import json
import traceback
from datetime import datetime, timedelta, timezone
import gradio as gr
from dotenv import load_dotenv
from logger_setup import sys_logger, log_method

try:
    from data_engine.fetcher import GoldDataFetcher
    from data_engine.indicators import TechnicalIndicators
    from agent_core.llm.client import LLMClientFactory
    from agent_core.core.react import ReactOrchestrator, ReactConfig
    from agent_core.core.prompt import (
        PromptBuilder,
        RoleRegistry,
        SkillRegistry,
        AIRole,
    )
    from database import RunDatabase
except ImportError as e:
    print(f"⚠️  Import error: {e}")
    raise

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

# ─────────────────────────────────────────────
# Trace formatter helpers
# ─────────────────────────────────────────────


def _signal_icon(signal: str) -> str:
    return {"BUY": "🟢", "SELL": "🔴"}.get(signal, "🟡")


def format_trace_html(react_trace: list) -> str:
    if not react_trace:
        return "<p style='color:#888'>No trace data available.</p>"

    parts = []
    for entry in react_trace:
        step = entry.get("step", "?")
        iteration = entry.get("iteration", "?")
        response = entry.get("response", {})
        note = entry.get("note", "")

        if "FINAL" in step:
            hdr_color, bg_color, border = "#1a7a4a", "#f0faf4", "#4caf7d"
        elif step == "TOOL_EXECUTION":
            hdr_color, bg_color, border = "#7a5c1a", "#fdfaf0", "#c9a84c"
        else:
            hdr_color, bg_color, border = "#1a4a7a", "#f0f6fa", "#4c84af"

        action = response.get("action", entry.get("tool_name", ""))
        thought = response.get("thought", "")

        card = f"""
        <div style="margin:10px 0;border-left:4px solid {border};border-radius:8px;
                    background:{bg_color};padding:12px 16px;font-family:monospace;font-size:13px;">
            <div style="color:{hdr_color};font-weight:bold;font-size:12px;
                        text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
                {step} · iteration {iteration}{"&nbsp;— " + note if note else ""}
            </div>
        """
        if action:
            card += f"<div style='margin-bottom:4px'><b>Action:</b> <code>{action}</code></div>"
        if thought:
            card += f"<div style='margin-bottom:4px'><b>Thought:</b> {thought}</div>"
        if response.get("signal"):
            sig = response["signal"]
            conf = response.get("confidence", 0)
            card += f"""
            <div style="margin-top:8px;padding:8px;background:rgba(0,0,0,0.04);border-radius:6px;">
                <span style="font-weight:bold">{_signal_icon(sig)} {sig}</span>
                &nbsp;· confidence: <b>{conf:.0%}</b>
                {f" · entry: ฿{response.get('entry_price')}" if response.get('entry_price') else ""}
            </div>"""
        if "observation" in entry:
            obs = entry["observation"]
            status = obs.get("status", "?")
            status_color = "#1a7a4a" if status == "success" else "#b22222"
            card += f"""
            <div style="margin-top:6px">
                <b>Observation:</b>
                <span style="color:{status_color};font-weight:bold">[{status}]</span>
                {str(obs.get("data") or obs.get("error", ""))[:300]}
            </div>"""
        card += "</div>"
        parts.append(card)

    return "\n".join(parts)


def format_history_html(rows: list[dict]) -> str:
    if not rows:
        return "<p style='color:#888;padding:16px'>No runs recorded yet.</p>"

    header = """
    <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:monospace">
    <thead>
    <tr style="background:#f4f4f4;border-bottom:2px solid #ddd">
        <th style="padding:8px;text-align:left">ID</th>
        <th style="padding:8px;text-align:left">Time (TH)</th>
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
        sig = r.get("signal", "HOLD")
        icon = _signal_icon(sig)
        conf = r.get("confidence")
        conf_str = f"{conf:.0%}" if conf is not None else "—"
        price_str = f"${r['gold_price']:.0f}" if r.get("gold_price") else "—"
        rsi_str = f"{r['rsi']:.1f}" if r.get("rsi") else "—"
        raw_ts = r.get("run_at")
        if raw_ts:
            dt_utc = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            ts = (dt_utc + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts = ""
        provider_str = r.get("provider", "")
        if provider_str == "gemini":
            provider_str = "gemini-2.5-flash"

        rows_html.append(
            f"""
        <tr style="border-bottom:1px solid #eee">
            <td style="padding:6px 8px;color:#666">#{r['id']}</td>
            <td style="padding:6px 8px">{ts}</td>
            <td style="padding:6px 8px">{provider_str}</td>
            <td style="padding:6px 8px">{r.get('interval_tf','')}</td>
            <td style="padding:6px 8px;text-align:center">{icon} {sig}</td>
            <td style="padding:6px 8px;text-align:right">{conf_str}</td>
            <td style="padding:6px 8px;text-align:right">{price_str}</td>
            <td style="padding:6px 8px;text-align:right">{rsi_str}</td>
            <td style="padding:6px 8px;text-align:right">{r.get('iterations_used','')}</td>
        </tr>"""
        )

    return header + "".join(rows_html) + "</tbody></table>"


def format_stats_html(stats: dict) -> str:
    total = stats["total"]
    if total == 0:
        return "<span style='color:#888'>No data yet</span>"
    buy_pct = stats["buy_count"] / total * 100
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
# [เพิ่มใหม่] Portfolio helpers
# ─────────────────────────────────────────────


def format_portfolio_html(p: dict) -> str:
    """แสดงสรุป portfolio เป็น HTML card"""
    if not p:
        return "<p style='color:#888'>No portfolio data.</p>"

    cash = p.get("cash_balance", 0.0)
    gold_g = p.get("gold_grams", 0.0)
    cost = p.get("cost_basis_thb", 0.0)
    cur_val = p.get("current_value_thb", 0.0)
    pnl = p.get("unrealized_pnl", 0.0)
    trades = p.get("trades_today", 0)
    updated = p.get("updated_at", "")

    pnl_color = "#1a7a4a" if pnl >= 0 else "#b22222"
    pnl_prefix = "+" if pnl >= 0 else ""
    can_buy = cash >= 1000
    can_sell = gold_g > 0

    # แปลง UTC → TH time สำหรับ updated_at
    ts_th = ""
    if updated:
        try:
            dt_utc = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            ts_th = (dt_utc + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            ts_th = updated

    return f"""
    <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:10px;
                padding:16px;font-family:monospace;font-size:13px;">
        <div style="font-weight:bold;font-size:14px;margin-bottom:10px;color:#333">
            💼 Portfolio Summary
            <span style="font-size:11px;color:#888;font-weight:normal;margin-left:8px">
                updated {ts_th} (TH)
            </span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div style="background:white;border-radius:6px;padding:10px;border:1px solid #e0e0e0">
                <div style="color:#888;font-size:11px">💵 Cash Balance</div>
                <div style="font-size:18px;font-weight:bold;color:#1a4a7a">฿{cash:,.2f}</div>
            </div>
            <div style="background:white;border-radius:6px;padding:10px;border:1px solid #e0e0e0">
                <div style="color:#888;font-size:11px">🥇 Gold (grams)</div>
                <div style="font-size:18px;font-weight:bold;color:#7a5c1a">{gold_g:.4f} g</div>
            </div>
            <div style="background:white;border-radius:6px;padding:10px;border:1px solid #e0e0e0">
                <div style="color:#888;font-size:11px">📥 Cost Basis</div>
                <div style="font-size:15px;font-weight:bold">฿{cost:,.2f}</div>
            </div>
            <div style="background:white;border-radius:6px;padding:10px;border:1px solid #e0e0e0">
                <div style="color:#888;font-size:11px">📊 Current Value</div>
                <div style="font-size:15px;font-weight:bold">฿{cur_val:,.2f}</div>
            </div>
        </div>
        <div style="margin-top:8px;background:white;border-radius:6px;padding:10px;border:1px solid #e0e0e0">
            <span style="color:#888;font-size:11px">📈 Unrealized PnL: </span>
            <span style="font-weight:bold;color:{pnl_color}">{pnl_prefix}฿{pnl:,.2f}</span>
            &nbsp;&nbsp;
            <span style="color:#888;font-size:11px">🔄 Trades today: </span>
            <span style="font-weight:bold">{trades}</span>
        </div>
        <div style="margin-top:8px;display:flex;gap:8px;">
            <span style="padding:4px 10px;border-radius:12px;font-size:12px;font-weight:bold;
                         background:{'#e6f9ee' if can_buy else '#ffeaea'};
                         color:{'#1a7a4a' if can_buy else '#b22222'}">
                {'✅ can_buy' if can_buy else '❌ cannot buy (cash < ฿1,000)'}
            </span>
            <span style="padding:4px 10px;border-radius:12px;font-size:12px;font-weight:bold;
                         background:{'#e6f9ee' if can_sell else '#ffeaea'};
                         color:{'#1a7a4a' if can_sell else '#b22222'}">
                {'✅ can_sell' if can_sell else '❌ cannot sell (no gold)'}
            </span>
        </div>
    </div>
    """


def save_portfolio_fn(
    cash: float,
    gold_g: float,
    cost: float,
    cur_val: float,
    pnl: float,
    trades: int,
) -> tuple[str, str]:
    """บันทึก portfolio ลง DB แล้ว return (status_msg, portfolio_html)"""
    data = {
        "cash_balance": cash,
        "gold_grams": gold_g,
        "cost_basis_thb": cost,
        "current_value_thb": cur_val,
        "unrealized_pnl": pnl,
        "trades_today": int(trades),
    }
    try:
        db.save_portfolio(data)
        p = db.get_portfolio()
        return "✅ Portfolio saved!", format_portfolio_html(p)
    except Exception as e:
        return f"❌ Save failed: {e}", ""


def load_portfolio_to_form() -> tuple:
    """โหลด portfolio จาก DB มาใส่ form fields"""
    p = db.get_portfolio()
    return (
        p.get("cash_balance", 1500.0),
        p.get("gold_grams", 0.0),
        p.get("cost_basis_thb", 0.0),
        p.get("current_value_thb", 0.0),
        p.get("unrealized_pnl", 0.0),
        p.get("trades_today", 0),
        format_portfolio_html(p),
    )


# ─────────────────────────────────────────────
# Core pipeline
# ─────────────────────────────────────────────


@log_method(sys_logger)
def run_strategy_cycle(
    provider: str, period: str, interval: str
) -> tuple[str, str, str, str, str, str]:
    market_state = {}
    result = {}

    sys_logger.info(
        f"⚙️ Config: Provider={provider} | Period={period} | Interval={interval}"
    )

    try:
        # ── Step 1: Fetch ──────────────────────────────────────────────
        sys_logger.info("Step 1/5: Fetching Market Data...")

        raw = fetcher.fetch_all(include_news=False, history_days=90, interval=interval)
        ohlcv_df = raw.get("ohlcv_df")
        spot_data = raw.get("spot_price", {})
        forex_data = raw.get("forex", {})
        thai_gold = raw.get("thai_gold", {})

        if ohlcv_df is None or ohlcv_df.empty:
            err = "❌ No OHLCV data returned."
            return err, "", "", "", "", ""

        # ── Step 2: Indicators ─────────────────────────────────────────
        sys_logger.info("Step 2/5: Calculating Technical Indicators...")

        indicators = TechnicalIndicators(ohlcv_df)
        indicators_dict = indicators.to_dict()

        spot = spot_data.get("price_usd_per_oz", "N/A")
        rsi = indicators_dict.get("rsi", {}).get("value", "N/A")
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
                "forex": forex_data,
                "thai_gold_thb": thai_gold,
            },
            "technical_indicators": indicators_dict,
            "news": {"summary": {}, "by_category": {}},
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
            llm_client=llm_client,
            prompt_builder=prompt_builder,
            tool_registry={},
            config=ReactConfig(max_iterations=5, max_tool_calls=0),
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
        sys_logger.info("✅ Database save completed.")
    except Exception as e:
        sys_logger.error(f"[DB] Save failed: {e}", exc_info=True)

    # ── Step 5: Format outputs ─────────────────────────────────────────
    sys_logger.info("Step 5/5: Formatting UI Outputs...")

    fd = result.get("final_decision", {})
    trace_list = result.get("react_trace", [])

    simple_trace_lines = []
    for entry in trace_list:
        step = entry.get("step", "?")
        iteration = entry.get("iteration", "?")
        response = entry.get("response", {})
        simple_trace_lines.append(f"\n── {step} (Iteration {iteration}) ──")
        if response:
            simple_trace_lines.append(f"Action: {response.get('action','?')}")
            thought = response.get("thought", "")
            if thought:
                simple_trace_lines.append(f"Thought: {thought[:300]}")
    trace_text = "\n".join(simple_trace_lines) or "No trace."

    signal = fd.get("signal", "HOLD")
    confidence = fd.get("confidence", 0.0)
    entry_price = fd.get("entry_price")
    stop_loss = fd.get("stop_loss")
    take_profit = fd.get("take_profit")
    rationale = fd.get("rationale", "")

    entry_str = f"฿{entry_price:.2f}" if entry_price else "N/A"
    sl_str = f"฿{stop_loss:.2f}" if stop_loss else "N/A"
    tp_str = f"฿{take_profit:.2f}" if take_profit else "N/A"

    # [เพิ่มใหม่] แสดง portfolio snapshot ใน verdict ด้วย
    pf = market_state.get("portfolio", {})
    pf_line = (
        f"\n\n💼 Portfolio at analysis time:\n"
        f"   Cash: ฿{pf.get('cash_balance',0):,.2f} | "
        f"Gold: {pf.get('gold_grams',0):.4f}g | "
        f"Trades today: {pf.get('trades_today',0)}"
    )

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
        f"{pf_line}"
    )

    explain_html = format_trace_html(trace_list)
    history_html = format_history_html(db.get_recent_runs(50))
    stats_html = format_stats_html(db.get_signal_stats())

    return market_text, trace_text, verdict_text, explain_html, history_html, stats_html


def load_run_detail(run_id_str: str) -> tuple[str, str]:
    try:
        run_id = int(run_id_str.strip().lstrip("#"))
    except ValueError:
        return "<p style='color:red'>Invalid run ID</p>", ""

    detail = db.get_run_detail(run_id)
    if not detail:
        return f"<p style='color:red'>Run #{run_id} not found</p>", ""

    trace_html = format_trace_html(detail.get("react_trace") or [])
    provider_str = detail.get("provider", "")
    if provider_str == "gemini":
        provider_str = "gemini-2.5-flash"

    raw_ts = detail.get("run_at", "")
    ts_th = ""
    if raw_ts:
        dt_utc = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        ts_th = (dt_utc + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")

    fd_text = f"Run #{detail['id']} · {ts_th} (TH) · {provider_str}\n\n"
    return trace_html, fd_text


def refresh_history() -> tuple[str, str]:
    return format_history_html(db.get_recent_runs(50)), format_stats_html(
        db.get_signal_stats()
    )


# ─────────────────────────────────────────────
# Auto-run helpers
# ─────────────────────────────────────────────


def _status_badge(active: bool, last_run: str = "") -> str:
    if active:
        last = f" · last run {last_run}" if last_run else ""
        return (
            "<div style='display:inline-flex;align-items:center;gap:8px;"
            "background:#e6f9ee;border:1.5px solid #34c759;"
            "border-radius:20px;padding:4px 14px;font-size:13px;"
            "font-family:monospace;color:#1a7a3c;'>"
            "<span style='width:9px;height:9px;border-radius:50%;"
            "background:#34c759;display:inline-block;"
            "box-shadow:0 0 0 2px #b6f0cc;animation:pulse 1.5s infinite'></span>"
            f"AUTO-RUN ON · ทุก 30 นาที{last}"
            "</div>"
            "<style>@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}</style>"
        )
    return (
        "<div style='display:inline-flex;align-items:center;gap:8px;"
        "background:#f4f4f4;border:1.5px solid #bbb;"
        "border-radius:20px;padding:4px 14px;font-size:13px;"
        "font-family:monospace;color:#888;'>"
        "<span style='width:9px;height:9px;border-radius:50%;"
        "background:#bbb;display:inline-block'></span>"
        "AUTO-RUN OFF"
        "</div>"
    )


def run_multi_interval(provider: str, period: str, intervals: list[str]) -> tuple:
    if not intervals:
        return ("⚠️ กรุณาเลือกอย่างน้อย 1 Interval",) + ("",) * 5 + ("",)

    summary_rows = []
    last_results = None

    for iv in intervals:
        try:
            results = run_strategy_cycle(provider, period, iv)
            verdict = results[2]
            signal, conf, entry = "?", "", ""
            for line in verdict.splitlines():
                if "DECISION" in line:
                    signal = line.split(":")[-1].strip()
                elif "Confidence" in line:
                    conf = line.split(":")[-1].strip()
                elif "Entry Price" in line:
                    entry = line.split(":")[-1].strip()
            summary_rows.append(
                {
                    "interval": iv,
                    "signal": signal,
                    "conf": conf,
                    "entry": entry,
                    "ok": True,
                }
            )
            last_results = results
        except Exception as e:
            summary_rows.append(
                {
                    "interval": iv,
                    "signal": "ERROR",
                    "conf": "",
                    "entry": str(e)[:60],
                    "ok": False,
                }
            )

    rows_html = []
    for r in summary_rows:
        sig = (
            r["signal"]
            .replace("BUY", "🟢 BUY")
            .replace("SELL", "🔴 SELL")
            .replace("HOLD", "🟡 HOLD")
        )
        bg = "#f0faf4" if r["ok"] else "#fff0f0"
        rows_html.append(
            f"""
        <tr style="background:{bg};border-bottom:1px solid #e0e0e0">
            <td style="padding:8px 12px;font-weight:bold;font-family:monospace">{r['interval']}</td>
            <td style="padding:8px 12px;font-weight:bold">{sig}</td>
            <td style="padding:8px 12px;text-align:right">{r['conf']}</td>
            <td style="padding:8px 12px;text-align:right;font-family:monospace">{r['entry']}</td>
        </tr>"""
        )

    now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%H:%M:%S")
    multi_html = f"""
    <div style="margin-top:8px">
        <div style="font-size:12px;color:#888;margin-bottom:6px;font-family:monospace">
            🕐 Multi-interval scan · {now} · provider: {provider}
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr style="background:#f4f4f4;border-bottom:2px solid #ddd">
            <th style="padding:8px 12px;text-align:left">Interval</th>
            <th style="padding:8px 12px;text-align:left">Signal</th>
            <th style="padding:8px 12px;text-align:right">Confidence</th>
            <th style="padding:8px 12px;text-align:right">Entry Price</th>
        </tr></thead>
        <tbody>{"".join(rows_html)}</tbody>
        </table>
    </div>"""

    if last_results:
        return last_results + (multi_html,)
    return ("", "", "", "", "", "", multi_html)


def auto_run_cycle(auto_enabled: bool, provider: str, period: str, intervals):
    if not auto_enabled:
        return [gr.update()] * 7 + [_status_badge(False)]
    results = list(run_multi_interval(provider, period, intervals or []))
    now = datetime.now().strftime("%H:%M:%S")
    ivs = ", ".join(intervals) if intervals else "-"
    return results + [_status_badge(True, f"{now} [{ivs}]")]


def toggle_timer(enabled: bool):
    return _status_badge(enabled)


# ─────────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────────

PROVIDER_CHOICES = [
    ("gemini-2.5-flash", "gemini"),
    ("llama-3.3-70b-versatile", "groq"),
    ("mock", "mock"),
]
PERIOD_CHOICES = ["1d", "5d", "7d", "1mo"]
INTERVAL_CHOICES = ["15m", "30m", "1h", "4h", "1d"]

CSS = """
.tab-nav button { font-size: 14px !important; }
.trace-card { font-family: monospace; }
#stats-bar { padding: 8px 12px; background: #f8f8f8; border-radius: 8px; }
"""

with gr.Blocks(
    title="🟡 AI Gold Trading Agent", theme=gr.themes.Soft(), css=CSS
) as demo:
    gr.Markdown(
        "# 🟡 AI Gold Trading Agent Dashboard\n**ReAct LLM loop — real-time gold analysis**"
    )

    # ── Controls ───────────────────────────────────────────────────────
    with gr.Row():
        provider_dd = gr.Dropdown(
            PROVIDER_CHOICES, value="gemini", label="🤖 LLM Provider"
        )
        period_dd = gr.Dropdown(PERIOD_CHOICES, value="7d", label="📅 Data Period")
        run_btn = gr.Button("▶ Run Analysis", variant="primary", scale=1)
        auto_check = gr.Checkbox(label="⏰ Auto-run every 30 min", value=False, scale=0)

    interval_cbs = gr.CheckboxGroup(
        choices=["15m", "30m", "1h", "4h", "1d"],
        value=["1h"],
        label="⏱️ Candle Intervals (เลือกได้หลายตัว)",
    )

    auto_status = gr.HTML(value=_status_badge(False))
    timer = gr.Timer(value=900, active=True)

    # ── Tabs ───────────────────────────────────────────────────────────
    with gr.Tabs():

        # Tab 1 — Live Analysis
        with gr.TabItem("📊 Live Analysis"):
            gr.Markdown("### 📡 Multi-Interval Summary")
            multi_summary = gr.HTML()

            with gr.Row():
                market_box = gr.Textbox(
                    label="Market State", lines=9, interactive=False
                )
                trace_box = gr.Textbox(
                    label="🧠 ReAct Trace", lines=15, interactive=False
                )
                verdict_box = gr.Textbox(
                    label="🎯 Final Decision", lines=12, interactive=False
                )

            gr.Markdown("### 🔍 Explainability — Full ReAct Reasoning")
            explain_html = gr.HTML(label="Step-by-step AI reasoning")

        # Tab 2 — Run History
        with gr.TabItem("📜 Run History"):
            with gr.Row():
                stats_html = gr.HTML(elem_id="stats-bar")
                refresh_btn = gr.Button("🔄 Refresh", scale=0)

            history_html = gr.HTML()

            gr.Markdown("### 🔎 Load Run Detail")
            with gr.Row():
                run_id_input = gr.Textbox(
                    label="Run ID (e.g. #42)", placeholder="#42", scale=1
                )
                load_btn = gr.Button("Load", scale=0)

            with gr.Row():
                detail_trace = gr.HTML(label="Trace for selected run")
                detail_fd = gr.Textbox(
                    label="Decision summary", lines=8, interactive=False
                )

        # ── [เพิ่มใหม่] Tab 3 — Portfolio ─────────────────────────────
        with gr.TabItem("💼 Portfolio"):
            gr.Markdown(
                "### 💼 Portfolio ของฉัน\n"
                "กรอกข้อมูลจากแอพ **ออม NOW** แล้วกด **บันทึก** ก่อนกด Run Analysis\n\n"
                "> ⚠️ ต้องอัปเดตทุกครั้งที่ซื้อ/ขายทองเสร็จ เพื่อให้ LLM ได้ข้อมูลที่ถูกต้อง"
            )

            with gr.Row():
                pf_cash = gr.Number(
                    label="💵 Cash Balance (฿)", value=1500.0, precision=2
                )
                pf_gold = gr.Number(
                    label="🥇 ทองคำคงเหลือ (กรัม)", value=0.0, precision=4
                )
                pf_trade = gr.Number(
                    label="🔄 Trades Today (จำนวนไม้วันนี้)", value=0, precision=0
                )

            with gr.Row():
                pf_cost = gr.Number(label="📥 มูลค่าต้นทุน (฿)", value=0.0, precision=2)
                pf_curval = gr.Number(label="📊 มูลค่าปัจจุบัน (฿)", value=0.0, precision=2)
                pf_pnl = gr.Number(label="📈 กำไร/ขาดทุน (฿)", value=0.0, precision=2)

            with gr.Row():
                pf_save_btn = gr.Button("💾 บันทึก Portfolio", variant="primary")
                pf_reload_btn = gr.Button("🔄 โหลดข้อมูลจาก DB")

            pf_status = gr.Textbox(label="Status", lines=1, interactive=False)
            pf_display = gr.HTML(label="Portfolio Summary")

    # ── Wire events ────────────────────────────────────────────────────
    run_outputs = [
        market_box,
        trace_box,
        verdict_box,
        explain_html,
        history_html,
        stats_html,
        multi_summary,
    ]

    run_btn.click(
        fn=run_multi_interval,
        inputs=[provider_dd, period_dd, interval_cbs],
        outputs=run_outputs,
        api_name="analyze",
    )

    auto_check.change(fn=toggle_timer, inputs=[auto_check], outputs=[auto_status])

    timer.tick(
        fn=auto_run_cycle,
        inputs=[auto_check, provider_dd, period_dd, interval_cbs],
        outputs=run_outputs + [auto_status],
    )

    load_btn.click(
        fn=load_run_detail,
        inputs=[run_id_input],
        outputs=[detail_trace, detail_fd],
    )

    refresh_btn.click(fn=refresh_history, inputs=[], outputs=[history_html, stats_html])

    # ── [เพิ่มใหม่] Portfolio events ───────────────────────────────────
    pf_save_btn.click(
        fn=save_portfolio_fn,
        inputs=[pf_cash, pf_gold, pf_cost, pf_curval, pf_pnl, pf_trade],
        outputs=[pf_status, pf_display],
    )

    pf_reload_btn.click(
        fn=load_portfolio_to_form,
        inputs=[],
        outputs=[pf_cash, pf_gold, pf_cost, pf_curval, pf_pnl, pf_trade, pf_display],
    )

    # Load on startup
    demo.load(fn=refresh_history, outputs=[history_html, stats_html])
    demo.load(
        fn=lambda: format_portfolio_html(db.get_portfolio()), outputs=[pf_display]
    )

# ─────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🟡 goldtrader Dashboard v3  (Portfolio + History + Explainability)")
    print("=" * 60)
    port = int(os.environ.get("PORT", 10000))
    demo.launch(server_name="0.0.0.0", server_port=port, show_error=True)