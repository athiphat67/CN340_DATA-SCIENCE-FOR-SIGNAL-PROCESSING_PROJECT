"""
model_utils.py — Model Loading & Management Utilities
จัดการการโหลด ML models สำหรับ GoldTrader Dashboard:
  - LLM Client factory wrapper
  - Technical analysis model helpers
  - Signal scoring utilities
"""

import os
import logging
import hashlib
import json
from typing import Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Supported Providers
# ─────────────────────────────────────────────

PROVIDER_CONFIGS = {
    "gemini": {
        "display_name" : "Gemini 2.5 Flash",
        "env_key"      : "GEMINI_API_KEY",
        "model_id"     : "gemini-2.5-flash-preview-04-17",
        "max_tokens"   : 8192,
        "free_tier"    : True,
        "rate_limit"   : "15 req/min (free)",
    },
    "groq": {
        "display_name" : "LLaMA 3.3 70B (Groq)",
        "env_key"      : "GROQ_API_KEY",
        "model_id"     : "llama-3.3-70b-versatile",
        "max_tokens"   : 4096,
        "free_tier"    : True,
        "rate_limit"   : "30 req/min (free)",
    },
    "mock": {
        "display_name" : "Mock (Testing)",
        "env_key"      : None,
        "model_id"     : "mock-v1",
        "max_tokens"   : 0,
        "free_tier"    : True,
        "rate_limit"   : "unlimited",
    },
}

# ─────────────────────────────────────────────
# Model Registry — in-memory cache
# ─────────────────────────────────────────────

_model_cache: dict[str, Any] = {}
_load_stats: dict[str, int]  = {}   # provider → load count


class ModelRegistry:
    """
    Lazy-load และ cache LLM clients
    ทำให้ไม่ต้อง instantiate ใหม่ทุก request
    """

    def get_client(self, provider: str, force_reload: bool = False) -> Any:
        """
        โหลด LLM client ตาม provider
        ใช้ cache เพื่อลด latency
        """
        if provider not in PROVIDER_CONFIGS:
            raise ValueError(f"Unknown provider: {provider}. Choose from: {list(PROVIDER_CONFIGS.keys())}")

        cache_key = f"llm_{provider}"

        if not force_reload and cache_key in _model_cache:
            logger.debug(f"[ModelRegistry] cache hit: {provider}")
            return _model_cache[cache_key]

        logger.info(f"[ModelRegistry] loading client: {provider}")

        try:
            from agent_core.llm.client import LLMClientFactory
            client = LLMClientFactory.create(provider)
            _model_cache[cache_key] = client
            _load_stats[provider]   = _load_stats.get(provider, 0) + 1
            return client
        except ImportError:
            logger.error("[ModelRegistry] agent_core not found — returning MockClient")
            client = MockLLMClient(provider)
            _model_cache[cache_key] = client
            return client

    def invalidate(self, provider: Optional[str] = None) -> None:
        """ล้าง cache — ทั้งหมด หรือเฉพาะ provider"""
        if provider:
            _model_cache.pop(f"llm_{provider}", None)
        else:
            _model_cache.clear()
        logger.info(f"[ModelRegistry] cache invalidated: {provider or 'all'}")

    def get_status(self) -> list[dict]:
        """สรุปสถานะ provider ทั้งหมด"""
        results = []
        for name, cfg in PROVIDER_CONFIGS.items():
            env_key   = cfg.get("env_key")
            has_key   = bool(os.getenv(env_key)) if env_key else True
            is_cached = f"llm_{name}" in _model_cache
            results.append({
                "provider"     : name,
                "display_name" : cfg["display_name"],
                "model_id"     : cfg["model_id"],
                "free_tier"    : cfg["free_tier"],
                "rate_limit"   : cfg["rate_limit"],
                "api_key_set"  : has_key,
                "cached"       : is_cached,
                "load_count"   : _load_stats.get(name, 0),
            })
        return results

    def format_status_html(self) -> str:
        """แสดงสถานะ provider เป็น HTML"""
        rows = []
        for s in self.get_status():
            key_badge = (
                "<span style='color:#1a7a4a;font-weight:bold'>✅ Set</span>"
                if s["api_key_set"]
                else "<span style='color:#b22222;font-weight:bold'>❌ Missing</span>"
            )
            cache_badge = (
                "<span style='color:#1a4a7a'>🔵 Cached</span>"
                if s["cached"]
                else "<span style='color:#888'>○ Not loaded</span>"
            )
            rows.append(f"""
            <tr style="border-bottom:1px solid #eee">
                <td style="padding:8px 12px;font-weight:bold">{s['display_name']}</td>
                <td style="padding:8px 12px;font-family:monospace;font-size:12px">{s['model_id']}</td>
                <td style="padding:8px 12px">{'🆓 Free' if s['free_tier'] else '💰 Paid'}</td>
                <td style="padding:8px 12px;font-size:12px">{s['rate_limit']}</td>
                <td style="padding:8px 12px">{key_badge}</td>
                <td style="padding:8px 12px">{cache_badge}</td>
                <td style="padding:8px 12px;text-align:right;color:#888">{s['load_count']}</td>
            </tr>""")

        return f"""
        <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:monospace">
        <thead>
        <tr style="background:#f4f4f4;border-bottom:2px solid #ddd">
            <th style="padding:8px 12px;text-align:left">Provider</th>
            <th style="padding:8px 12px;text-align:left">Model ID</th>
            <th style="padding:8px 12px;text-align:left">Tier</th>
            <th style="padding:8px 12px;text-align:left">Rate Limit</th>
            <th style="padding:8px 12px;text-align:left">API Key</th>
            <th style="padding:8px 12px;text-align:left">Cache</th>
            <th style="padding:8px 12px;text-align:right">Loads</th>
        </tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
        </table>"""


