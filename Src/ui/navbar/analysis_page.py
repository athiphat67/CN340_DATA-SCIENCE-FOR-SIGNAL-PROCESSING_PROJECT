"""
ui/navbar/analysis_page.py
📊 Live Analysis — navbar page

v2: เพิ่ม LLM Call Logs section — แสดง prompt/response/token stats
    จาก react_trace ของ run ปัจจุบัน

v3 (fixes):
    - [FIX #1] market_box → market_html (gr.HTML) — แสดง market state แบบ structured sections
               แทน str()[:1000] ที่ตัดข้อมูลกลางคัน
    - [FIX #2] trace_box ถูกลบออก — ข้อมูลจริงอยู่ใน explain_html อยู่แล้ว ไม่ต้องซ้ำ
    - [FIX #3] เพิ่ม gr.Tabs() รวม LLM Trace + System Log ใน panel เดียว
               ทั้ง 2 log file มี display surface ครบถ้วน
    - [FIX #4] history_html / stats_html ถูก visible=True แล้ว (เดิม visible=False ไม่เคยโชว์)
    - [FIX #5] run_outputs tuple อัพเดตให้ตรงกับ output components ที่เปลี่ยน
"""

import json
import os
from pathlib import Path

import gradio as gr

from ui.core.renderers import TraceRenderer, HistoryRenderer, StatsRenderer, StatusRenderer
from ui.core.utils import format_error_message
from ui.core import (
    PROVIDER_CHOICES,
    PERIOD_CHOICES,
    INTERVAL_CHOICES,
    AUTO_RUN_INTERVALS,
    DEFAULT_AUTO_RUN,
)
from ui.core.config import get_all_llm_choices
from logs.logger_setup import sys_logger, log_method

from .base import PageBase, PageComponents, AppContext, navbar_page


# ─────────────────────────────────────────────────────────────────
# Log file paths  (ปรับ path ให้ตรงกับ project ของคุณ)
# ─────────────────────────────────────────────────────────────────

_LOG_DIR       = Path("logs")
_SYSTEM_LOG    = _LOG_DIR / "system.log"
_LLM_TRACE_LOG = _LOG_DIR / "llm_trace.log"


def _read_log_lines(log_filename: str) -> tuple[list[str], Path | None, str | None]:
    """
    Read log lines from likely locations.
    Returns: (lines, resolved_path, error_message)
    """
    # รองรับการรันได้ทั้งจาก project root และจากโฟลเดอร์ Src
    # - cwd = <repo>/Src      -> logs/*.log
    # - cwd = <repo>          -> Src/logs/*.log
    candidates = [
        Path("logs") / log_filename,
        Path("logs") / "logs" / log_filename,
        Path("Src") / "logs" / log_filename,
        Path("Src") / "logs" / "logs" / log_filename,
        Path.cwd() / "logs" / log_filename,
        Path.cwd() / "logs" / "logs" / log_filename,
        Path.cwd() / "Src" / "logs" / log_filename,
        Path.cwd() / "Src" / "logs" / "logs" / log_filename,
    ]

    # remove duplicates but keep order
    seen = set()
    uniq_candidates = []
    for p in candidates:
        rp = str(p.resolve()) if p.exists() else str(p)
        if rp in seen:
            continue
        seen.add(rp)
        uniq_candidates.append(p)

    # exact filename ก่อน
    for path in uniq_candidates:
        if not path.exists():
            continue
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines(), path, None
        except OSError as exc:
            return [], path, f"อ่านไฟล์ไม่ได้: {exc}"

    # fallback: รองรับ rotated logs เช่น llm_trace.log.1 / system.log.1
    rotated_candidates: list[Path] = []
    for base in [
        Path("logs"),
        Path("logs") / "logs",
        Path("Src") / "logs",
        Path("Src") / "logs" / "logs",
        Path.cwd() / "logs",
        Path.cwd() / "logs" / "logs",
        Path.cwd() / "Src" / "logs",
        Path.cwd() / "Src" / "logs" / "logs",
    ]:
        if not base.exists() or not base.is_dir():
            continue
        for p in base.glob(f"{log_filename}*"):
            if p.is_file():
                rotated_candidates.append(p)

    if rotated_candidates:
        rotated_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        pick = rotated_candidates[0]
        try:
            return pick.read_text(encoding="utf-8", errors="replace").splitlines(), pick, None
        except OSError as exc:
            return [], pick, f"อ่านไฟล์ไม่ได้: {exc}"

    checked = "<br>".join(str(p) for p in uniq_candidates)
    return [], None, f"ไม่พบไฟล์ log ({log_filename})<br><small style='color:#546e7a'>checked:<br>{checked}</small>"


# ─────────────────────────────────────────────────────────────────
# [FIX #1]  Market State HTML renderer
# ─────────────────────────────────────────────────────────────────

