"""
renderers.py — HTML/UI Rendering components
Gold Trading Agent v3.2
"""
from datetime import datetime, timedelta
from typing import List, Dict

# ─────────────────────────────────────────────
# Signal Icons & Colors
# ─────────────────────────────────────────────

def _signal_icon(signal: str) -> str:
    """Return emoji icon for signal"""
    return {"BUY": "🟢", "SELL": "🔴"}.get(signal, "🟡")


def _signal_color(signal: str) -> tuple[str, str]:
    """Return (header_color, background_color) for signal"""
    colors = {
        "BUY": ("#1a7a4a", "#f0faf4", "#4caf7d"),   # green
        "SELL": ("#7a1a1a", "#faf0f0", "#af4c4c"), # red
        "HOLD": ("#7a4a1a", "#faf8f0", "#af854c"), # orange
    }
    default = ("#1a4a7a", "#f0f6fa", "#4c84af")  # blue
    return colors.get(signal, default)


# ─────────────────────────────────────────────
# Trace Renderer
# ─────────────────────────────────────────────

class TraceRenderer:
    """Render ReAct trace as HTML cards"""
    
    @staticmethod
    def format_trace_html(react_trace: list) -> str:
        """
        Format ReAct trace to interactive HTML
        Shows each step of the reasoning process
        """
        if not react_trace:
            return "<p style='color:#888'>No trace data available.</p>"
        
        parts = []
        for idx, entry in enumerate(react_trace, 1):
            step = entry.get("step", "?")
            iteration = entry.get("iteration", "?")
            response = entry.get("response", {})
            note = entry.get("note", "")
            
            # Color coding by step type
            if "FINAL" in step:
                hdr_color, bg_color, border = "#1a7a4a", "#f0faf4", "#4caf7d"
            elif step == "TOOL_EXECUTION":
                hdr_color, bg_color, border = "#7a5c1a", "#fdfaf0", "#c9a84c"
            elif "THOUGHT" in step:
                hdr_color, bg_color, border = "#1a4a7a", "#f0f6fa", "#4c84af"
            else:
                hdr_color, bg_color, border = "#5a5a5a", "#f5f5f5", "#888888"
            
            action = response.get("action", entry.get("tool_name", ""))
            thought = response.get("thought", "")
            
            card = f"""
            <div style="margin:12px 0;border-left:5px solid {border};border-radius:8px;
                        background:{bg_color};padding:14px 16px;font-family:monospace;font-size:13px;">
                <div style="color:{hdr_color};font-weight:bold;font-size:11px;
                            text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">
                    [{idx}] {step} · iteration {iteration}{' — ' + note if note else ''}
                </div>
            """
            
            if action:
                card += f"<div style='margin-bottom:6px;color:#333'><b>Action:</b> <code style='background:rgba(0,0,0,0.05);padding:2px 4px;border-radius:3px'>{action}</code></div>"
            
            if thought:
                card += f"<div style='margin-bottom:6px;color:#333;line-height:1.5'><b>Thought:</b> {thought}</div>"
            
            if response.get("signal"):
                sig = response["signal"]
                conf = response.get("confidence", 0)
                icon = _signal_icon(sig)
                entry_price = response.get("entry_price", "")
                entry_str = f" · entry: ฿{entry_price}" if entry_price else ""
                
                card += f"""
                <div style="margin-top:10px;padding:8px;background:rgba(0,0,0,0.08);border-radius:6px;border-left:3px solid {border};">
                    <span style="font-weight:bold;font-size:14px">{icon} {sig}</span>
                    &nbsp;· confidence: <b>{conf:.0%}</b>{entry_str}
                </div>"""
            
            if "observation" in entry:
                obs = entry["observation"]
                status = obs.get("status", "?")
                status_color = "#1a7a4a" if status == "success" else "#b22222"
                obs_data = str(obs.get("data") or obs.get("error", ""))[:200]
                
                card += f"""
                <div style="margin-top:8px;padding:6px;background:rgba(0,0,0,0.03);border-radius:4px">
                    <b style="font-size:11px">Observation:</b>
                    <span style="color:{status_color};font-weight:bold">[{status}]</span><br>
                    <code style="font-size:12px;color:#555">{obs_data}</code>
                </div>"""
            
            card += "</div>"
            parts.append(card)
        
        return "\n".join(parts)


