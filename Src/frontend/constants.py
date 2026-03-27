# ui_components/constants.py

TRADINGVIEW_CHART_HTML = """
    <div>
        <iframe src="https://s.tradingview.com/widgetembed/?symbol=OANDA:XAUUSD&interval=60&theme=dark&style=1&timezone=Asia%2FBangkok"
        style="width:100%; height:520px; border:none;"></iframe>
        <div style="font-size:11px;color:#888;margin-top:6px;font-family:monospace;text-align:right">
        📡 Powered by TradingView · OANDA:XAUUSD · Real-time
        </div>
    </div>
"""

TRADINGVIEW_TICKER_HTML = """
    <iframe src="https://s.tradingview.com/embed-widget/ticker-tape/?locale=en&symbols=%5B%7B%22proName%22%3A%22OANDA%3AXAUUSD%22%2C%22title%22%3A%22Gold%2FUSD%22%7D%2C%7B%22proName%22%3A%22OANDA%3AXAGUSD%22%2C%22title%22%3A%22Silver%2FUSD%22%7D%2C%7B%22proName%22%3A%22TVC%3ADXY%22%2C%22title%22%3A%22USD%20Index%22%7D%2C%7B%22proName%22%3A%22FX_IDC%3AUSDTHB%22%2C%22title%22%3A%22USD%2FTHB%22%7D%5D&colorTheme=dark"
    style="width:100%; height:70px; border:none;"></iframe>
"""

CSS = """
.tab-nav button { font-size: 14px !important; }
.trace-card { font-family: monospace; }
#stats-bar { padding: 8px 12px; background: #f8f8f8; border-radius: 8px; }
"""

PROVIDER_CHOICES = [("gemini-2.5-flash", "gemini"), ("llama-3.3-70b-versatile", "groq"), ("mock", "mock")]
PERIOD_CHOICES   = ["1d", "5d", "7d", "1mo"]
INTERVAL_CHOICES = ["15m", "30m", "1h", "4h", "1d"]

STATUS_BADGE_OFF = """
<div style="display:inline-block; padding:4px 12px; border-radius:16px; 
            background-color:#ffeaea; color:#b22222; font-weight:bold; font-size:12px; border:1px solid #ffcccc">
    ● Auto-run: OFF
</div>
"""

STATUS_BADGE_ACTIVE = """
<div style="display:inline-block; padding:4px 12px; border-radius:16px; 
            background-color:#e6f9ee; color:#1a7a4a; font-weight:bold; font-size:12px; border:1px solid #b7ebc6">
    ● Auto-run: ACTIVE (Every 30m)
</div>
"""

SIGNAL_ICONS = {
    "BUY": "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
    "WAIT": "⚪"
}