def _render_market_state(state: dict) -> str:
    if not state:
        return "<div style='color:#5a6270;padding:12px'>No data — run analysis first</div>"

    md   = state.get("market_data", {})
    ti   = state.get("technical_indicators", {})
    port = state.get("portfolio", {})
    news = state.get("news", []) 

    spot      = md.get("spot_price_usd", {}).get("price_usd_per_oz", 0)
    usd_thb   = md.get("forex", {}).get("usd_thb", 0)
    thai      = md.get("thai_gold_thb", {})
    sell_thb  = thai.get("sell_price_thb") or thai.get("spot_price_thb", 0)
    buy_thb   = thai.get("buy_price_thb")  or thai.get("spot_price_thb", 0)

    rsi_val   = float(ti.get("rsi", {}).get("value", 50))
    macd      = ti.get("macd", {})
    macd_line = float(macd.get("macd_line", 0) or 0)
    sig_line  = float(macd.get("signal_line", 0) or 0)
    hist      = float(macd.get("histogram", 0) or 0)
    trend     = ti.get("trend", {})
    ema20     = float(trend.get("ema_20", 0) or 0)
    ema50     = float(trend.get("ema_50", 0) or 0)
    bb        = ti.get("bollinger", {})
    bb_upper  = float(bb.get("upper", 0) or 0)
    bb_lower  = float(bb.get("lower", 0) or 0)
    atr_val   = float(ti.get("atr", {}).get("value", 0) or 0)

    # ── Derived interpretations ────────────────────────────────
    rsi_pct = min(max(rsi_val, 0), 100)
    if rsi_val < 30:
        rsi_label, rsi_pill, rsi_explain = "Oversold", ("pill-blue", "Possible bounce"), "Price has fallen a lot — buyers may step in"
    elif rsi_val < 50:
        rsi_label, rsi_pill, rsi_explain = "Bearish neutral", ("pill-amber", "Below midpoint"), "Momentum leaning downward"
    elif rsi_val < 60:
        rsi_label, rsi_pill, rsi_explain = "Neutral", ("pill-green", "Balanced"), "No strong signal either way"
    elif rsi_val < 70:
        rsi_label, rsi_pill, rsi_explain = "Bullish", ("pill-amber", "Near overbought"), "Strong run — may pause soon"
    else:
        rsi_label, rsi_pill, rsi_explain = "Overbought", ("pill-red", "Overbought"), "Price rose fast — pullback likely"

    macd_bull  = macd_line > sig_line
    hist_color = "#27500A" if hist > 0 else "#791F1F"
    hist_bg    = "#EAF3DE" if hist > 0 else "#FCEBEB"
    hist_sign  = "+" if hist >= 0 else ""

    trend_up   = ema20 > ema50
    trend_pill = ("pill-green", "Uptrend") if trend_up else ("pill-red", "Downtrend")
    trend_explain = "Fast average above slow — recent gains accelerating" if trend_up else "Fast average below slow — recent losses accelerating"

    bb_range = bb_upper - bb_lower if bb_upper > bb_lower else 1
    price_in_band = min(max((ema20 - bb_lower) / bb_range * 100, 0), 100)
    atr_thb = round(atr_val * usd_thb) if usd_thb else 0

    cash          = port.get("cash_balance", 0) or 0
    gold_g        = port.get("gold_grams", 0) or 0
    cost_basis    = port.get("cost_basis", 0) or 0      
    current_value = port.get("current_value", 0) or 0   
    pnl           = port.get("unrealized_pnl", 0) or 0
    trades        = port.get("trades_today", 0) or 0
    
    pnl_color = "#27500A" if pnl >= 0 else "#791F1F"
    can_buy   = cash >= 1010

    pill_css = """
    .pill-green{background:#EAF3DE;color:#27500A}
    .pill-amber{background:#FAEEDA;color:#633806}
    .pill-red{background:#FCEBEB;color:#791F1F}
    .pill-blue{background:#E6F1FB;color:#0C447C}
    """

    def pill(cls, text):
        return f'<span style="display:inline-block;font-size:10px;font-weight:500;padding:2px 7px;border-radius:4px" class="{cls}">{text}</span>'

    def card(content):
        return f'<div style="background:#fff;border:0.5px solid #e0ddd5;border-radius:12px;padding:14px 16px">{content}</div>'

    def section_lbl(t):
        return f'<div style="font-size:10px;font-weight:500;color:#5a6270;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">{t}</div>'

    def insight(dot_color, text):
        return (f'<div style="display:flex;gap:8px;padding:6px 0;border-bottom:0.5px solid #ece9e0">'
                f'<div style="width:7px;height:7px;border-radius:50%;background:{dot_color};flex-shrink:0;margin-top:3px"></div>'
                f'<div style="font-size:12px;color:#2c2c2a">{text}</div></div>')

    rsi_gauge = f"""
    {card(f'''
    {section_lbl("RSI 14 — buying momentum")}
    <div style="display:flex;justify-content:space-between;margin-bottom:5px">
      <span style="font-size:12px;color:#5a6270">0</span>
      <span style="font-size:16px;font-weight:500;color:#171c1f">{rsi_val:.1f}</span>
      <span style="font-size:12px;color:#5a6270">100</span>
    </div>
    <div style="position:relative;height:14px;border-radius:7px;overflow:hidden">
      <div style="position:absolute;inset:0;display:flex">
        <div style="width:30%;background:#E6F1FB"></div>
        <div style="width:40%;background:#EAF3DE"></div>
        <div style="width:30%;background:#FCEBEB"></div>
      </div>
      <div style="position:absolute;top:2px;bottom:2px;width:4px;border-radius:2px;background:#2C2C2A;left:calc({rsi_pct:.1f}% - 2px)"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#5a6270;margin-top:3px">
      <span>Oversold</span><span>Neutral</span><span>Overbought</span>
    </div>
    <div style="margin-top:7px;display:flex;gap:6px;align-items:center">
      {pill(rsi_pill[0], rsi_pill[1])}
      <span style="font-size:11px;color:#5a6270">{rsi_explain}</span>
    </div>''')}"""

    macd_card = f"""
    {card(f'''
    {section_lbl("MACD — trend momentum")}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      {pill("pill-green" if macd_bull else "pill-red", "Bullish" if macd_bull else "Bearish")}
      <span style="font-size:11px;color:#5a6270">{"MACD above signal — buyers in control" if macd_bull else "MACD below signal — sellers in control"}</span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px">
      <div style="background:#f5f3ee;border-radius:7px;padding:7px;text-align:center">
        <div style="font-size:10px;color:#5a6270;margin-bottom:2px">MACD</div>
        <div style="font-size:14px;font-weight:500;color:{"#27500A" if macd_line > 0 else "#791F1F"}">{macd_line:.3f}</div>
      </div>
      <div style="background:#f5f3ee;border-radius:7px;padding:7px;text-align:center">
        <div style="font-size:10px;color:#5a6270;margin-bottom:2px">Signal</div>
        <div style="font-size:14px;font-weight:500;color:#2c2c2a">{sig_line:.3f}</div>
      </div>
      <div style="background:{hist_bg};border-radius:7px;padding:7px;text-align:center">
        <div style="font-size:10px;color:#5a6270;margin-bottom:2px">Histogram</div>
        <div style="font-size:14px;font-weight:500;color:{hist_color}">{hist_sign}{hist:.3f}</div>
      </div>
    </div>''')}"""

    trend_card = f"""
    {card(f'''
    {section_lbl("Trend — EMA 20 vs EMA 50")}
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <div style="flex:1;background:#FAEEDA;border-radius:7px;padding:8px;text-align:center">
        <div style="font-size:10px;color:#854F0B">EMA 50 (slow)</div>
        <div style="font-size:15px;font-weight:500;color:#633806">{ema50:,.2f}</div>
      </div>
      <div style="font-size:20px;color:{"#3B6D11" if trend_up else "#A32D2D"};font-weight:500">{"→" if trend_up else "←"}</div>
      <div style="flex:1;background:{"#EAF3DE" if trend_up else "#FCEBEB"};border-radius:7px;padding:8px;text-align:center">
        <div style="font-size:10px;color:{"#3B6D11" if trend_up else "#A32D2D"}">EMA 20 (fast)</div>
        <div style="font-size:15px;font-weight:500;color:{"#27500A" if trend_up else "#791F1F"}">{ema20:,.2f}</div>
      </div>
    </div>
    <div style="display:flex;gap:6px;align-items:center">
      {pill(trend_pill[0], trend_pill[1])}
      <span style="font-size:11px;color:#5a6270">{trend_explain}</span>
    </div>''')}"""

    bb_card = f"""
    {card(f'''
    {section_lbl("Bollinger bands — price range")}
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:7px">
      <div style="background:#E6F1FB;border-radius:7px;padding:7px;text-align:center">
        <div style="font-size:10px;color:#0C447C">Lower (support)</div>
        <div style="font-size:13px;font-weight:500;color:#0C447C">{bb_lower:,.2f}</div>
      </div>
      <div style="background:#f5f3ee;border-radius:7px;padding:7px;text-align:center">
        <div style="font-size:10px;color:#5a6270">Mid (EMA 20)</div>
        <div style="font-size:13px;font-weight:500;color:#2c2c2a">{ema20:,.2f}</div>
      </div>
      <div style="background:#FCEBEB;border-radius:7px;padding:7px;text-align:center">
        <div style="font-size:10px;color:#791F1F">Upper (resistance)</div>
        <div style="font-size:13px;font-weight:500;color:#791F1F">{bb_upper:,.2f}</div>
      </div>
    </div>
    <div style="position:relative;height:10px;border-radius:5px;overflow:hidden;margin-bottom:6px">
      <div style="position:absolute;inset:0;background:#f5f3ee"></div>
      <div style="position:absolute;top:2px;bottom:2px;width:4px;border-radius:2px;background:#2C2C2A;left:calc({price_in_band:.1f}% - 2px)"></div>
    </div>
    <div style="font-size:11px;color:#5a6270">
      Price near upper band — tends to revert toward mid. Typical daily swing: ฿{atr_thb:,}/gram (ATR {atr_val:.2f}).
    </div>''')}"""

    # Synced styling: muted grey (#5a6270) for secondary data, dark (#2c2c2a) for primary
    portfolio_card = f"""
    {card(f'''
    {section_lbl("Portfolio")}
    <table style="width:100%;font-size:12px;border-collapse:collapse">
      <tr><td style="padding:4px 0;color:#5a6270">Cash</td><td style="text-align:right;font-weight:500;color:#2c2c2a">฿{cash:,.2f}</td></tr>
      <tr><td style="padding:4px 0;color:#5a6270">Gold held</td><td style="text-align:right;color:#5a6270">{gold_g:.4f} g</td></tr>
      <tr><td style="padding:4px 0;color:#5a6270">Cost basis</td><td style="text-align:right;color:#5a6270">฿{cost_basis:,.2f}</td></tr>
      <tr><td style="padding:4px 0;color:#5a6270">Current value</td><td style="text-align:right;font-weight:500;color:#2c2c2a">฿{current_value:,.2f}</td></tr>
      <tr><td style="padding:4px 0;color:#5a6270">Unrealized PnL</td><td style="text-align:right;font-weight:500;color:{pnl_color}">฿{pnl:,.2f}</td></tr>
      <tr><td style="padding:4px 0;color:#5a6270">Trades today</td><td style="text-align:right;color:#2c2c2a">{trades}</td></tr>
    </table>
    <div style="background:#{"EAF3DE" if can_buy else "FCEBEB"};border-radius:7px;padding:7px;margin-top:8px;font-size:11px;color:#{"27500A" if can_buy else "791F1F"}">
      {"Can enter 1 buy position (min ฿1,010)" if can_buy else f"Cannot buy — need ฿{1010 - cash:.0f} more"}
    </div>''')}"""

    # Synced styling: properly matching the muted section labels and primary text colors
    if not news:
        news_html = "<div style='font-size:11px;color:#5a6270'>ไม่มีข่าว</div>"
    elif isinstance(news, str):
        news_html = f"<div style='font-size:12px;color:#2c2c2a'>{news}</div>"
    else:
        news_items = "".join([f"<div style='font-size:12px;color:#2c2c2a;margin-bottom:4px;line-height:1.4'>• {n}</div>" for n in news])
        news_html = f"<div style='max-height:120px;overflow-y:auto;padding-right:4px'>{news_items}</div>"

    news_card = f"""
    {card(f'''
    {section_lbl("News")}
    {news_html}''')}"""

    insights = ""
    if trend_up:
        insights += insight("#639922", "Trend is up — EMA 20 is above EMA 50, recent prices rising faster")
    else:
        insights += insight("#E24B4A", "Trend is down — EMA 20 below EMA 50, recent price declining")
    if macd_bull and hist > 0:
        insights += insight("#639922", f"MACD histogram +{hist:.3f} — buying pressure growing")
    elif not macd_bull:
        insights += insight("#E24B4A", "MACD bearish — selling pressure dominating")
    if rsi_val >= 70:
        insights += insight("#BA7517", f"RSI {rsi_val:.1f} — overbought, pullback risk is high")
    elif rsi_val >= 60:
        insights += insight("#BA7517", f"RSI {rsi_val:.1f} — strong but near overbought zone")
    elif rsi_val <= 30:
        insights += insight("#378ADD", f"RSI {rsi_val:.1f} — oversold, potential bounce entry")
    if price_in_band > 75:
        insights += insight("#BA7517", "Price near upper Bollinger Band — statistically likely to revert toward mid")

    reasoning_card = f"""
    {card(f'''
    {section_lbl("Why this signal?")}
    {insights}''')}"""

    return f"""
    <style>
      .pill-green{{background:#EAF3DE;color:#27500A}}
      .pill-amber{{background:#FAEEDA;color:#633806}}
      .pill-red{{background:#FCEBEB;color:#791F1F}}
      .pill-blue{{background:#E6F1FB;color:#0C447C}}
    </style>
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:4px 0">

      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:14px">
        <div style="background:#fff;border:0.5px solid #e0ddd5;border-radius:12px;padding:14px 16px;border-top:3px solid #888780">
          <div style="font-size:10px;font-weight:500;color:#5a6270;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">Signal</div>
          <div style="font-size:22px;font-weight:500;color:#888780">HOLD</div>
          <div style="font-size:11px;color:#5a6270;margin-top:2px">Confidence 50%</div>
        </div>
        <div style="background:#fff;border:0.5px solid #e0ddd5;border-radius:12px;padding:14px 16px">
          <div style="font-size:10px;font-weight:500;color:#5a6270;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">Gold sell price</div>
          <div style="font-size:22px;font-weight:500;color:#2c2c2a">฿{sell_thb:,}</div>
          <div style="font-size:11px;color:#5a6270;margin-top:2px">Buy ฿{buy_thb:,} · spread ฿{sell_thb - buy_thb:,}</div>
        </div>
        <div style="background:#fff;border:0.5px solid #e0ddd5;border-radius:12px;padding:14px 16px">
          <div style="font-size:10px;font-weight:500;color:#5a6270;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">Gold in USD</div>
          <div style="font-size:22px;font-weight:500;color:#2c2c2a">${spot:,.0f}</div>
          <div style="font-size:11px;color:#5a6270;margin-top:2px">USD/THB {usd_thb:.2f}</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:14px">
        <div style="display:flex;flex-direction:column;gap:12px">
          {rsi_gauge}
          {macd_card}
          {trend_card}
          {bb_card}
        </div>
        <div style="display:flex;flex-direction:column;gap:12px">
          {portfolio_card}
          {news_card}
          {reasoning_card}
        </div>
      </div>
    </div>"""