# ─────────────────────────────────────────────
# History Renderer
# ─────────────────────────────────────────────

class HistoryRenderer:
    """Render run history as HTML table"""
    
    @staticmethod
    def format_history_html(rows: List[Dict]) -> str:
        """Format run history to sortable HTML table"""
        if not rows:
            return "<p style='color:#888;padding:16px'>📊 No runs recorded yet.</p>"
        
        header = """
        <div style="overflow-x:auto;border-radius:8px;border:1px solid #ddd;box-shadow:0 2px 4px rgba(0,0,0,0.05)">
        <table style="width:100%;border-collapse:collapse;font-size:12px;font-family:monospace">
        <thead>
        <tr style="background:linear-gradient(to right, #f8f9fa, #ffffff);border-bottom:2px solid #ddd;position:sticky;top:0">
            <th style="padding:10px 8px;text-align:left;font-weight:600;color:#333">ID</th>
            <th style="padding:10px 8px;text-align:left;font-weight:600;color:#333">Time (TH)</th>
            <th style="padding:10px 8px;text-align:left;font-weight:600;color:#333">Provider</th>
            <th style="padding:10px 8px;text-align:left;font-weight:600;color:#333">Intervals</th>
            <th style="padding:10px 8px;text-align:center;font-weight:600;color:#333">Signal</th>
            <th style="padding:10px 8px;text-align:right;font-weight:600;color:#333">Conf</th>
            <th style="padding:10px 8px;text-align:right;font-weight:600;color:#333">Price</th>
            <th style="padding:10px 8px;text-align:right;font-weight:600;color:#333">RSI</th>
            <th style="padding:10px 8px;text-align:right;font-weight:600;color:#333">Iter</th>
        </tr>
        </thead><tbody>
        """
        
        rows_html = []
        for idx, r in enumerate(rows):
            # Alternate row colors
            row_bg = "#fafafa" if idx % 2 == 0 else "white"
            
            sig = r.get("signal", "HOLD")
            icon = _signal_icon(sig)
            conf = r.get("confidence")
            conf_str = f"{conf:.0%}" if conf is not None else "—"
            price_str = f"฿{r['gold_price']:.0f}" if r.get("gold_price") else "—"
            rsi_str = f"{r['rsi']:.1f}" if r.get("rsi") else "—"
            
            # Format timestamp
            raw_ts = r.get("run_at")
            if raw_ts:
                try:
                    dt_utc = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                    ts = (dt_utc + timedelta(hours=7)).strftime("%m-%d %H:%M")
                except:
                    ts = raw_ts
            else:
                ts = "—"
            
            provider_str = r.get("provider", "")
            if provider_str == "gemini":
                provider_str = "gemini"
            elif provider_str == "groq":
                provider_str = "groq"
            elif provider_str == "anthropic":
                provider_str = "claude"
            
            intervals_str = r.get("interval_tf", "")
            
            rows_html.append(f"""
        <tr style="background:{row_bg};border-bottom:1px solid #e0e0e0;hover-effect">
            <td style="padding:8px;color:#666;border-right:1px solid #eee">#<b>{r.get('id', '?')}</b></td>
            <td style="padding:8px;border-right:1px solid #eee">{ts}</td>
            <td style="padding:8px;border-right:1px solid #eee;font-size:11px">{provider_str}</td>
            <td style="padding:8px;border-right:1px solid #eee;font-size:11px">{intervals_str}</td>
            <td style="padding:8px;text-align:center;border-right:1px solid #eee"><b>{icon} {sig}</b></td>
            <td style="padding:8px;text-align:right;border-right:1px solid #eee"><code>{conf_str}</code></td>
            <td style="padding:8px;text-align:right;border-right:1px solid #eee"><code>{price_str}</code></td>
            <td style="padding:8px;text-align:right;border-right:1px solid #eee"><code>{rsi_str}</code></td>
            <td style="padding:8px;text-align:right"><code>{r.get('iterations_used', '—')}</code></td>
        </tr>""")
        
        return header + "".join(rows_html) + """</tbody></table></div>"""


