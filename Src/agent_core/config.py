# config.py
import os

# ─── PATH CONFIGURATION ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ปรับให้ยืดหยุ่นโดยใช้ absolute path
SKILL_MD_PATH = os.path.join(BASE_DIR, "tools", "tools_manual.md")
DATA_DIR      = os.path.join(BASE_DIR, "data")
OUTPUT_PATH    = os.path.join(DATA_DIR, "Output")
DEFAULT_OUTPUT_FILENAME = "Output.json"
DEFAULT_OUTPUT_PATH     = os.path.join(OUTPUT_PATH, DEFAULT_OUTPUT_FILENAME)

# ─── LLM CONFIGURATION ────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"
MAX_ITERATIONS = 5
MAX_TOOL_CALLS = 3

# ─── MOCK DATA ────────────────────────────────────────────────────
MOCK_MARKET_STATE = {
    "timestamp":      "2025-03-25T08:00:00Z",
    "gold_price_usd": 3025.40,
    "rsi_1h":         28.5,
    "macd_signal":    "bullish_crossover",
    "dxy":            103.72,
    "vix":            18.4,
    "us10y_yield":    4.31,
    "spx_1d_return":  -0.0082,
    "gold_etf_flow":  240.5,
}