# ─────────────────────────────────────────────────────────────────
# LLM Trace log file renderer  [FIX #3 — log file panel]
# ─────────────────────────────────────────────────────────────────

def _render_llm_trace_log(n_lines: int = 300) -> str:
    """
    อ่าน llm_trace.log และแสดงเป็น HTML

    Format คาดหวัง: แต่ละบรรทัดเป็น JSON object ที่ logger เขียนไว้
    ถ้า parse ไม่ได้ก็แสดงเป็น plain text line
    """
    lines, path, err = _read_log_lines("llm_trace.log")
    if err:
        return f"<div style='color:#888;padding:12px;font-size:0.85em'>{err}</div>"

    lines = lines[-n_lines:]
    if not lines:
        return "<div style='color:#888;padding:12px;font-size:0.85em'>llm_trace.log ว่างเปล่า</div>"

    SIG_COLOR = {"BUY": "#1D9E75", "SELL": "#D85A30", "HOLD": "#BA7517"}
    rows = []

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue

        # ลอง parse JSON ก่อน
        try:
            obj      = json.loads(raw)
            ts       = obj.get("time") or obj.get("timestamp") or obj.get("ts") or ""
            step     = obj.get("step") or obj.get("label") or "—"
            signal   = (obj.get("signal") or obj.get("response", {}).get("signal") or "")
            tok_tot  = obj.get("token_total") or obj.get("tokens") or ""
            model    = obj.get("model") or ""
            note     = obj.get("note") or ""
            display  = f"{ts[:19] if ts else ''}  {step}"
            extra    = "  ".join(filter(None, [
                f'<span style="color:{SIG_COLOR.get(signal,"#888780")};font-weight:600">{signal}</span>' if signal else "",
                f'<span style="color:#78909c">{tok_tot:,} tok</span>' if isinstance(tok_tot, int) and tok_tot else "",
                f'<span style="color:#78909c">{model}</span>'          if model  else "",
                f'<span style="color:#ffd54f">⚠ {note}</span>'         if note   else "",
            ]))
            rows.append(
                f'<div style="padding:4px 8px;border-bottom:1px solid #21262d;'
                f'font-family:monospace;font-size:0.78em;color:#c9d1d9">'
                f'{display}{"  " + extra if extra else ""}</div>'
            )
        except (json.JSONDecodeError, AttributeError):
            # plain text fallback
            safe = raw.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            rows.append(
                f'<div style="padding:3px 8px;border-bottom:1px solid #21262d;'
                f'font-family:monospace;font-size:0.78em;color:#8b949e">{safe}</div>'
            )

    source_html = (
        f'<div style="font-size:0.72em;color:#546e7a;padding:6px 8px;border-bottom:1px solid #21262d">'
        f"source: {path}</div>"
        if path else ""
    )
    return (
        f'<div style="background:#0d1117;border-radius:8px;max-height:450px;overflow-y:auto">'
        f'{source_html}{"".join(rows)}</div>'
    )


