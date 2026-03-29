"""
config.py — Global configuration from environment
Gold Trading Agent v3.2
"""
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# LLM Providers
# ─────────────────────────────────────────────

PROVIDER_CHOICES = [
    ("gemini-2.5-flash", "gemini"),
    ("llama-3.3-70b-versatile", "groq"),
    ("mock", "mock"), 
    ("qwen3.5:9b (local)",  "ollama"),
]

# ─────────────────────────────────────────────
# Data Periods (detailed - up to 3 months)
# ─────────────────────────────────────────────

PERIOD_CHOICES = [
    "1d",    # 1 day
    "3d",    # 3 days
    "5d",    # 5 days (1 week)
    "7d",    # 1 week
    "14d",   # 2 weeks
    "1mo",   # 1 month (30 days)
    "2mo",   # 2 months
    "3mo",   # 3 months (90 days)
]

PERIOD_LABELS = {
    "1d":   "1 Day",
    "3d":   "3 Days",
    "5d":   "5 Days (1 Week)",
    "7d":   "1 Week",
    "14d":  "2 Weeks",
    "1mo":  "1 Month",
    "2mo":  "2 Months",
    "3mo":  "3 Months",
}

# ─────────────────────────────────────────────
# Candle Intervals (detailed - down to 1 minute)
# ─────────────────────────────────────────────

INTERVAL_CHOICES = [
    "1m",    # 1 minute (scalping)
    "5m",    # 5 minutes (day trading)
    "15m",   # 15 minutes
    "30m",   # 30 minutes
    "1h",    # 1 hour (intraday)
    "4h",    # 4 hours (swing)
    "1d",    # 1 day (position)
    "1w",    # 1 week (long-term)
]

INTERVAL_LABELS = {
    "1m":   "1 Min (Scalping)",
    "5m":   "5 Min (Day Trading)",
    "15m":  "15 Min",
    "30m":  "30 Min",
    "1h":   "1 Hour (Intraday)",
    "4h":   "4 Hours (Swing)",
    "1d":   "1 Day (Position)",
    "1w":   "1 Week (Long-term)",
}

# ─────────────────────────────────────────────
# Weighted Voting (detailed by interval)
# ─────────────────────────────────────────────
# Weight explains how much each interval influences final decision
# Higher weight = more important signal
# Sum of all weights = 1.0

INTERVAL_WEIGHTS = {
    # Scalping/Noise (low weight - risky, high noise)
    "1m":   0.03,    # 3% (very noisy, only for scalpers)
    "5m":   0.05,    # 5% (noisy, day traders only)
    
    # Intraday (medium weight - good for trading)
    "15m":  0.10,    # 10% (decent balance, still noisy)
    "30m":  0.15,    # 15% (good balance)
    
    # Core Trading (high weight - best signals)
    "1h":   0.22,    # 22% (excellent balance - sweet spot)
    "4h":   0.30,    # 30% (strong signal, lower noise)
    
    # Long-term (position weight - strong trends)
    "1d":   0.12,    # 12% (trend confirmation)
    "1w":   0.03,    # 3% (very long-term, might be outdated)
}

# Validate weights sum to 1.0
_weight_sum = sum(INTERVAL_WEIGHTS.values())
assert abs(_weight_sum - 1.0) < 0.001, f"Weights sum to {_weight_sum}, must be 1.0"

# ─────────────────────────────────────────────
# Thai Stock Market Calendar
# ─────────────────────────────────────────────
# Thailand Gold trading hours on ออม NOW platform

THAI_MARKET_CALENDAR = {
    "market_hours": {
        "open": "09:00",      # 9:00 AM Bangkok time
        "close": "16:30",     # 4:30 PM Bangkok time
        "timezone": "Asia/Bangkok",
    },
    "trading_days": {
        "monday": True,
        "tuesday": True,
        "wednesday": True,
        "thursday": True,
        "friday": True,
        "saturday": False,
        "sunday": False,
    },
    "holidays_2024": [
        "2024-01-01",  # New Year's Day
        "2024-02-26",  # Makha Bucha
        "2024-04-06",  # Chakri Memorial Day
        "2024-04-13",  # Songkran Festival (13-15)
        "2024-04-14",
        "2024-04-15",
        "2024-05-01",  # Labour Day
        "2024-05-22",  # Visakha Bucha
        "2024-07-20",  # Buddhist Lent
        "2024-07-28",  # King's Birthday
        "2024-07-29",  # Bridge holiday
        "2024-08-12",  # Queen Suthida's Birthday
        "2024-10-13",  # King Bhumibol Memorial Day
        "2024-10-14",  # Bridge holiday
        "2024-10-23",  # Chulalongkorn Memorial Day
        "2024-12-05",  # King Bhumibol Memorial Day
        "2024-12-10",  # Constitution Day
        "2024-12-31",  # New Year's Eve
    ],
    "holidays_2025": [
        "2025-01-01",  # New Year's Day
        "2025-02-26",  # Makha Bucha
        "2025-04-06",  # Chakri Memorial Day
        "2025-04-13",  # Songkran Festival (13-15)
        "2025-04-14",
        "2025-04-15",
        "2025-05-01",  # Labour Day
        "2025-05-22",  # Visakha Bucha
        "2025-07-20",  # Buddhist Lent
        "2025-07-28",  # King's Birthday
        "2025-08-12",  # Queen Suthida's Birthday
        "2025-10-13",  # King Bhumibol Memorial Day
        "2025-10-23",  # Chulalongkorn Memorial Day
        "2025-12-05",  # King Bhumibol Memorial Day
        "2025-12-10",  # Constitution Day
        "2025-12-31",  # New Year's Eve
    ],
    "holidays_2026": [
        "2026-01-01",  # New Year's Day
        "2026-02-26",  # Makha Bucha
        "2026-04-06",  # Chakri Memorial Day
        "2026-04-13",  # Songkran Festival (13-15)
        "2026-04-14",
        "2026-04-15",
        "2026-05-01",  # Labour Day
        "2026-05-22",  # Visakha Bucha
        "2026-07-20",  # Buddhist Lent
        "2026-07-28",  # King's Birthday
        "2026-08-12",  # Queen Suthida's Birthday
        "2026-10-13",  # King Bhumibol Memorial Day
        "2026-10-23",  # Chulalongkorn Memorial Day
        "2026-12-05",  # King Bhumibol Memorial Day
        "2026-12-10",  # Constitution Day
        "2026-12-31",  # New Year's Eve
    ],
}

