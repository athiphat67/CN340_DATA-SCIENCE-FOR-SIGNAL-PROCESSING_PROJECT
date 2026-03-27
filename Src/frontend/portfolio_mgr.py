# ui_components/portfolio_mgr.py
from datetime import datetime, timedelta
import gradio as gr

def format_portfolio_html(p: dict) -> str:
    """สร้าง HTML สำหรับแสดงผล Portfolio Summary บน Dashboard"""
    if not p:
        return "<p style='color:#888'>No portfolio data.</p>"

    cash     = p.get("cash_balance", 0.0)
    gold_g   = p.get("gold_grams", 0.0)
    cost     = p.get("cost_basis_thb", 0.0)
    cur_val  = p.get("current_value_thb", 0.0)
    pnl      = p.get("unrealized_pnl", 0.0)
    trades   = p.get("trades_today", 0)
    updated  = p.get("updated_at", "")

    pnl_color  = "#1a7a4a" if pnl >= 0 else "#b22222"
    pnl_prefix = "+" if pnl >= 0 else ""
    can_buy    = cash >= 1000
    can_sell   = gold_g > 0

    ts_th = ""
    if updated:
        try:
            # แปลงเวลาเป็น Timezone ไทย (UTC+7)
            dt_utc = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            ts_th  = (dt_utc + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
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

def create_portfolio_handlers(db):
    """
    สร้างฟังก์ชันสำหรับรับ Event จาก Gradio โดยผูกกับ Instance ของ Database
    """
    
    def save_portfolio_fn(cash, gold_g, cost, cur_val, pnl, trades):
        data = {
            "cash_balance"      : cash,
            "gold_grams"        : gold_g,
            "cost_basis_thb"    : cost,
            "current_value_thb" : cur_val,
            "unrealized_pnl"    : pnl,
            "trades_today"      : int(trades),
        }
        try:
            db.save_portfolio(data)
            p = db.get_portfolio()
            return "✅ Portfolio saved!", format_portfolio_html(p)
        except Exception as e:
            return f"❌ Save failed: {e}", ""

    def load_portfolio_to_form():
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

    return save_portfolio_fn, load_portfolio_to_form