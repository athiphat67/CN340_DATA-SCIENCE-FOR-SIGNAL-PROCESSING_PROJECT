import json
import logging
from pathlib import Path
import pandas as pd
from data_engine.tools.tool_registry import call_tool
from data_engine.tools.schema_validator import validate_market_state
from data_engine.tools.interceptor_manager import start_interceptor_background
from data_engine.thailand_timestamp import get_thai_time

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
_WEEKEND_WARN        = "Market is closed (Weekend) — Price data might be stale."
_WEEKEND_INSTRUCTION = "Market is closed. Weigh news sentiment higher than short-term indicators."


class GoldTradingOrchestrator:
    def __init__(self, history_days=90, interval="5m",
                 max_news_per_cat=5, output_dir=None):
        start_interceptor_background()

        self.history_days     = history_days
        self.interval         = interval
        self.max_news_per_cat = max_news_per_cat
        self.output_dir       = Path(output_dir) if output_dir else Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # [FIX B2] เพิ่ม interval parameter — รับจาก services.py
    def run(self, save_to_file=True, history_days=None, interval=None) -> dict:
        effective_days     = history_days or self.history_days
        effective_interval = interval or self.interval   # ← ใช้ที่ส่งมา ถ้าไม่ส่ง fallback default

        # ── Step 1: fetch_price ──
        price_result = call_tool("fetch_price",
                                  history_days=effective_days,
                                  interval=effective_interval)

        # จัดการ Timezone: ชดเชย +7h ก่อนส่งคำนวณ Indicator
        ohlcv_df = price_result.get("ohlcv_df")
        if ohlcv_df is not None and not ohlcv_df.empty:
            if ohlcv_df.index.tz is None:
                ohlcv_df.index = ohlcv_df.index + pd.Timedelta(hours=7)

        # ── Step 2: fetch_indicators ──
        ind_result = call_tool("fetch_indicators",
                                ohlcv_df=ohlcv_df,
                                interval=effective_interval)

        # ── Step 3: fetch_news ──
        news_result = call_tool("fetch_news",
                                 max_per_category=self.max_news_per_cat)

        # ── Step 4: Assemble ──
        payload = self._assemble_payload(
            price_result, ind_result, news_result, effective_days, effective_interval
        )

        schema_errors = validate_market_state(payload)
        if schema_errors:
            logger.error(f"🚨 Schema errors: {schema_errors}")

        if save_to_file:
            self._save(payload)

        payload["_raw_ohlcv"] = ohlcv_df
        return payload

    def _assemble_payload(self, price, ind, news, history_days, interval=None) -> dict:
        spot     = price.get("spot_price_usd", {})
        thai     = price.get("thai_gold_thb", {})
        ind_d    = ind.get("indicators", {})
        dq       = ind.get("data_quality", {})
        news_s   = news.get("summary", {})
        now_thai = get_thai_time().isoformat()

        # [FIX B1] _weekend_warn อยู่ใน if block → NameError เมื่อ is_weekend=False
        # แก้: ใช้ constant ระดับ module และครอบทั้ง block ไว้ใน if
        if dq.get("is_weekend"):
            warnings = dq.setdefault("warnings", [])
            if _WEEKEND_WARN not in warnings:          # dedup
                warnings.append(_WEEKEND_WARN)
            dq.setdefault("llm_instruction", _WEEKEND_INSTRUCTION)

        # ── Normalize technical_indicators ──────────────────────────────────────
        macd_d  = ind_d.get("macd", {})
        trend_d = ind_d.get("trend", {})
        if macd_d and "signal" not in macd_d:
            macd_d["signal"] = macd_d.get("crossover", "neutral")
        if trend_d and "trend_signal" not in trend_d:
            trend_d["trend_signal"] = trend_d.get("trend", "neutral")

        # ── thai_gold_thb: เพิ่ม mid_price + timestamp ─────────────────────────
        sell = thai.get("sell_price_thb", 0)
        buy  = thai.get("buy_price_thb", 0)
        thai.setdefault("mid_price_thb", round((sell + buy) / 2, 2) if sell and buy else 0)
        thai.setdefault("timestamp", thai.get("timestamp", now_thai))

        # ── forex: [FIX B5] รับ source จาก fetch_price ด้วย ──────────────────
        forex_data  = price.get("forex", {})
        usd_thb_val = forex_data.get("usd_thb", 0.0)
        _src = (
            forex_data.get("source")
            or forex_data.get("usd_thb_source")
            or forex_data.get("provider")
            or price.get("data_sources", {}).get("forex")
            or "unknown"
        )
        forex = {
            "usd_thb": float(usd_thb_val),
            "source":  _src,
        }

        # ── Transform news ───────────────────────────────────────────────────────
        by_cat      = news.get("by_category", {})
        latest_news = []

        if "top_5_key_headlines" in by_cat:
            latest_news = by_cat.get("top_5_key_headlines", [])
        else:
            for cat_name, cat_data in by_cat.items():
                if isinstance(cat_data, str):
                    continue
                articles = cat_data if isinstance(cat_data, list) else cat_data.get("articles", [])
                for a in articles[:2]:
                    title = a.get("title", "") if isinstance(a, dict) else str(a)
                    if title:
                        latest_news.append(f"[{cat_name}] {title}")

        latest_news = latest_news[:10]

        effective_interval = interval or self.interval
        return {
            "meta": {
                "agent":        "gold-trading-agent",
                "version":      "1.3.0",
                "generated_at": now_thai,
                "history_days": history_days,
                "interval":     effective_interval,   # [FIX B2]
                "data_mode":    "live",
            },
            "data_quality":  dq,
            "data_sources":  price.get("data_sources", {}),
            "market_data": {
                "spot_price_usd":      spot,
                "forex":               forex,
                "thai_gold_thb":       thai,
                "recent_price_action": price.get("recent_price_action", []),
            },
            "technical_indicators": ind_d,
            "news": {
                "summary":     news_s,
                "by_category": by_cat,
                "latest_news": latest_news,
                "news_count":  len(latest_news),
            },
            "portfolio":  {},
            "interval":   effective_interval,          # [FIX B2]
            "timestamp":  now_thai,
        }

    def _save(self, payload: dict):
        ts = get_thai_time().strftime("%Y%m%d_%H%M%S")
        for fp in [self.output_dir / f"payload_{ts}.json",
                   self.output_dir / "latest.json"]:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Saved: {fp}")