def is_thailand_market_open(dt: datetime = None) -> bool:
    """
    Check if Thailand gold market is currently open
    
    Args:
        dt: datetime object (default: now)
    
    Returns:
        True if market is open, False otherwise
    """
    if dt is None:
        dt = datetime.now()
    
    # Check day of week (Monday=0, Sunday=6)
    day_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][dt.weekday()]
    if not THAI_MARKET_CALENDAR["trading_days"][day_name]:
        return False
    
    # Check if it's a holiday
    date_str = dt.strftime("%Y-%m-%d")
    all_holidays = (THAI_MARKET_CALENDAR["holidays_2024"] + 
                   THAI_MARKET_CALENDAR["holidays_2025"] + 
                   THAI_MARKET_CALENDAR["holidays_2026"])
    if date_str in all_holidays:
        return False
    
    # Check if within market hours (09:00-16:30 Bangkok time)
    open_time = datetime.strptime("09:00", "%H:%M").time()
    close_time = datetime.strptime("16:30", "%H:%M").time()
    current_time = dt.time()
    
    return open_time <= current_time <= close_time


# ─────────────────────────────────────────────
# Auto-run Timer Intervals (in minutes)
# ─────────────────────────────────────────────

AUTO_RUN_INTERVALS = {
    "5":   300,      # 5 นาที = 300 วินาที
    "10":  600,      # 10 นาที
    "15":  900,      # 15 นาที (default)
    "30":  1800,     # 30 นาที
    "60":  3600,     # 1 ชั่วโมง
}

DEFAULT_AUTO_RUN = "15"

# ─────────────────────────────────────────────
# Service Configuration
# ─────────────────────────────────────────────

SERVICE_CONFIG = {
    "max_retries": 3,
    "retry_delay": 2,           # exponential backoff base
    "data_fetch_timeout": 30,   # seconds
    "llm_call_timeout": 60,     # seconds
}

# ─────────────────────────────────────────────
# Default Portfolio (if DB is empty)
# ─────────────────────────────────────────────

DEFAULT_PORTFOLIO = {
    "cash_balance": 1500.0,
    "gold_grams": 0.0,
    "cost_basis_thb": 0.0,
    "current_value_thb": 0.0,
    "unrealized_pnl": 0.0,
    "trades_today": 0,
}

# ─────────────────────────────────────────────
# UI Configuration
# ─────────────────────────────────────────────

UI_CONFIG = {
    "title": "🟡 AI Gold Trading Agent Dashboard",
    "theme": "soft",
    "port": int(os.environ.get("PORT", 10000)),
    "show_error": True,
}

# ─────────────────────────────────────────────
# Validation Rules
# ─────────────────────────────────────────────

VALIDATION = {
    "min_cash_for_buy": 1000,      # ออม NOW minimum
    "min_portfolio_update_interval": 60,  # seconds between updates
}

# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────

def get_interval_weight(interval: str) -> float:
    """Get weight for interval, default 0 if not found"""
    return INTERVAL_WEIGHTS.get(interval, 0.0)

def validate_provider(provider: str) -> bool:
    """Validate if provider is in choices"""
    providers = [p[1] for p in PROVIDER_CHOICES]
    return provider in providers

def validate_period(period: str) -> bool:
    """Validate if period is valid"""
    return period in PERIOD_CHOICES

def validate_intervals(intervals: list) -> bool:
    """Validate if all intervals are valid"""
    return all(iv in INTERVAL_CHOICES for iv in intervals)

def get_period_label(period: str) -> str:
    """Get human-readable label for period"""
    return PERIOD_LABELS.get(period, period)

def get_interval_label(interval: str) -> str:
    """Get human-readable label for interval"""
    return INTERVAL_LABELS.get(interval, interval)