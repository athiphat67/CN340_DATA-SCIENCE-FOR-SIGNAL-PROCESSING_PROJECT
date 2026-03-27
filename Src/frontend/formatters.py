# ui_components/formatters.py
from datetime import datetime, timedelta

def signal_icon(signal: str) -> str:
    return {"BUY": "🟢", "SELL": "🔴"}.get(signal, "🟡")

def format_trace_html(react_trace: list) -> str:
    if not react_trace:
        return "<p style='color:#888'>No trace data available.</p>"

    parts = []
    for entry in react_trace:
        step      = entry.get("step", "?")
        iteration = entry.get("iteration", "?")
        response  = entry.get("response", {})
        note      = entry.get("note", "")

        if "FINAL" in step:
            hdr_color, bg_color, border = "#1a7a4a", "#f0faf4", "#4caf7d"
        elif step == "TOOL_EXECUTION":
            hdr_color, bg_color, border = "#7a5c1a", "#fdfaf0", "#c9a84c"
        else:
            hdr_color, bg_color, border = "#1a4a7a", "#f0f6fa", "#4c84af"

        action  = response.get("action", entry.get("tool_name", ""))
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
            sig  = response["signal"]
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
        sig      = r.get("signal", "HOLD")
        icon     = signal_icon(sig)
        conf     = r.get("confidence")
        conf_str = f"{conf:.0%}" if conf is not None else "—"
        price_str = f"${r['gold_price']:.0f}" if r.get("gold_price") else "—"
        rsi_str   = f"{r['rsi']:.1f}" if r.get("rsi") else "—"
        raw_ts = r.get("run_at")
        if raw_ts:
            dt_utc = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            ts = (dt_utc + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts = ""
        provider_str = r.get("provider", "")
        if provider_str == "gemini":
            provider_str = "gemini-2.5-flash"

        rows_html.append(f"""
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
        </tr>""")

    return header + "".join(rows_html) + "</tbody></table>"


def format_stats_html(stats: dict) -> str:
    total = stats["total"]
    if total == 0:
        return "<span style='color:#888'>No data yet</span>"
    buy_pct  = stats["buy_count"]  / total * 100
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