# ─────────────────────────────────────────────────────────────────
# System log file renderer  [FIX #3 — log file panel]
# ─────────────────────────────────────────────────────────────────

def _render_system_log(n_lines: int = 250) -> str:
    """
    อ่าน system.log และแสดงเป็น HTML color-coded ตาม log level
    """
    lines, path, err = _read_log_lines("system.log")
    if err:
        return f"<div style='color:#888;padding:12px;font-size:0.85em'>{err}</div>"

    lines = lines[-n_lines:]
    if not lines:
        return "<div style='color:#888;padding:12px;font-size:0.85em'>system.log ว่างเปล่า</div>"

    LEVEL_COLOR = {
        "ERROR":    "#f44336",
        "CRITICAL": "#e91e63",
        "WARNING":  "#ff9800",
        "WARN":     "#ff9800",
        "INFO":     "#4caf50",
        "DEBUG":    "#546e7a",
    }

    rows = []
    for raw in lines:
        raw   = raw.strip()
        if not raw:
            continue
        level = next((k for k in LEVEL_COLOR if k in raw.upper()), "DEBUG")
        color = LEVEL_COLOR[level]
        safe  = raw.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        rows.append(
            f'<div style="padding:3px 8px;border-bottom:1px solid #21262d;'
            f'font-family:monospace;font-size:0.78em;color:{color}">{safe}</div>'
        )

    source_html = (
        f'<div style="font-size:0.72em;color:#546e7a;padding:6px 8px;border-bottom:1px solid #21262d">'
        f"source: {path}</div>"
        if path else ""
    )
    return (
        f'<div style="background:#0d1117;border-radius:8px;max-height:450px;overflow-y:auto">'
        f'{source_html}{"".join(rows)}</div>'
    )


