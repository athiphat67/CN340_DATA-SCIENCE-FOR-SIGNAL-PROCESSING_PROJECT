"""
backtest_main_pipeline.py
══════════════════════════════════════════════════════════════════════
Backtest ที่จำลอง Main Pipeline จริง (GoldTrader v3.2)

สิ่งที่ใช้จาก main จริงๆ:
  ✅ PromptBuilder.build_final_decision()   — prompt เดียวกับ production
  ✅ ReactOrchestrator.run()                — ReAct loop เดียวกัน
  ✅ RiskManager.evaluate()                 — risk check เดียวกัน
  ✅ roles.json / skills.json               — config เดียวกัน

สิ่งที่ adapter จัดการแทน main:
  → Historical CSV แทน live yfinance
  → News CSV (timestamp+sentiment) แทน live RSS+FinBERT
  → OllamaClient (Qwen3.5) แทน Gemini/Groq
  → SimPortfolio stateful แทน PostgreSQL
  → JSON cache ต่อ candle (resume ได้ถ้า crash)

Directory ที่ต้องมี (relative to Src/):
  backtest/
    data_XAU_THB/
      thai_gold_1m_dataset.csv          ← price data (1-min OHLCV)
    news_api_backtest/
      finnhub_3month_news_ready_v2.csv  ← timestamp, news_count, overall_sentiment
    backtest_cache_main/                ← auto-created, JSON cache per candle
    backtest_results_main/             ← auto-created, output CSV

Market State Structure (ตรงกับที่ PromptBuilder คาดหวัง):
  {
    "market_data": {
      "thai_gold_thb": {"spot_price_thb": float},
      "spot_price":    {"price_usd_per_oz": float},
      "forex":         {"USDTHB": float},
      "ohlcv":         {"open": float, "high": float, "low": float,
                        "close": float, "volume": float}
    },
    "technical_indicators": {
      "rsi":       {"value": float, "period": 14, "signal": str},
      "macd":      {"macd_line": float, "signal_line": float,
                    "histogram": float, "signal": str},
      "trend":     {"ema_20": float, "ema_50": float, "trend": str},
      "bollinger": {"upper": float, "lower": float, "mid": float},
      "atr":       {"value": float}
    },
    "news": {
      "overall_sentiment": float,
      "news_count": int,
      "top_headlines_summary": str
    },
    "portfolio": {
      "cash_balance": float, "gold_grams": float,
      "cost_basis_thb": float, "current_value_thb": float,
      "unrealized_pnl": float, "trades_today": int,
      "can_buy": str, "can_sell": str
    },
    "interval": str,
    "timestamp": str
  }
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import requests

# ── path setup ─────────────────────────────────────────────────────
# รันได้ทั้งจาก Src/ หรือจาก Src/backtest/
_THIS_DIR = Path(__file__).parent.resolve()
for candidate in [_THIS_DIR.parent, _THIS_DIR]:
    if (candidate / "agent_core").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════

GOLD_GRAM_PER_BAHT = 15.244  # 1 บาททอง = 15.244 กรัม
SPREAD_THB = 30.0  # bid/ask spread ออม NOW
COMMISSION_THB = 3.0  # commission per trade
DEFAULT_CASH = 1500.0  # initial portfolio cash
DEFAULT_CACHE_DIR = "backtest_cache_main"
DEFAULT_OUTPUT_DIR = "backtest_results_main"
MIN_CONFIDENCE = 0.7  # จาก roles.json + RiskManager


# ══════════════════════════════════════════════════════════════════
# Ollama Client (ใช้แทน LLMClientFactory สำหรับ backtest)
# ══════════════════════════════════════════════════════════════════


class OllamaClient:
    """
    HTTP client สำหรับ Ollama local server
    Interface เดียวกับ LLMClient ใน agent_core/llm/client.py
    """

    def __init__(
        self,
        model: str = "qwen3.5:9b",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._think_re = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

    def call(self, prompt_package) -> str:
        """
        ส่ง prompt ไป Ollama แล้วคืน raw string response
        รองรับ PromptPackage จาก agent_core และ dataclass ทั่วไป
        """
        system = getattr(prompt_package, "system", "")
        user = getattr(prompt_package, "user", "") or getattr(
            prompt_package, "user_message", ""
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        # strip <think> blocks (Qwen3 thinking mode)
        return self._think_re.sub("", raw).strip()

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════
# Simulated Portfolio (stateful ตาม signal จริง)
# ══════════════════════════════════════════════════════════════════


@dataclass
class SimPortfolio:
    cash_balance: float = DEFAULT_CASH
    gold_grams: float = 0.0
    cost_basis_thb: float = 0.0
    trades_today: int = 0
    _last_date: str = ""

    def reset_daily(self, date_str: str):
        if date_str != self._last_date:
            self.trades_today = 0
            self._last_date = date_str

    def can_buy(self, min_cash: float = 1000.0) -> bool:
        return self.cash_balance >= min_cash

    def can_sell(self) -> bool:
        return self.gold_grams > 1e-4

    def execute_buy(self, price_thb_per_baht: float, position_thb: float) -> bool:
        """ซื้อทอง — price_thb_per_baht คือราคาต่อบาท (หน่วย 15.244 กรัม)"""
        total_cost = position_thb + SPREAD_THB + COMMISSION_THB
        if self.cash_balance < total_cost:
            return False
        grams = (position_thb / price_thb_per_baht) * GOLD_GRAM_PER_BAHT
        self.cash_balance -= total_cost
        self.gold_grams += grams
        self.cost_basis_thb = price_thb_per_baht
        self.trades_today += 1
        return True

    def execute_sell(self, price_thb_per_baht: float) -> bool:
        """ขายทองทั้งหมด"""
        if not self.can_sell():
            return False
        proceeds = (self.gold_grams / GOLD_GRAM_PER_BAHT) * price_thb_per_baht
        net_proceeds = proceeds - SPREAD_THB - COMMISSION_THB
        self.cash_balance += net_proceeds
        self.gold_grams = 0.0
        self.cost_basis_thb = 0.0
        self.trades_today += 1
        return True

    def current_value(self, price_thb_per_baht: float) -> float:
        return (self.gold_grams / GOLD_GRAM_PER_BAHT) * price_thb_per_baht

    def unrealized_pnl(self, price_thb_per_baht: float) -> float:
        if self.gold_grams <= 1e-4:
            return 0.0
        return self.current_value(price_thb_per_baht) - (
            (self.gold_grams / GOLD_GRAM_PER_BAHT) * self.cost_basis_thb
        )

    def to_market_state_dict(self, price_thb_per_baht: float) -> dict:
        cur_val = self.current_value(price_thb_per_baht)
        unr_pnl = self.unrealized_pnl(price_thb_per_baht)
        can_buy = (
            f"YES (cash={self.cash_balance:.0f})"
            if self.can_buy()
            else "NO (cash < 1000)"
        )
        can_sell = (
            f"YES ({self.gold_grams:.4f}g)" if self.can_sell() else "NO (no gold held)"
        )
        return {
            "cash_balance": round(self.cash_balance, 2),
            "gold_grams": round(self.gold_grams, 4),
            "cost_basis_thb": round(self.cost_basis_thb, 2),
            "current_value_thb": round(cur_val, 2),
            "unrealized_pnl": round(unr_pnl, 2),
            "trades_today": self.trades_today,
            "can_buy": can_buy,
            "can_sell": can_sell,
        }


# ══════════════════════════════════════════════════════════════════
# Cache Layer (JSON ต่อ candle — resume ได้ถ้า crash)
# ══════════════════════════════════════════════════════════════════


class CandleCache:
    """
    เก็บผล ReactOrchestrator ต่อ candle เป็น JSON file
    Key: {model}_{timestamp_YYYYmmddTHHMM}.json
    """

    def __init__(self, cache_dir: str, model: str):
        self.dir = Path(cache_dir)
        self.slug = re.sub(r"[^a-zA-Z0-9_-]", "_", model)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._hits = self._misses = 0

    def _path(self, ts: pd.Timestamp) -> Path:
        return self.dir / f"{self.slug}_{ts.strftime('%Y%m%dT%H%M')}.json"

    def get(self, ts: pd.Timestamp) -> Optional[dict]:
        p = self._path(ts)
        if not p.exists():
            self._misses += 1
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self._hits += 1
            return data
        except Exception:
            self._misses += 1
            return None

    def set(self, ts: pd.Timestamp, data: dict):
        self._path(ts).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }


# ══════════════════════════════════════════════════════════════════
# News Loader (CSV: published_at, news_count, overall_sentiment)
# ══════════════════════════════════════════════════════════════════


class HistoricalNewsLoader:
    """
    โหลด finnhub_3month_news_ready_v2.csv แล้ว match กับ candle timestamp
    ใช้ nearest-match (ไม่เกิน window_hours ชั่วโมง ก่อน candle close)
    """

    def __init__(self, csv_path: str, window_hours: int = 4):
        self.window = pd.Timedelta(hours=window_hours)
        self.df: Optional[pd.DataFrame] = None

        if csv_path and os.path.exists(csv_path):
            self._load(csv_path)
        else:
            logger.warning(f"News CSV not found: {csv_path} → no-news mode")

    def _load(self, path: str):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        df["published_at"] = pd.to_datetime(df["published_at"])
        self.df = df.sort_values("published_at").reset_index(drop=True)
        logger.info(f"✓ News loaded: {len(self.df)} rows from {path}")

    def get(self, candle_ts: pd.Timestamp) -> dict:
        """คืน news dict สำหรับ candle นี้ (nearest match ภายใน window)"""
        if self.df is None:
            return {
                "overall_sentiment": 0.0,
                "news_count": 0,
                "top_headlines_summary": "No news data available.",
            }

        window_start = candle_ts - self.window
        mask = (self.df["published_at"] >= window_start) & (
            self.df["published_at"] <= candle_ts
        )
        subset = self.df[mask]

        if subset.empty:
            # fallback: nearest row ก่อน candle
            earlier = self.df[self.df["published_at"] <= candle_ts]
            if earlier.empty:
                return {
                    "overall_sentiment": 0.0,
                    "news_count": 0,
                    "top_headlines_summary": "No news available for this period.",
                }
            subset = earlier.tail(1)

        row = subset.iloc[-1]
        sentiment = float(row.get("overall_sentiment", 0.0))
        news_count = int(row.get("news_count", 0))

        # ถ้ามี top_headlines_summary (จาก v2 ที่มี text) ใช้ได้เลย
        headline = str(row.get("top_headlines_summary", "")).strip()
        if not headline or headline == "nan":
            headline = f"Sentiment score: {sentiment:+.4f} ({news_count} articles)"

        return {
            "overall_sentiment": round(sentiment, 4),
            "news_count": news_count,
            "top_headlines_summary": headline[:300],
        }


# ══════════════════════════════════════════════════════════════════
# Market State Builder
# ══════════════════════════════════════════════════════════════════


def build_market_state(
    row: pd.Series,
    portfolio: SimPortfolio,
    news: dict,
    interval: str,
) -> dict:
    """
    แปลง 1 candle row → market_state dict
    ที่ PromptBuilder / ReactOrchestrator คาดหวัง

    Columns ที่ต้องมีใน row:
      close_thai, open_thai, high_thai, low_thai
      gold_spot_usd, usd_thb_rate
      rsi, macd_line, signal_line, macd_hist (หรือ macd_histogram)
      ema_20, ema_50
      bb_upper, bb_lower, bb_mid   (หรือ bollinger_*)
      atr
      timestamp
    """
    price = float(row.get("close_thai", 0))

    # ── Technical indicators ────────────────────────────────────
    rsi_val = float(row.get("rsi", 50))
    rsi_sig = (
        "overbought" if rsi_val > 70 else "oversold" if rsi_val < 30 else "neutral"
    )

    macd_line = float(row.get("macd_line", 0))
    sig_line = float(row.get("signal_line", 0))
    macd_hist = float(row.get("macd_hist", row.get("macd_histogram", 0)))
    macd_sig = "bullish" if macd_hist > 0 else "bearish" if macd_hist < 0 else "neutral"

    ema20 = float(row.get("ema_20", price))
    ema50 = float(row.get("ema_50", price))
    trend = "uptrend" if ema20 > ema50 else "downtrend" if ema20 < ema50 else "neutral"

    bb_upper = float(row.get("bb_upper", row.get("bollinger_upper", price * 1.02)))
    bb_lower = float(row.get("bb_lower", row.get("bollinger_lower", price * 0.98)))
    bb_mid = float(row.get("bb_mid", row.get("bollinger_mid", price)))

    atr = float(row.get("atr", 0))

    # ── Portfolio state ─────────────────────────────────────────
    port_dict = portfolio.to_market_state_dict(price)

    return {
        "market_data": {
            "thai_gold_thb": {"spot_price_thb": price},
            "spot_price": {"price_usd_per_oz": float(row.get("gold_spot_usd", 0))},
            "forex": {"USDTHB": float(row.get("usd_thb_rate", 0))},
            "ohlcv": {
                "open": float(row.get("open_thai", price)),
                "high": float(row.get("high_thai", price)),
                "low": float(row.get("low_thai", price)),
                "close": price,
                "volume": float(row.get("volume", 0)),
            },
        },
        "technical_indicators": {
            "rsi": {"value": round(rsi_val, 2), "period": 14, "signal": rsi_sig},
            "macd": {
                "macd_line": round(macd_line, 4),
                "signal_line": round(sig_line, 4),
                "histogram": round(macd_hist, 4),
                "signal": macd_sig,
            },
            "trend": {
                "ema_20": round(ema20, 2),
                "ema_50": round(ema50, 2),
                "trend": trend,
            },
            "bollinger": {
                "upper": round(bb_upper, 2),
                "lower": round(bb_lower, 2),
                "mid": round(bb_mid, 2),
            },
            "atr": {"value": round(atr, 2)},
        },
        "news": news,
        "portfolio": port_dict,
        "interval": interval,
        "timestamp": str(row.get("timestamp", "")),
    }


# ══════════════════════════════════════════════════════════════════
# Main Backtest Class
# ══════════════════════════════════════════════════════════════════


class MainPipelineBacktest:
    """
    Backtest ที่รัน ReactOrchestrator จริงจาก main system
    ต่อ historical candle

    Usage:
        bt = MainPipelineBacktest(
            gold_csv="backtest/data_XAU_THB/thai_gold_1m_dataset.csv",
            news_csv="backtest/news_api_backtest/finnhub_3month_news_ready_v2.csv",
            ollama_model="qwen3.5:9b",
            timeframe="1h",
            days=30,
        )
        bt.run()
        bt.export_csv()
    """

    def __init__(
        self,
        gold_csv: str,
        news_csv: str = "",
        ollama_model: str = "qwen3.5:9b",
        ollama_url: str = "http://localhost:11434",
        timeframe: str = "1h",
        days: int = 30,
        cache_dir: str = DEFAULT_CACHE_DIR,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        react_max_iter: int = 5,
        request_delay: float = 0.3,
    ):
        self.gold_csv = gold_csv
        self.timeframe = timeframe
        self.days = days
        self.output_dir = output_dir
        self.react_max_iter = react_max_iter
        self.request_delay = request_delay

        # components
        self.ollama = OllamaClient(model=ollama_model, base_url=ollama_url)
        self.cache = CandleCache(cache_dir=cache_dir, model=ollama_model)
        self.news_loader = HistoricalNewsLoader(news_csv)
        self.portfolio = SimPortfolio()

        # data
        self.raw_df: Optional[pd.DataFrame] = None
        self.agg_df: Optional[pd.DataFrame] = None
        self.results: List[dict] = []

        # lazy-loaded main components
        self._react: Optional[object] = None
        self._prompt_builder: Optional[object] = None
        self._risk_manager: Optional[object] = None

        logger.info(
            f"MainPipelineBacktest init | model={ollama_model} | {timeframe} | {days}d"
        )

    # ── Main system components ─────────────────────────────────

    def _load_main_components(self):
    """Import และ init ReactOrchestrator + PromptBuilder + RiskManager จาก main"""
    if self._react is not None:
        return
 
    try:
        from agent_core.core.prompt import (
            PromptBuilder,
            RoleRegistry,
            SkillRegistry,
            AIRole,
        )
        from agent_core.core.react import ReactOrchestrator, ReactConfig
        from agent_core.core.risk import RiskManager
 
        # ── 1. Load skills.json ─────────────────────────────────────────
        skill_registry = SkillRegistry()
        skills_path = Path(__file__).parent / "agent_core/config/skills.json"
 
        if skills_path.exists():
            # ✅ ใช้ load_from_json() — ไม่ต้อง manual parse
            skill_registry.load_from_json(str(skills_path))
            logger.info(f"✓ Skills loaded from {skills_path}")
        else:
            logger.warning(f"skills.json not found at {skills_path}")
 
        # ── 2. Load roles.json ──────────────────────────────────────────
        role_registry = RoleRegistry(skill_registry)
        roles_path = Path(__file__).parent / "agent_core/config/roles.json"
 
        if roles_path.exists():
            # ✅ ใช้ load_from_json() — จัดการ format + สร้าง RoleDefinition ถูกต้อง
            role_registry.load_from_json(str(roles_path))
            logger.info(f"✓ Roles loaded from {roles_path}")
        else:
            logger.warning(f"roles.json not found at {roles_path}")
 
        # ── 3. เลือก role สำหรับ PromptBuilder ─────────────────────────
        trading_role = AIRole.ANALYST  # default
 
        # safety check: ถ้า ANALYST ไม่ได้ register → fallback role แรกที่มี
        if not role_registry.get(trading_role):
            registered = list(role_registry.roles.keys())
            logger.warning(
                f"⚠ Role {trading_role} ไม่พบ | roles ที่ register: {registered}"
            )
            if registered:
                trading_role = registered[0]
                logger.info(f"  → fallback to: {trading_role}")
            else:
                raise ValueError(
                    "ไม่มี role ใดถูก register\n"
                    "  ตรวจสอบ roles.json ให้มี format:\n"
                    '  {"roles": [{"name": "analyst", "title": "...", ...}]}'
                )
 
        # ── 4. สร้าง PromptBuilder ด้วย signature ที่ถูกต้อง ───────────
        # ✅ Bug fix: (role_registry, current_role) — ไม่ใช่ (skill_registry, role_registry)
        prompt_builder = PromptBuilder(
            role_registry=role_registry,
            current_role=trading_role,     # AIRole enum, ไม่ใช่ object
        )
        self._prompt_builder = prompt_builder
        logger.info(f"✓ PromptBuilder ready | role={trading_role}")
 
        # ── 5. Risk + React ─────────────────────────────────────────────
        risk_manager = RiskManager()
        config = ReactConfig(max_iterations=self.react_max_iter)
        tool_registry = {}
 
        self._react = ReactOrchestrator(
            llm_client=self.ollama,
            prompt_builder=prompt_builder,
            tool_registry=tool_registry,
            config=config,
        )
        self._risk_manager = risk_manager
        logger.info("✓ Main components loaded (ReactOrchestrator, PromptBuilder, RiskManager)")
 
    except ImportError as e:
        raise ImportError(
            f"ไม่พบ agent_core: {e}\n"
            "ตรวจสอบว่า sys.path ชี้ไปที่ Src/ ที่มีโฟลเดอร์ agent_core/"
        ) from e

    # ── Data loading & aggregation ─────────────────────────────

    def load_and_aggregate(self) -> pd.DataFrame:
        """โหลด CSV และ aggregate เป็น candle ตาม timeframe"""
        logger.info(f"Loading: {self.gold_csv}")
        df = pd.read_csv(self.gold_csv)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        self.raw_df = df

        # filter days
        cutoff = df["timestamp"].max() - timedelta(days=self.days)
        df_f = df[df["timestamp"] >= cutoff].copy()
        logger.info(
            f"Filtered: {len(df_f)} rows | {cutoff.date()} → {df_f['timestamp'].max().date()}"
        )

        # aggregate
        df_f = df_f.set_index("timestamp")
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "4h": "4h",
            "1d": "1D",
        }
        freq = freq_map.get(self.timeframe, self.timeframe)

        agg = {
            "open_thai": "first",
            "high_thai": "max",
            "low_thai": "min",
            "close_thai": "last",
            "gold_spot_usd": "mean",
            "usd_thb_rate": "mean",
        }
        # เพิ่ม columns ที่อาจมีใน CSV เข้า agg ด้วย
        optional_cols = [
            "volume",
            "rsi",
            "macd_line",
            "signal_line",
            "macd_hist",
            "macd_histogram",
            "ema_20",
            "ema_50",
            "bb_upper",
            "bb_lower",
            "bb_mid",
            "bollinger_upper",
            "bollinger_lower",
            "bollinger_mid",
            "atr",
        ]
        for col in optional_cols:
            if col in df_f.columns:
                agg[col] = "last"

        self.agg_df = df_f.resample(freq).agg(agg).dropna(subset=["close_thai"])
        self.agg_df = self.agg_df.reset_index()

        # คำนวณ indicators ที่ยังไม่มีใน CSV
        self._ensure_indicators()

        logger.info(f"✓ Aggregated {len(self.agg_df)} candles ({self.timeframe})")
        return self.agg_df

    def _ensure_indicators(self):
        """คำนวณ indicator ที่หายไปจาก CSV"""
        df = self.agg_df
        close = df["close_thai"]

        if "ema_20" not in df.columns:
            df["ema_20"] = close.ewm(span=20, adjust=False).mean()
        if "ema_50" not in df.columns:
            df["ema_50"] = close.ewm(span=50, adjust=False).mean()
        if "rsi" not in df.columns:
            df["rsi"] = self._calc_rsi(close)
        if "macd_line" not in df.columns:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            df["macd_line"] = ema12 - ema26
            df["signal_line"] = df["macd_line"].ewm(span=9, adjust=False).mean()
            df["macd_hist"] = df["macd_line"] - df["signal_line"]
        if "atr" not in df.columns:
            df["atr"] = self._calc_atr(df)
        if "bb_upper" not in df.columns:
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            df["bb_upper"] = sma20 + 2 * std20
            df["bb_lower"] = sma20 - 2 * std20
            df["bb_mid"] = sma20

        self.agg_df = df

    @staticmethod
    def _calc_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df["high_thai"]
        low = df["low_thai"]
        close = df["close_thai"]
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(period).mean()

    # ── Per-candle runner ───────────────────────────────────────

    def _run_candle(self, row: pd.Series) -> dict:
        """
        รัน ReactOrchestrator 1 candle → return result dict

        Result dict:
          timestamp, close_thai,
          llm_signal, llm_confidence, llm_rationale,
          final_signal, final_confidence,
          rejection_reason, position_size_thb,
          stop_loss, take_profit,
          iterations_used, from_cache
        """
        ts = pd.Timestamp(row["timestamp"])

        # ── 1. Cache check ──────────────────────────────────────
        cached = self.cache.get(ts)
        if cached:
            return {**cached, "from_cache": True}

        # ── 2. Build market_state ───────────────────────────────
        news = self.news_loader.get(ts)
        price = float(row["close_thai"])
        self.portfolio.reset_daily(ts.strftime("%Y-%m-%d"))
        market_state = build_market_state(row, self.portfolio, news, self.timeframe)

        # ── 3. Run ReactOrchestrator (real main pipeline) ───────
        try:
            result = self._react.run(market_state)
        except Exception as e:
            logger.error(f"  ✗ React error at {ts}: {e}")
            result = {
                "final_decision": {
                    "signal": "HOLD",
                    "confidence": 0.5,
                    "rationale": f"error: {e}",
                    "rejection_reason": str(e),
                    "position_size_thb": 0.0,
                    "stop_loss": 0.0,
                    "take_profit": 0.0,
                },
                "react_trace": [],
                "iterations_used": 0,
            }

        fd = result.get("final_decision", {})

        # ── 4. Extract pre-risk LLM signal from trace ───────────
        # React trace มี step THOUGHT_FINAL หรือ iteration สุดท้าย
        trace = result.get("react_trace", [])
        llm_signal = "HOLD"
        llm_confidence = 0.5
        llm_rationale = ""
        for step in reversed(trace):
            resp = step.get("response", {})
            if isinstance(resp, dict) and "signal" in resp:
                llm_signal = resp.get("signal", "HOLD")
                llm_confidence = float(resp.get("confidence", 0.5))
                llm_rationale = resp.get("rationale", "")
                break

        candle_result = {
            "timestamp": str(ts),
            "close_thai": price,
            "llm_signal": llm_signal,
            "llm_confidence": llm_confidence,
            "llm_rationale": llm_rationale[:200],
            "final_signal": fd.get("signal", "HOLD"),
            "final_confidence": fd.get("confidence", llm_confidence),
            "rejection_reason": fd.get("rejection_reason"),
            "position_size_thb": fd.get("position_size_thb", 0.0),
            "stop_loss": fd.get("stop_loss", 0.0),
            "take_profit": fd.get("take_profit", 0.0),
            "iterations_used": result.get("iterations_used", 1),
            "news_sentiment": news.get("overall_sentiment", 0.0),
            "from_cache": False,
        }

        # ── 5. Cache ────────────────────────────────────────────
        self.cache.set(ts, candle_result)
        return candle_result

    def _apply_to_portfolio(self, candle_result: dict):
        """อัปเดต portfolio ตาม final_signal"""
        signal = candle_result["final_signal"]
        price = candle_result["close_thai"]
        pos_size = candle_result["position_size_thb"]

        if signal == "BUY":
            ok = self.portfolio.execute_buy(price, pos_size)
            if not ok:
                logger.debug(
                    f"  BUY skipped (insufficient cash): {self.portfolio.cash_balance:.0f} THB"
                )
        elif signal == "SELL":
            self.portfolio.execute_sell(price)

    # ── Full run ────────────────────────────────────────────────

    def run(self):
        """รัน backtest ทั้งหมด"""
        if self.agg_df is None:
            self.load_and_aggregate()

        self._load_main_components()

        total = len(self.agg_df)
        logger.info(f"\n{'='*60}")
        logger.info(
            f"Starting backtest: {total} candles | {self.timeframe} | {self.days}d"
        )
        logger.info(f"{'='*60}")

        for idx, row in self.agg_df.iterrows():
            ts = row["timestamp"]
            progress = f"[{idx+1}/{total}]"

            result = self._run_candle(row)
            self._apply_to_portfolio(result)
            self.results.append(result)

            cache_tag = "[CACHE]" if result["from_cache"] else ""
            logger.info(
                f"  {progress} {ts} | "
                f"LLM={result['llm_signal']}({result['llm_confidence']:.2f}) → "
                f"FINAL={result['final_signal']} "
                f"{'[REJECTED]' if result['rejection_reason'] else ''} {cache_tag}"
            )

            if not result["from_cache"] and self.request_delay > 0:
                time.sleep(self.request_delay)

        logger.info(f"\n✓ Backtest complete | cache: {self.cache.stats}")
        self._add_validation()

    def _add_validation(self):
        """เพิ่ม actual_direction และ validation columns"""
        df = pd.DataFrame(self.results)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["next_close"] = df["close_thai"].shift(-1)
        df["price_change"] = df["next_close"] - df["close_thai"]
        df["actual_direction"] = df["price_change"].apply(
            lambda x: "UP" if x > 0 else ("DOWN" if x < 0 else "FLAT")
        )
        df["net_pnl_thb"] = df["price_change"] - SPREAD_THB - COMMISSION_THB

        # validate ทั้ง llm_signal และ final_signal
        for col_prefix in ["llm", "final"]:
            sig_col = f"{col_prefix}_signal"
            corr_col = f"{col_prefix}_correct"
            prof_col = f"{col_prefix}_profitable"

            df[corr_col] = df.apply(
                lambda r: _signal_correct(r[sig_col], r["actual_direction"]), axis=1
            )
            df[prof_col] = df[corr_col] & (df["net_pnl_thb"] > 0)

        self.result_df = df

    # ── Metrics & export ────────────────────────────────────────

    def calculate_metrics(self) -> dict:
        df = self.result_df.copy()
        metrics = {}

        for prefix in ["llm", "final"]:
            active = df[df[f"{prefix}_signal"] != "HOLD"]
            total = len(active)

            if total == 0:
                metrics[prefix] = {"note": "all HOLD"}
                continue

            correct = active[f"{prefix}_correct"].sum()
            profitable = active[f"{prefix}_profitable"].sum()
            accuracy = correct / total * 100
            sensitivity = total / len(df) * 100

            correct_rows = active[active[f"{prefix}_correct"]]
            avg_pnl = correct_rows["net_pnl_thb"].mean() if len(correct_rows) else 0.0

            buy_count = (active[f"{prefix}_signal"] == "BUY").sum()
            sell_count = (active[f"{prefix}_signal"] == "SELL").sum()

            rejected_count = (
                df["rejection_reason"].notna().sum() if prefix == "final" else 0
            )

            metrics[prefix] = {
                "directional_accuracy_pct": round(accuracy, 2),
                "signal_sensitivity_pct": round(sensitivity, 2),
                "total_signals": total,
                "buy_signals": int(buy_count),
                "sell_signals": int(sell_count),
                "correct_signals": int(correct),
                "correct_profitable": int(profitable),
                "avg_net_pnl_thb": round(avg_pnl, 2),
                "rejected_by_risk": int(rejected_count),
                "avg_confidence": round(active[f"{prefix}_confidence"].mean(), 3),
            }

        self.metrics = metrics

        # พิมพ์สรุป
        logger.info("\n" + "=" * 60)
        logger.info("METRICS SUMMARY")
        logger.info("=" * 60)
        for name, m in metrics.items():
            logger.info(f"\n{name.upper()}:")
            for k, v in m.items():
                logger.info(f"  {k:<35} {v}")

        return metrics

    def export_csv(self, filename: str = None) -> str:
        os.makedirs(self.output_dir, exist_ok=True)

        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"main_backtest_{self.timeframe}_{self.days}d_{ts}.csv"

        path = os.path.join(self.output_dir, filename)
        df = self.result_df.copy()

        # columns ที่ต้องการ export
        export_cols = [
            "timestamp",
            "close_thai",
            "actual_direction",
            "price_change",
            "net_pnl_thb",
            "news_sentiment",
            "llm_signal",
            "llm_confidence",
            "llm_rationale",
            "llm_correct",
            "llm_profitable",
            "final_signal",
            "final_confidence",
            "final_correct",
            "final_profitable",
            "rejection_reason",
            "position_size_thb",
            "stop_loss",
            "take_profit",
            "iterations_used",
            "from_cache",
        ]
        export_cols = [c for c in export_cols if c in df.columns]

        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("=== MAIN PIPELINE BACKTEST — SUMMARY ===\n")
            if hasattr(self, "metrics"):
                for name, m in self.metrics.items():
                    for k, v in m.items():
                        f.write(f"{name}_{k},{v}\n")
            f.write("\n=== DETAILED SIGNAL LOG ===\n")
            df[export_cols].to_csv(f, index=False)

        logger.info(f"✓ Exported: {path}")
        return path


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _signal_correct(signal: str, actual: str) -> bool:
    if signal == "HOLD":
        return actual == "FLAT"
    if signal == "BUY":
        return actual == "UP"
    if signal == "SELL":
        return actual == "DOWN"
    return False


# ══════════════════════════════════════════════════════════════════
# Standalone runner function
# ══════════════════════════════════════════════════════════════════


def run_main_backtest(
    gold_csv: str,
    news_csv: str = "",
    timeframe: str = "1h",
    days: int = 30,
    ollama_model: str = "qwen3.5:9b",
    ollama_url: str = "http://localhost:11434",
    cache_dir: str = DEFAULT_CACHE_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    react_max_iter: int = 5,
) -> dict:
    bt = MainPipelineBacktest(
        gold_csv=gold_csv,
        news_csv=news_csv,
        ollama_model=ollama_model,
        ollama_url=ollama_url,
        timeframe=timeframe,
        days=days,
        cache_dir=cache_dir,
        output_dir=output_dir,
        react_max_iter=react_max_iter,
    )
    bt.run()
    metrics = bt.calculate_metrics()
    bt.export_csv()
    return metrics
