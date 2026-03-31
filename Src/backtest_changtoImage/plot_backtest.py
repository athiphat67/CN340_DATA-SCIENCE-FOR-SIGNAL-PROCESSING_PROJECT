import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from io import StringIO

# ─────────────────────────────────────────────
# CONFIG & THEME
# ─────────────────────────────────────────────
OUTPUT_IMAGE = "backtest_dashboard_white.png"
FIGSIZE      = (20, 10)
plt.style.use('default')  # ใช้สไตล์มาตรฐาน (พื้นหลังขาว)

def load_data(filepath):
    summary = {}
    csv_content = []
    is_log = False
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if "=== DETAILED SIGNAL LOG ===" in line:
                is_log = True
                continue
            if is_log:
                csv_content.append(line)
            elif "," in line and "=" not in line:
                parts = line.split(",", 1)
                if len(parts) == 2: summary[parts[0].strip()] = parts[1].strip()

    df = pd.read_csv(StringIO("\n".join(csv_content)))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return summary, df

def plot_dashboard(summary, df, out_path):
    fig = plt.figure(figsize=FIGSIZE, facecolor='white')
    gs = fig.add_gridspec(1, 2, width_ratios=[3.5, 1], wspace=0.15)

    # --- ฝั่งซ้าย: กราฟราคา ---
    ax = fig.add_subplot(gs[0])
    ax.set_facecolor('#fdfdfd')
    
    # วาดราคา Close
    ax.plot(df['timestamp'], df['close_thai'], color='#2563eb', lw=1.2, alpha=0.7, label='Gold Price (THB)')
    
    # จุด BUY / SELL
    buys = df[df['final_signal'] == 'BUY']
    sells = df[df['final_signal'] == 'SELL']
    
    ax.scatter(buys['timestamp'], buys['close_thai'], marker='^', color='#16a34a', s=100, label='BUY Signal', edgecolors='black', linewidths=0.5, zorder=5)
    ax.scatter(sells['timestamp'], sells['close_thai'], marker='v', color='#dc2626', s=100, label='SELL Signal', edgecolors='black', linewidths=0.5, zorder=5)

    ax.set_title("Backtest Analysis: Price & Signals", fontsize=18, fontweight='bold', pad=20, color='#1e293b')
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper left', frameon=True, facecolor='white')

    # --- ฝั่งขวา: Performance Panel ---
    ax_stats = fig.add_subplot(gs[1])
    ax_stats.axis('off')
    
    # ดึงค่ามาแสดง
    total_sig = float(summary.get('final_total_signals', 0))
    win_rate = (float(summary.get('final_correct_signals', 0)) / max(total_sig, 1)) * 100
    
    stats = [
        ("PORTFOLIO SUMMARY", "header"),
        ("Initial Capital", f"{float(summary.get('risk_initial_portfolio_thb', 0)):,.0f} THB"),
        ("Final Portfolio", f"{float(summary.get('risk_final_portfolio_thb', 0)):,.2f} THB"),
        ("Total Return", f"{float(summary.get('risk_total_return_pct', 0)):+.2f}%"),
        ("", "spacer"),
        ("RISK METRICS", "header"),
        ("Max Drawdown", f"{float(summary.get('risk_mdd_pct', 0)):.2f}%"),
        ("Sharpe Ratio", f"{float(summary.get('risk_sharpe_ratio', 0)):.2f}"),
        ("Sortino Ratio", f"{float(summary.get('risk_sortino_ratio', 0)):.2f}"),
        ("", "spacer"),
        ("STRATEGY STATS", "header"),
        ("Win Rate", f"{win_rate:.1f}%"),
        ("Directional Acc.", f"{float(summary.get('final_directional_accuracy_pct', 0)):.2f}%"),
        ("Total Signals", f"{int(total_sig)}"),
        ("BUY / SELL", f"{int(float(summary.get('final_buy_signals',0)))} / {int(float(summary.get('final_sell_signals',0)))}"),
        ("Avg Confidence", f"{summary.get('final_avg_confidence', '0')[:5]}"),
    ]

    y_pos = 0.95
    for label, val in stats:
        if val == "header":
            ax_stats.text(0.05, y_pos, label, fontsize=13, fontweight='bold', color='#1e3a8a', transform=ax_stats.transAxes)
            y_pos -= 0.045
        elif val == "spacer":
            y_pos -= 0.02
        else:
            ax_stats.text(0.05, y_pos, label, fontsize=10, color='#64748b', transform=ax_stats.transAxes)
            # ปรับสีตามค่า (ถ้าเป็นกำไรเป็นสีเขียว ขาดทุนเป็นสีแดง)
            t_color = '#0f172a'
            if "+" in val and "%" in val: t_color = '#16a34a'
            if "-" in val and "%" in val: t_color = '#dc2626'
            
            ax_stats.text(0.95, y_pos, val, fontsize=10, fontweight='bold', ha='right', color=t_color, transform=ax_stats.transAxes)
            y_pos -= 0.035

    # วาดเส้นแบ่ง
    rect = plt.Rectangle((0, 0.02), 1, 0.96, fill=True, color='#f8fafc', transform=ax_stats.transAxes, zorder=-1)
    ax_stats.add_patch(rect)
    line = plt.Line2D([0, 0], [0.02, 0.98], transform=ax_stats.transAxes, color='#e2e8f0', lw=1.5)
    ax_stats.add_artist(line)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"✅ Dashboard (White) บันทึกแล้ว: {os.path.abspath(out_path)}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = [f for f in os.listdir(script_dir) if f.endswith('.csv')]
    
    if csv_files:
        path = os.path.join(script_dir, csv_files[0])
        s_data, d_df = load_data(path)
        plot_dashboard(s_data, d_df, os.path.join(script_dir, OUTPUT_IMAGE))
    else:
        print("❌ ไม่พบไฟล์ CSV")