# ─────────────────────────────────────────────────────────────────
# LLM Trace (in-memory from react_trace)  — unchanged logic, kept here
# ─────────────────────────────────────────────────────────────────

def _render_llm_logs_from_trace(trace: list) -> str:
    """Render LLM call logs from react_trace list — dark terminal style."""
    if not trace:
        return "<div style='color:#888;padding:16px'>ยังไม่มี LLM log — กด ▶ Run Analysis ก่อน</div>"

    llm_steps = [
        s for s in trace
        if s.get("step", "").startswith("THOUGHT") or s.get("prompt_text")
    ]
    if not llm_steps:
        return "<div style='color:#888;padding:16px'>ไม่พบ LLM call ใน trace</div>"

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
        model        = step.get("model",    "—")
        provider     = step.get("provider", "—")
        note         = step.get("note",     "")

        sig    = response.get("signal", "")
        conf   = response.get("confidence", None)
        action = response.get("action", "")

        sig_badge = ""
        if sig:
            color = SIG_COLOR.get(sig, "#999")
            sig_badge = f'<span style="background:{color};color:#fff;border-radius:4px;padding:2px 8px;font-weight:bold;font-size:0.85em;margin-left:8px">{sig}</span>'
            if conf is not None:
                try:
                    sig_badge += f'<span style="color:#aaa;font-size:0.82em;margin-left:6px">{float(conf):.0%}</span>'
                except (TypeError, ValueError):
                    pass
        elif action:
            sig_badge = f'<span style="background:#5c6bc0;color:#fff;border-radius:4px;padding:2px 8px;font-size:0.82em;margin-left:8px">{action}</span>'

        label_color = (
            "#4caf50" if "FINAL" in step_label
            else "#42a5f5" if step_label.startswith("THOUGHT")
            else "#ff9800"
        )

        if token_total > 0:
            token_html = (
                f'<div style="display:flex;gap:12px;align-items:center;margin:8px 0;font-size:0.82em;color:#90caf9">'
                f'<span>IN {token_in:,}</span>'
                f'<span>OUT {token_out:,}</span>'
                f'<span style="color:#fff;font-weight:bold">TOTAL {token_total:,}</span>'
                f'<span style="color:#78909c">· {model} ({provider})</span>'
                f'</div>'
            )
        else:
            token_html = f'<div style="font-size:0.78em;color:#546e7a;margin:4px 0">· {model} ({provider}) · tokens N/A</div>'

        note_html = f'<div style="color:#ffd54f;font-size:0.78em;margin-top:4px">⚠ {note}</div>' if note else ""

        prompt_section = ""
        if prompt_text:
            safe_p = prompt_text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            prompt_section = (
                f'<details style="margin-top:10px">'
                f'<summary style="cursor:pointer;color:#80cbc4;font-size:0.85em;user-select:none">Full Prompt ({len(prompt_text):,} chars)</summary>'
                f'<pre style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;margin-top:6px;'
                f'font-size:0.75em;color:#c9d1d9;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto">{safe_p}</pre>'
                f'</details>'
            )

        response_section = ""
        if response_raw:
            safe_r = response_raw.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            response_section = (
                f'<details style="margin-top:6px">'
                f'<summary style="cursor:pointer;color:#ce93d8;font-size:0.85em;user-select:none">Raw Response ({len(response_raw):,} chars)</summary>'
                f'<pre style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;margin-top:6px;'
                f'font-size:0.75em;color:#c9d1d9;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto">{safe_r}</pre>'
                f'</details>'
            )

        rows_html += (
            f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin-bottom:10px">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
            f'<span style="font-family:monospace;font-weight:bold;color:{label_color};font-size:0.9em">{step_label}</span>'
            f'<span style="background:#21262d;color:#8b949e;border-radius:12px;padding:1px 8px;font-size:0.78em">iter {iteration}</span>'
            f'{sig_badge}</div>'
            f'{token_html}{note_html}{prompt_section}{response_section}'
            f'</div>'
        )

    total_in  = sum(s.get("token_input",  0) for s in llm_steps)
    total_out = sum(s.get("token_output", 0) for s in llm_steps)
    total_all = sum(s.get("token_total",  0) for s in llm_steps)
    providers = list(dict.fromkeys(s.get("provider","") for s in llm_steps if s.get("provider")))

    summary_html = (
        f'<div style="background:#1c2128;border:1px solid #30363d;border-radius:8px;'
        f'padding:12px 16px;margin-bottom:14px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">'
        f'<span style="color:#fff;font-weight:bold">{len(llm_steps)} LLM calls</span>'
        f'<span style="color:#90caf9">IN {total_in:,}</span>'
        f'<span style="color:#90caf9">OUT {total_out:,}</span>'
        f'<span style="color:#fff;font-weight:bold">TOTAL {total_all:,} tokens</span>'
        f'<span style="color:#78909c;font-size:0.85em">via {", ".join(providers) or "—"}</span>'
        f'</div>'
    )

    return (
        f'<div style="font-family:\'JetBrains Mono\',Consolas,monospace;'
        f'background:#0d1117;border-radius:12px;padding:16px">'
        f'{summary_html}{rows_html}</div>'
    )


