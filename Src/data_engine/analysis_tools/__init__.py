# 1. Import all Technical Tools
from .technical_tools import (
    get_htf_trend,
    calculate_ema_distance,
    detect_swing_low,
    detect_rsi_divergence,
    check_bb_rsi_combo,
    get_support_resistance_zones,
    check_spot_thb_alignment,
    detect_breakout_confirmation
)

# 2. Import all Fundamental Tools
from .fundamental_tools import (
    get_deep_news_by_category,
    check_upcoming_economic_calendar,
    get_intermarket_correlation,
    check_fed_speakers_schedule,
    get_institutional_positioning
)

# 3. Map Tool names (Strings returned by LLM) to actual functions
TOOL_REGISTRY = {
    # Technical
    "get_htf_trend": get_htf_trend,
    "calculate_ema_distance": calculate_ema_distance,
    "detect_swing_low": detect_swing_low,
    "detect_rsi_divergence": detect_rsi_divergence,
    "check_bb_rsi_combo": check_bb_rsi_combo,
    "get_support_resistance_zones": get_support_resistance_zones,
    "check_spot_thb_alignment": check_spot_thb_alignment,
    "detect_breakout_confirmation": detect_breakout_confirmation,

    # Fundamental
    "get_deep_news_by_category": get_deep_news_by_category,
    "check_upcoming_economic_calendar": check_upcoming_economic_calendar,
    "get_intermarket_correlation": get_intermarket_correlation,
    "check_fed_speakers_schedule": check_fed_speakers_schedule,
    "get_institutional_positioning": get_institutional_positioning
}

# 4. LLM Manual (To be injected into the System Prompt)
# Clearly defines arguments to prevent the LLM from hallucinating data types.
AVAILABLE_TOOLS_INFO = """
### 📈 1. TECHNICAL ANALYSIS TOOLS (Price Action & Structure) ###
Use these tools to analyze market structures, confirm trends, and find exact entry/exit setups.

1. "get_htf_trend": Identifies the macro trend (Bullish/Bearish) on Higher Timeframes by comparing the current price to the EMA-200.
   - Arguments: {"timeframe": "4h", "history_days": 45} (Supports timeframe: "1h", "4h", "1d")
2. "get_support_resistance_zones": Dynamically maps significant Support and Resistance zones using ATR-adjusted clustering of historical swing points. Use this to see if the price is approaching key liquidity areas.
   - Arguments: {"interval": "15m", "history_days": 5}
3. "detect_swing_low": Scans recent candles for a confirmed "Swing Low" structure (a V-shape bottom followed by a breakout). Use this to confirm a potential bullish reversal.
   - Arguments: {"interval": "15m", "history_days": 3, "lookback_candles": 15}
4. "detect_rsi_divergence": Checks for Bullish RSI Divergence (price makes a lower low, but RSI makes a higher low). Use this to identify weakening selling momentum.
   - Arguments: {"interval": "15m", "history_days": 5, "lookback_candles": 30}
5. "check_bb_rsi_combo": Detects high-probability reversal setups. Triggers when the price breaks below the Lower Bollinger Band, RSI is Oversold (<35), and the MACD histogram is flattening.
   - Arguments: {"interval": "15m", "history_days": 5}
6. "calculate_ema_distance": Measures how far the current price is from the EMA-20 relative to the ATR. Use this to check if the market is "Overextended" and due for a mean reversion (pullback).
   - Arguments: {"interval": "15m", "history_days": 5}
7. "check_spot_thb_alignment": Analyzes the correlation between Spot Gold (XAU/USD) and the Thai Baht (USD/THB). Use this to determine if currency movements will amplify or suppress local Thai Gold prices.
   - Arguments: {"interval": "15m", "lookback_candles": 4}
8. "detect_breakout_confirmation": Evaluates candle anatomy when a Support/Resistance zone is breached. Use this to confirm if a breakout is strong (real) or a potential fakeout.
   - Arguments: {"zone_top": <float>, "zone_bottom": <float>, "interval": "15m", "history_days": 3}

---
### 📰 2. FUNDAMENTAL TOOLS (News & Macro Factors) ###
Use these tools to evaluate economic impacts and news sentiment.

1. "get_deep_news_by_category": Performs a deep-dive analysis into a specific news category to extract detailed articles and sentiment.
   - Arguments: {"category": "fed_policy"} 
   - Supported categories: "gold_price", "usd_thb", "fed_policy", "inflation", "geopolitics", "dollar_index", "thai_economy", "thai_gold_market"

*(Note: Economic calendar, Intermarket correlation, Fed speakers, and Institutional positioning tools are currently pending development and should not be called yet.)*
"""