# ─────────────────────────────────────────────
# Mock client (ใช้สำหรับ test หรือเมื่อ import ล้มเหลว)
# ─────────────────────────────────────────────

class MockLLMClient:
    """Mock LLM client สำหรับ dev/test โดยไม่ต้อง API key"""

    def __init__(self, provider: str = "mock"):
        self.provider = provider

    def complete(self, prompt: str, **kwargs) -> str:
        return json.dumps({
            "signal"     : "HOLD",
            "confidence" : 0.5,
            "entry_price": None,
            "stop_loss"  : None,
            "take_profit": None,
            "rationale"  : "[MOCK] No real LLM connected. This is a test response.",
            "action"     : "FINAL_DECISION",
            "thought"    : "Mock analysis — no real data processed.",
        })


# ─────────────────────────────────────────────
# Signal scoring utilities
# ─────────────────────────────────────────────

def score_signal(signal: str, confidence: float) -> dict:
    """
    คำนวณ composite score จาก signal + confidence
    ใช้สำหรับ ranking multi-interval signals
    """
    base_scores = {"BUY": 1.0, "HOLD": 0.0, "SELL": -1.0}
    base = base_scores.get(signal.upper(), 0.0)
    score = base * confidence
    return {
        "signal"    : signal,
        "confidence": confidence,
        "score"     : round(score, 4),
        "strength"  : _score_label(abs(score)),
    }


def _score_label(abs_score: float) -> str:
    if abs_score >= 0.75:
        return "STRONG"
    elif abs_score >= 0.50:
        return "MODERATE"
    elif abs_score >= 0.25:
        return "WEAK"
    return "NEUTRAL"


def aggregate_signals(signal_list: list[dict]) -> dict:
    """
    รวม signals จากหลาย interval → weighted consensus
    signal_list: [{"interval": "1h", "signal": "BUY", "confidence": 0.8}, ...]
    """
    # น้ำหนัก timeframe — longer = higher weight
    weights = {"15m": 1, "30m": 1.5, "1h": 2, "4h": 3, "1d": 4}

    total_weight = 0.0
    weighted_score = 0.0
    base_scores = {"BUY": 1.0, "HOLD": 0.0, "SELL": -1.0}

    for s in signal_list:
        sig = s.get("signal", "HOLD").upper()
        conf = float(s.get("confidence", 0.5))
        tf = s.get("interval", "1h")
        w = weights.get(tf, 1)
        weighted_score += base_scores.get(sig, 0) * conf * w
        total_weight += w

    if total_weight == 0:
        return {"signal": "HOLD", "confidence": 0.0, "score": 0.0}

    final_score = weighted_score / total_weight

    if final_score > 0.15:
        final_signal = "BUY"
    elif final_score < -0.15:
        final_signal = "SELL"
    else:
        final_signal = "HOLD"

    return {
        "signal"    : final_signal,
        "confidence": round(abs(final_score), 4),
        "score"     : round(final_score, 4),
        "strength"  : _score_label(abs(final_score)),
    }


# ─────────────────────────────────────────────
# Prompt hash utility — ตรวจ duplicate runs
# ─────────────────────────────────────────────

def compute_market_hash(market_state: dict) -> str:
    """
    สร้าง hash จาก market state
    ใช้ตรวจว่า market เปลี่ยนหรือเปล่าก่อน re-run
    """
    key_data = {
        "price"   : market_state.get("market_data", {}).get("spot_price_usd", {}).get("price_usd_per_oz"),
        "rsi"     : market_state.get("technical_indicators", {}).get("rsi", {}).get("value"),
        "macd"    : market_state.get("technical_indicators", {}).get("macd", {}).get("macd_line"),
    }
    raw = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ─────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────

model_registry = ModelRegistry()


# ─────────────────────────────────────────────
# Quick test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Provider Status ===")
    for s in model_registry.get_status():
        print(f"  {s['provider']:10s} | key={'✅' if s['api_key_set'] else '❌'} | {s['rate_limit']}")

    print("\n=== Signal Aggregation Test ===")
    test_signals = [
        {"interval": "15m", "signal": "BUY",  "confidence": 0.6},
        {"interval": "1h",  "signal": "BUY",  "confidence": 0.8},
        {"interval": "4h",  "signal": "HOLD", "confidence": 0.5},
        {"interval": "1d",  "signal": "BUY",  "confidence": 0.7},
    ]
    result = aggregate_signals(test_signals)
    print(f"  Consensus: {result}")