# ─────────────────────────────────────────────
# Portfolio Renderer
# ─────────────────────────────────────────────

class PortfolioRenderer:
    """Render portfolio as HTML summary cards"""
    
    @staticmethod
    def format_portfolio_html(p: dict) -> str:
        """Format portfolio to beautiful HTML cards"""
        if not p:
            return "<p style='color:#888'>📊 No portfolio data.</p>"
        
        cash = p.get("cash_balance", 0.0)
        gold_g = p.get("gold_grams", 0.0)
        cost = p.get("cost_basis_thb", 0.0)
        cur_val = p.get("current_value_thb", 0.0)
        pnl = p.get("unrealized_pnl", 0.0)
        trades = p.get("trades_today", 0)
        updated = p.get("updated_at", "")
        
        pnl_color = "#1a7a4a" if pnl >= 0 else "#b22222"
        pnl_icon = "📈" if pnl >= 0 else "📉"
        pnl_prefix = "+" if pnl >= 0 else ""
        
        can_buy = cash >= 1000
        can_sell = gold_g > 0
        
        # Format timestamp
        ts_th = ""
        if updated:
            try:
                dt_utc = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                ts_th = (dt_utc + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
            except:
                ts_th = updated
        
        # Calculate total and percentages
        total_value = cash + cur_val
        cash_pct = (cash / total_value * 100) if total_value > 0 else 0
        gold_pct = (cur_val / total_value * 100) if total_value > 0 else 0
        
        # Calculate ROI
        roi = ((cur_val - cost) / cost * 100) if cost > 0 else 0
        roi_color = "#1a7a4a" if roi >= 0 else "#b22222"
        roi_icon = "📈" if roi >= 0 else "📉"
        
        html = f"""
        <div style="border:2px solid #e0e0e0;border-radius:12px;padding:20px;background:linear-gradient(135deg, #fafafa, #f5f5f5);font-family:system-ui,-apple-system,sans-serif;font-size:14px;">
            
            <!-- Title -->
            <div style="margin-bottom:16px;border-bottom:2px solid #ddd;padding-bottom:12px;">
                <h3 style="margin:0;color:#2c3e50;font-size:18px;">💼 Portfolio Summary</h3>
                <div style="color:#999;font-size:12px;">Last updated: {ts_th}</div>
            </div>
            
            <!-- Main Metrics Grid -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
                
                <!-- Cash Balance -->
                <div style="background:linear-gradient(135deg, #e3f2fd, #f3e5f5);padding:16px;border-radius:10px;border-left:5px solid #4c84af;">
                    <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:4px;">💵 Cash Balance</div>
                    <div style="font-size:22px;font-weight:bold;color:#2c3e50;">฿{cash:,.2f}</div>
                    <div style="font-size:12px;color:#999;margin-top:4px;">{cash_pct:.1f}% of total</div>
                </div>
                
                <!-- Gold Position -->
                <div style="background:linear-gradient(135deg, #fff8e1, #ffe0b2);padding:16px;border-radius:10px;border-left:5px solid #c9a84c;">
                    <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:4px;">🥇 Gold Position</div>
                    <div style="font-size:22px;font-weight:bold;color:#2c3e50;">{gold_g:.4f} g</div>
                    <div style="font-size:12px;color:#999;margin-top:4px;">{gold_pct:.1f}% of total value</div>
                </div>
                
                <!-- Cost Basis -->
                <div style="background:linear-gradient(135deg, #f3e5f5, #e1f5fe);padding:16px;border-radius:10px;border-left:5px solid #7a5c1a;">
                    <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:4px;">📥 Cost Basis</div>
                    <div style="font-size:22px;font-weight:bold;color:#2c3e50;">฿{cost:,.2f}</div>
                    <div style="font-size:12px;color:#999;margin-top:4px;">Average: ฿{cost/gold_g:.2f}/g</div>
                </div>
                
                <!-- Current Value -->
                <div style="background:linear-gradient(135deg, #e8f5e9, #f1f8e9);padding:16px;border-radius:10px;border-left:5px solid #4caf7d;">
                    <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:4px;">📊 Current Value</div>
                    <div style="font-size:22px;font-weight:bold;color:#2c3e50;">฿{cur_val:,.2f}</div>
                    <div style="font-size:12px;color:#999;margin-top:4px;">Current: ฿{cur_val/gold_g:.2f}/g</div>
                </div>
            </div>
            
            <!-- P&L & ROI Summary -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
                
                <!-- Unrealized P&L -->
                <div style="background:white;padding:14px;border-radius:10px;border-left:5px solid {pnl_color};">
                    <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:4px;">{pnl_icon} Unrealized P&L</div>
                    <div style="font-size:20px;font-weight:bold;color:{pnl_color};">{pnl_prefix}฿{abs(pnl):,.2f}</div>
                    <div style="font-size:12px;color:#999;margin-top:4px;;">{pnl_prefix}{(pnl/cost*100):.1f}% if selling now</div>
                </div>
                
                <!-- ROI -->
                <div style="background:white;padding:14px;border-radius:10px;border-left:5px solid {roi_color};">
                    <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:4px;">{roi_icon} ROI</div>
                    <div style="font-size:20px;font-weight:bold;color:{roi_color};">+{roi:.1f}% </div>
                    <div style="font-size:12px;color:#999;margin-top:4px;">Return on investment</div>
                </div>
            </div>
            
            <!-- Allocation Bar -->
            <div style="background:white;padding:14px;border-radius:10px;margin-bottom:16px;">
                <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:8px;">📊 Asset Allocation</div>
                <div style="display:flex;gap:4px;height:24px;border-radius:4px;overflow:hidden;background:#f0f0f0;">
                    <div style="width:{cash_pct}%;background:linear-gradient(to right, #4c84af, #6fa5d4);border-radius:0;" title="Cash {cash_pct:.1f}%"></div>
                    <div style="width:{gold_pct}%;background:linear-gradient(to right, #c9a84c, #e0c080);border-radius:0;" title="Gold {gold_pct:.1f}%"></div>
                </div>
                <div style="display:flex;gap:16px;margin-top:8px;font-size:11px;">
                    <div><span style="display:inline-block;width:12px;height:12px;background:#4c84af;border-radius:2px;margin-right:4px;"></span>Cash: {cash_pct:.1f}%</div>
                    <div><span style="display:inline-block;width:12px;height:12px;background:#c9a84c;border-radius:2px;margin-right:4px;"></span>Gold: {gold_pct:.1f}%</div>
                </div>
            </div>
            
            <!-- Trading Constraints -->
            <div style="background:#f5f5f5;padding:14px;border-radius:10px;border-left:5px solid #999;">
                <div style="color:#666;font-size:11px;text-transform:uppercase;font-weight:600;margin-bottom:8px;">⚙️ Constraints</div>
                <div style="display:flex;gap:12px;flex-wrap:wrap;">
                    <div style="padding:6px 12px;border-radius:6px;background:{'#e8f5e9' if can_buy else '#ffebee'};border:1px solid {'#4caf7d' if can_buy else '#ef5350'};font-size:12px;">
                        {'✅' if can_buy else '❌'} <b>Can Buy</b> (Min ฿1,000)
                    </div>
                    <div style="padding:6px 12px;border-radius:6px;background:{'#e8f5e9' if can_sell else '#ffebee'};border:1px solid {'#4caf7d' if can_sell else '#ef5350'};font-size:12px;">
                        {'✅' if can_sell else '❌'} <b>Can Sell</b> ({gold_g:.4f}g)
                    </div>
                    <div style="padding:6px 12px;border-radius:6px;background:#e3f2fd;border:1px solid #4c84af;font-size:12px;">
                        🔄 <b>Trades Today:</b> {int(trades)}
                    </div>
                </div>
            </div>
        </div>
        """
        
        return html


# ─────────────────────────────────────────────
# Stats Renderer
# ─────────────────────────────────────────────

class StatsRenderer:
    """Render statistics summary"""
    
    @staticmethod
    def format_stats_html(stats: dict) -> str:
        """Format statistics to HTML badge"""
        total = stats.get("total", 0)
        if total == 0:
            return "<span style='color:#888;font-size:13px'>📊 No data yet</span>"
        
        buy_count = stats.get("buy_count", 0)
        sell_count = stats.get("sell_count", 0)
        hold_count = stats.get("hold_count", 0)
        buy_pct = (buy_count / total * 100) if total > 0 else 0
        sell_pct = (sell_count / total * 100) if total > 0 else 0
        hold_pct = (hold_count / total * 100) if total > 0 else 0
        
        avg_conf = stats.get("avg_confidence", 0)
        avg_price = stats.get("avg_price", 0)
        
        html = f"""
        <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;padding:8px 12px;background:#f8f8f8;border-radius:8px;font-family:monospace;font-size:13px;">
            <div style="padding:4px 8px;background:white;border-radius:4px;">
                <b>{total}</b> runs total
            </div>
            <div style="padding:4px 8px;background:#e8f5e9;border-radius:4px;color:#2e7d32;">
                🟢 BUY: <b>{buy_count}</b> ({buy_pct:.0f}%)
            </div>
            <div style="padding:4px 8px;background:#ffebee;border-radius:4px;color:#c62828;">
                🔴 SELL: <b>{sell_count}</b> ({sell_pct:.0f}%)
            </div>
            <div style="padding:4px 8px;background:#fff8e1;border-radius:4px;color:#f57f17;">
                🟡 HOLD: <b>{hold_count}</b> ({hold_pct:.0f}%)
            </div>
            <div style="padding:4px 8px;background:white;border-radius:4px;">
                avg conf: <b>{avg_conf:.0%}</b>
            </div>
            <div style="padding:4px 8px;background:white;border-radius:4px;">
                avg price: <b>฿{avg_price:.0f}</b>
            </div>
        </div>
        """
        
        return html


# ─────────────────────────────────────────────
# Error/Status Renderer
# ─────────────────────────────────────────────

class StatusRenderer:
    """Render status badges and alerts"""
    
    @staticmethod
    def error_badge(message: str, is_validation: bool = False) -> str:
        """Render error badge"""
        icon = "❌" if is_validation else "⚠️"
        bg = "#ffebee" if is_validation else "#fff3e0"
        border = "#ef5350" if is_validation else "#ff9800"
        color = "#c62828" if is_validation else "#e65100"
        
        return f"""
        <div style="padding:12px 16px;background:{bg};border:2px solid {border};border-radius:8px;color:{color};font-weight:500;">
            {icon} {message}
        </div>
        """
    
    @staticmethod
    def success_badge(message: str) -> str:
        """Render success badge"""
        return f"""
        <div style="padding:12px 16px;background:#e8f5e9;border:2px solid #4caf7d;border-radius:8px;color:#2e7d32;font-weight:500;">
            ✅ {message}
        </div>
        """
    
    @staticmethod
    def info_badge(message: str) -> str:
        """Render info badge"""
        return f"""
        <div style="padding:12px 16px;background:#e3f2fd;border:2px solid #4c84af;border-radius:8px;color:#1565c0;font-weight:500;">
            ℹ️ {message}
        </div>
        """

    @staticmethod
    def warning_badge(message: str) -> str:
        """Render warning badge (ตลาดปิด / ราคาล่าช้า)"""
        return f"""
        <div style="padding:12px 16px;background:#fff8e1;border:2px solid #f9a825;border-radius:8px;color:#e65100;font-weight:500;">
            {message}
        </div>
        """