def _render_llm_logs_from_db(logs: list[dict]) -> str:
    """Render LLM logs from DB (llm_logs table)."""
    if not logs:
        return "<div style='color:#888;padding:16px'>ยังไม่มี LLM log ในฐานข้อมูลสำหรับ run นี้</div>"

    SIG_COLOR = {"BUY": "#4caf50", "SELL": "#f44336", "HOLD": "#ff9800"}
    rows_html = ""

    for idx, log in enumerate(logs):
        step_type   = log.get("step_type", f"STEP_{idx}")
        iteration   = log.get("iteration", "—")
        signal      = log.get("signal", "")
        confidence  = log.get("confidence")
        token_in    = log.get("token_input", 0) or 0
        token_out   = log.get("token_output", 0) or 0
        token_total = log.get("token_total", 0) or 0
        model       = log.get("model", "—") or "—"
        provider    = log.get("provider", "—") or "—"
        rationale   = log.get("rationale", "")
        full_prompt = log.get("full_prompt", "")
        full_resp   = log.get("full_response", "")
        elapsed_ms  = log.get("elapsed_ms")
        logged_at   = log.get("logged_at", "")
        is_fallback = bool(log.get("is_fallback", False))
        fallback_from = log.get("fallback_from", "")

        sig_badge = ""
        if signal:
            color = SIG_COLOR.get(signal, "#999")
            conf_str = ""
            if confidence is not None:
                try:
                    conf_str = f" {float(confidence):.0%}"
                except (TypeError, ValueError):
                    conf_str = ""
            sig_badge = (
                f'<span style="background:{color};color:#fff;border-radius:4px;'
                f'padding:2px 8px;font-weight:bold;font-size:0.85em;margin-left:8px">{signal}{conf_str}</span>'
            )

        fallback_html = ""
        if is_fallback:
            fallback_html = (
                f'<span style="background:#b71c1c;color:#fff;border-radius:4px;'
                f'padding:1px 6px;font-size:0.75em;margin-left:6px">⚠ fallback from {fallback_from or "unknown"}</span>'
            )

        token_html = (
            f'<div style="display:flex;gap:12px;align-items:center;margin:8px 0;'
            f'font-size:0.82em;color:#90caf9;flex-wrap:wrap">'
            f'<span>IN {token_in:,}</span>'
            f'<span>OUT {token_out:,}</span>'
            f'<span style="color:#fff;font-weight:bold">TOTAL {token_total:,}</span>'
            f'<span style="color:#78909c">· {model} ({provider})'
            f'{" · " + f"{elapsed_ms:,} ms" if elapsed_ms else ""}</span>'
            f'</div>'
        )

        rationale_html = ""
        if rationale:
            safe_rat = rationale.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            rationale_html = (
                f'<div style="color:#b0bec5;font-size:0.82em;margin:8px 0;'
                f'border-left:3px solid #42a5f5;padding-left:8px;white-space:pre-wrap">{safe_rat}</div>'
            )

        prompt_html = ""
        if full_prompt:
            safe_p = full_prompt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            prompt_html = (
                f'<details style="margin-top:8px"><summary style="cursor:pointer;color:#80cbc4;'
                f'font-size:0.85em">Full Prompt ({len(full_prompt):,} chars)</summary>'
                f'<pre style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;'
                f'margin-top:6px;font-size:0.75em;color:#c9d1d9;white-space:pre-wrap;word-break:break-all;'
                f'max-height:300px;overflow-y:auto">{safe_p}</pre></details>'
            )

        response_html = ""
        if full_resp:
            safe_r = full_resp.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            response_html = (
                f'<details style="margin-top:6px"><summary style="cursor:pointer;color:#ce93d8;'
                f'font-size:0.85em">Raw Response ({len(full_resp):,} chars)</summary>'
                f'<pre style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;'
                f'margin-top:6px;font-size:0.75em;color:#c9d1d9;white-space:pre-wrap;word-break:break-all;'
                f'max-height:300px;overflow-y:auto">{safe_r}</pre></details>'
            )

        rows_html += (
            f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin-bottom:10px">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
            f'<span style="font-family:monospace;font-weight:bold;color:#42a5f5;font-size:0.9em">{step_type}</span>'
            f'<span style="background:#21262d;color:#8b949e;border-radius:12px;padding:1px 8px;font-size:0.78em">iter {iteration}</span>'
            f'{sig_badge}{fallback_html}'
            f'<span style="color:#546e7a;font-size:0.75em;margin-left:auto">{logged_at}</span>'
            f'</div>{token_html}{rationale_html}{prompt_html}{response_html}</div>'
        )

    total_in = sum((r.get("token_input", 0) or 0) for r in logs)
    total_out = sum((r.get("token_output", 0) or 0) for r in logs)
    total_all = sum((r.get("token_total", 0) or 0) for r in logs)
    providers = list(dict.fromkeys(r.get("provider", "") for r in logs if r.get("provider")))

    return (
        f'<div style="font-family:\'JetBrains Mono\',Consolas,monospace;background:#0d1117;border-radius:12px;padding:16px">'
        f'<div style="background:#1c2128;border:1px solid #30363d;border-radius:8px;padding:12px 16px;'
        f'margin-bottom:14px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">'
        f'<span style="color:#fff;font-weight:bold">{len(logs)} LLM calls</span>'
        f'<span style="color:#90caf9">IN {total_in:,}</span>'
        f'<span style="color:#90caf9">OUT {total_out:,}</span>'
        f'<span style="color:#fff;font-weight:bold">TOTAL {total_all:,} tokens</span>'
        f'<span style="color:#78909c;font-size:0.85em">via {", ".join(providers) or "—"}</span>'
        f'</div>{rows_html}</div>'
    )


def _render_reasoning_from_db_logs(logs: list[dict]) -> str:
    """Fallback reasoning panel when trace is missing."""
    if not logs:
        return "<div style='color:#888;padding:12px'>No trace data available.</div>"

    rows = []
    for log in logs:
        step = log.get("step_type", "THOUGHT_FINAL")
        provider = log.get("provider", "—")
        rationale = (log.get("rationale") or "").strip()
        if not rationale:
            continue
        safe_rat = rationale.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rows.append(
            f"<li style='margin-bottom:8px'><b>{step}</b> <span style='color:#78909c'>({provider})</span><br>{safe_rat}</li>"
        )

    if not rows:
        return "<div style='color:#888;padding:12px'>No trace data available.</div>"

    return (
        "<div style='background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:12px'>"
        "<div style='color:#e6edf3;font-weight:600;margin-bottom:8px'>Reasoning (from DB)</div>"
        f"<ol style='color:#c9d1d9;padding-left:20px;margin:0'>{''.join(rows)}</ol>"
        "</div>"
    )


# ─────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────

@navbar_page("📊 Live Analysis")
class AnalysisPage(PageBase):
    """
    Renders the Live Analysis tab and wires all its events.

    Layout (top → bottom):
      1. Controls row          — model settings / execution / run button
      2. Result summary        — signal badge
      3. Three-column row      — market_html | verdict_box  (trace_box removed)
      4. Explainability        — step-by-step ReAct reasoning
      5. Log Tabs              — LLM Trace (live) | LLM Trace (file) | System Log
      6. History + Stats       — recent runs / cumulative stats
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

        # ── Controls ──────────────────────────────────────────────
        with gr.Row():
            with gr.Column(elem_classes="card shadow p-4 bg-white"):
                gr.Markdown("### Model Settings")
                pc.register("provider_dd", gr.Dropdown(
                    get_all_llm_choices(), value="gemini",
                    label="LLM Provider",
                    elem_classes="custom-input",
                ))
                pc.register("period_dd", gr.Dropdown(
                    PERIOD_CHOICES, value="7d",
                    label="Data Period",
                    elem_classes="custom-input",
                ))

            with gr.Column(elem_classes="card shadow p-4 bg-white"):
                gr.Markdown("### Execution")
                pc.register("interval_dd", gr.Dropdown(
                    choices=INTERVAL_CHOICES, value="1h",
                    label="Candle Interval",
                    elem_classes="custom-input",
                ))
                pc.register("auto_interval_dd", gr.Dropdown(
                    list(AUTO_RUN_INTERVALS.keys()),
                    value=DEFAULT_AUTO_RUN,
                    label="Auto-run Every (minutes)",
                    elem_classes="custom-input",
                ))

            with gr.Column(elem_classes="card shadow p-4 bg-white"):
                gr.Markdown("### Controls")
                pc.register("run_btn", gr.Button(
                    "▶ Run Analysis", variant="primary",
                ))
                pc.register("auto_check", gr.Checkbox(
                    label="Auto-run", value=False,
                ))
                pc.register("auto_status", gr.HTML(
                    value=StatusRenderer.info_badge("⏸ Auto-run disabled"),
                ))

        # ── Result summary ─────────────────────────────────────────
        gr.Markdown("### Analysis Result")
        pc.register("result_summary", gr.HTML())

        # ── [FIX #1 + FIX #2]  Market HTML  +  Verdict  ──────────
        # trace_box removed — it was showing only a one-line string while
        # the real trace is already rendered in explain_html below.
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("#### Market State")
                pc.register("market_html", gr.HTML(
                    value="<div style='color:#888;padding:12px'>กด ▶ Run Analysis เพื่อดูข้อมูลตลาด</div>",
                    label="Market State",
                ))
            with gr.Column(scale=1):
                pc.register("verdict_box", gr.Textbox(
                    label="Final Decision",
                    lines=12,
                    interactive=False,
                ))

        # ── Explainability ─────────────────────────────────────────
        gr.Markdown("### Step-by-Step Reasoning")
        pc.register("explain_html", gr.HTML(label="Step-by-step AI reasoning"))

        # ── [FIX #3]  Log Tabs — LLM Trace (live) + file + system ─
        #
        # gr.Tabs() คืออะไร?
        # ─────────────────
        # gr.Tabs() เป็น container component ของ Gradio ที่จัดกลุ่ม
        # เนื้อหาหลายชิ้นไว้ใต้แถบ tab เดียว ผู้ใช้คลิกเพื่อสลับระหว่าง
        # แต่ละ gr.Tab() โดยไม่ต้อง scroll
        #
        # โครงสร้าง:
        #   with gr.Tabs():
        #       with gr.Tab("ชื่อ Tab 1"):
        #           <components ของ tab 1>
        #       with gr.Tab("ชื่อ Tab 2"):
        #           <components ของ tab 2>
        #
        # ข้อดีในหน้านี้:
        #   - LLM Trace (live) แสดงผลจาก memory ของ run ล่าสุด
        #   - LLM Trace (file) อ่านจาก llm_trace.log (persistent ข้าม restart)
        #   - System Log อ่านจาก system.log — ไม่เคยมี surface มาก่อน
        # ─────────────────────────────────────────────────────────
        gr.Markdown("### Logs")
        with gr.Tabs():
            with gr.Tab("LLM Trace — live run"):
                pc.register("llm_logs_html", gr.HTML(
                    value="<div style='color:#888;padding:16px'>กด ▶ Run Analysis เพื่อดู LLM logs</div>",
                ))

            with gr.Tab("LLM Trace — log file"):
                with gr.Row():
                    refresh_llm_btn = gr.Button("↻ Refresh", size="sm", scale=0)
                pc.register("llm_trace_file_html", gr.HTML(
                    value=_render_llm_trace_log(),
                ))

            with gr.Tab("System Log"):
                with gr.Row():
                    refresh_sys_btn = gr.Button("↻ Refresh", size="sm", scale=0)
                pc.register("system_log_html", gr.HTML(
                    value=_render_system_log(),
                ))

        # ── [FIX #4]  History + Stats  (เดิม visible=False ไม่เคยโชว์) ─
        with gr.Tabs():
            with gr.Tab("Run History"):
                pc.register("history_html", gr.HTML(
                    value="<div style='color:#888;padding:12px'>ยังไม่มีประวัติ</div>",
                ))
            with gr.Tab("Statistics"):
                pc.register("stats_html", gr.HTML(
                    value="<div style='color:#888;padding:12px'>ยังไม่มีสถิติ</div>",
                ))

        # wire refresh buttons here (inside build so we have access to pc)
        refresh_llm_btn.click(
            fn=_render_llm_trace_log,
            inputs=[],
            outputs=[pc.llm_trace_file_html],
        )
        refresh_sys_btn.click(
            fn=_render_system_log,
            inputs=[],
            outputs=[pc.system_log_html],
        )

        return pc

    # ── Wire ───────────────────────────────────────────────────────

    def wire(self, demo: gr.Blocks, ctx: AppContext, pc: PageComponents) -> None:

        # [FIX #5] updated to match new component names:
        #   market_html replaces market_box
        #   trace_box removed
        run_outputs = [
            pc.market_html,       # was: market_box (Textbox → HTML)
            pc.verdict_box,
            pc.explain_html,
            pc.history_html,
            pc.stats_html,
            pc.result_summary,
            pc.auto_status,
            pc.llm_logs_html,
            pc.llm_trace_file_html,   # refresh file log on each run too
            pc.system_log_html,       # refresh system log on each run too
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
            # [FIX #5] 10 outputs now (market_html, verdict, explain,
            #          history, stats, summary, auto_status,
            #          llm_logs_html, llm_trace_file_html, system_log_html)
            _empty = ("",) * 10

            try:
                result = services["analysis"].run_analysis(provider, period, [interval])

                if result["status"] == "error":
                    error_msg = format_error_message(result)
                    badge = StatusRenderer.error_badge(
                        error_msg,
                        is_validation=(result.get("error_type") == "validation"),
                    )
                    # return 10-tuple on error
                    return ("", error_msg, badge, "", "", "", badge, "", _render_llm_trace_log(), _render_system_log())

                voting_result    = result["voting_result"]
                interval_results = result["data"]["interval_results"]

                # [FIX #1] structured HTML renderer replaces str()[:1000]
                market_html = _render_market_state(result["data"]["market_state"])

                signal     = voting_result["final_signal"]
                confidence = voting_result["weighted_confidence"]
                iv_name    = next(iter(interval_results))
                ir         = interval_results[iv_name]
                run_id     = result.get("run_id")
                icon       = {"BUY": "🟢", "SELL": "🔴"}.get(signal, "🟡")

                provider_used = ir.get("provider_used", provider)
                decision_txt = (
                    f"Interval:   {iv_name}\n"
                    f"Provider:   {provider_used}\n"
                    f"Signal:     {icon} {signal}\n"
                    f"Confidence: {confidence:.1%}\n"
                    f"Reasoning:  {ir.get('reasoning', ir.get('rationale', '—'))}\n"
                )
                if ir.get("entry_price"):
                    decision_txt += f"\nEntry:       ฿{ir['entry_price']:,.0f}"
                if ir.get("stop_loss"):
                    decision_txt += f"\nStop Loss:   ฿{ir['stop_loss']:,.0f}"
                if ir.get("take_profit"):
                    decision_txt += f"\nTake Profit: ฿{ir['take_profit']:,.0f}"

                best_trace     = ir.get("trace", [])
                explain_html   = TraceRenderer.format_trace_html(best_trace)
                llm_logs_html  = _render_llm_logs_from_trace(best_trace)

                # Prefer DB logs (llm_logs table) after run is persisted.
                if run_id and hasattr(services["history"], "get_llm_logs_for_run"):
                    db_logs = services["history"].get_llm_logs_for_run(run_id)
                    if db_logs:
                        llm_logs_html = _render_llm_logs_from_db(db_logs)
                        if not best_trace:
                            explain_html = _render_reasoning_from_db_logs(db_logs)

                history_html = HistoryRenderer.format_history_html(
                    services["history"].get_recent_runs(limit=20)
                )
                stats_html = StatsRenderer.format_stats_html(
                    services["history"].get_statistics()
                )

                signal_color = {"BUY": "#1D9E75", "SELL": "#D85A30"}.get(signal, "#888780")
                summary_html = f"""
                <div style="background:#f6fafe;border:2px solid {signal_color};
                            border-radius:12px;padding:20px;">
                    <h3 style="margin-top:0;color:#171c1f;">Analysis Result — {iv_name}</h3>
                    <span style="font-size:1.5em;font-weight:bold;color:{signal_color};">
                        {icon} {signal}
                    </span>
                    <span style="margin-left:12px;color:#424754;">
                        confidence {confidence:.1%}
                    </span>
                </div>"""

                badge = StatusRenderer.success_badge(
                    f"Analysis complete — {voting_result['final_signal']} signal"
                )

                return (
                    market_html,              # market_html  (was market_box str)
                    decision_txt,             # verdict_box
                    explain_html,             # explain_html
                    history_html,             # history_html (now visible)
                    stats_html,               # stats_html   (now visible)
                    summary_html,             # result_summary
                    badge,                    # auto_status
                    llm_logs_html,            # llm_logs_html (live trace)
                    _render_llm_trace_log(),  # llm_trace_file_html
                    _render_system_log(),     # system_log_html
                )

            except Exception as exc:
                sys_logger.error(f"AnalysisPage error: {exc}")
                badge = StatusRenderer.error_badge(f"Unexpected error: {exc}")
                return ("", f"❌ {exc}", badge, "", "", "", badge, "",
                        _render_llm_trace_log(), _render_system_log())

        return _run

    def _handle_auto_run(self, ctx: AppContext):
        _run = self._handle_run(ctx)

        def _auto(enabled, provider, period, interval, interval_minutes):
            if not enabled:
                empty10 = ("",) * 10
                return list(empty10) + [StatusRenderer.info_badge("⏸  Auto-run disabled")]
            result = list(_run(provider, period, interval))
            # index 6 = auto_status slot
            result[6] = StatusRenderer.success_badge(f"✅ Running every {interval_minutes} min")
            return result

        return _auto

    @staticmethod
    def _handle_timer_toggle(enabled: bool):
        return (
            StatusRenderer.success_badge("✅ Auto-run enabled")
            if enabled
            else StatusRenderer.info_badge("⏸  Auto-run disabled")
        )