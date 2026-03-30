"""
backtest_signal_only_llm.py
══════════════════════════════════════════════════════════════════
Extension ของ SignalOnlyBacktest สำหรับ Local LLM (Ollama)

Features:
  ✅ provider='local_llm'  → เรียก OllamaClient จริง
  ✅ Cache layer           → ไม่ re-run candle ที่เคยทำแล้ว
  ✅ News CSV integration  → merge historical news ต่อ candle
  ✅ Thinking mode strip   → รองรับ Qwen3.5 <think> tags
  ✅ Stateful portfolio    → simulate position ตาม signal ก่อนหน้า

วิธี integrate กับ backtest_signal_only.py เดิม:
  from backtest_signal_only_llm import LLMBacktestMixin
  class SignalOnlyBacktest(LLMBacktestMixin, SignalOnlyBacktest): ...
  
  หรือใช้ standalone:
  from backtest_signal_only_llm import run_llm_backtest

══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

import sys
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_path not in sys.path:
    sys.path.append(root_path)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

DEFAULT_CACHE_DIR   = "backtest_cache"
DEFAULT_NEWS_WINDOW = 120   # นาที: มองย้อนไป 2h ก่อน candle close
NEUTRAL_PORTFOLIO   = {
    "cash_balance":      1_500.0,
    "gold_grams":        0.0,
    "cost_basis_thb":    0.0,
    "current_value_thb": 0.0,
    "unrealized_pnl":    0.0,
    "trades_today":      0,
}

# Qwen3 think-block regex
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────

@dataclass
class BacktestSignal:
    """Output จาก LLM สำหรับ 1 candle"""
    signal:     str   = "HOLD"     # BUY | SELL | HOLD
    confidence: float = 0.5
    rationale:  str   = ""
    cached:     bool  = False      # True = โหลดจาก cache ไม่ได้ยิง API ใหม่
    error:      str   = ""         # ถ้ามี error ใน parse


@dataclass
class SimPortfolio:
    """Simulated portfolio state สำหรับ backtest แบบ stateful"""
    cash_balance:      float = 1_500.0
    gold_grams:        float = 0.0
    cost_basis_thb:    float = 0.0
    trades_today:      int   = 0

    def can_buy(self, min_cash: float = 1_000.0) -> bool:
        return self.cash_balance >= min_cash

    def can_sell(self) -> bool:
        return self.gold_grams > 0

    def execute_buy(self, price_thb_per_gram: float, grams: float = 0.1,
                    spread: float = 30, commission: float = 3) -> bool:
        cost = price_thb_per_gram * grams + spread + commission
        if self.cash_balance < cost:
            return False
        self.cash_balance  -= cost
        self.gold_grams    += grams
        self.cost_basis_thb = price_thb_per_gram
        self.trades_today  += 1
        return True

    def execute_sell(self, price_thb_per_gram: float,
                     spread: float = 30, commission: float = 3) -> bool:
        if self.gold_grams <= 0:
            return False
        proceeds = price_thb_per_gram * self.gold_grams - spread - commission
        self.cash_balance  += proceeds
        self.gold_grams     = 0.0
        self.cost_basis_thb = 0.0
        self.trades_today  += 1
        return True

    def to_dict(self) -> dict:
        current_val = self.gold_grams * self.cost_basis_thb
        return {
            "cash_balance":      round(self.cash_balance, 2),
            "gold_grams":        round(self.gold_grams, 4),
            "cost_basis_thb":    round(self.cost_basis_thb, 2),
            "current_value_thb": round(current_val, 2),
            "unrealized_pnl":    0.0,
            "trades_today":      self.trades_today,
        }


# ─────────────────────────────────────────────────────────────────
# Cache Layer
# ─────────────────────────────────────────────────────────────────

class SignalCache:
    """
    JSON file cache สำหรับ LLM responses ต่อ candle

    Key format: {model}_{timestamp_iso}.json
    ทำให้ถ้า backtest crash กลางคัน → resume ได้โดยไม่ต้อง re-run ทั้งหมด
    """

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR, model: str = "ollama"):
        self.cache_dir = Path(cache_dir)
        self.model_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", model)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def _key(self, timestamp: pd.Timestamp) -> Path:
        ts = timestamp.strftime("%Y%m%dT%H%M")
        return self.cache_dir / f"{self.model_slug}_{ts}.json"

    def get(self, timestamp: pd.Timestamp) -> Optional[BacktestSignal]:
        path = self._key(timestamp)
        if not path.exists():
            self._misses += 1
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._hits += 1
            return BacktestSignal(**data, cached=True)
        except Exception:
            self._misses += 1
            return None

    def set(self, timestamp: pd.Timestamp, signal: BacktestSignal) -> None:
        path = self._key(timestamp)
        data = asdict(signal)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def stats(self) -> Dict:
        total = self._hits + self._misses
        return {
            "hits":      self._hits,
            "misses":    self._misses,
            "total":     total,
            "hit_rate":  round(self._hits / total, 3) if total > 0 else 0.0,
        }


# ─────────────────────────────────────────────────────────────────
# News CSV Loader
# ─────────────────────────────────────────────────────────────────

class NewsLoader:
    """
    โหลด historical news CSV และ query ตาม candle timestamp

    Expected CSV columns:
        datetime        : "2026-01-15 10:00:00"  (UTC หรือ Bangkok time)
        title           : str
        source          : str (optional)
        sentiment_score : float -1.0 to 1.0
        category        : str  "gold_price" | "usd" | "geopolitical" | ...

    GDELT CSV format แตกต่างจากนี้ → ใช้ gdelt_to_news_csv.py แปลงก่อน
    """

    def __init__(self, csv_path: str, window_minutes: int = DEFAULT_NEWS_WINDOW):
        self.window_minutes = window_minutes
        self.df: Optional[pd.DataFrame] = None

        if csv_path and os.path.exists(csv_path):
            self._load(csv_path)
        else:
            logger.warning(f"News CSV ไม่พบ: {csv_path} → จะใช้ no-news mode")

    def _load(self, path: str) -> None:
        df = pd.read_csv(path)
        required = {"datetime", "title", "sentiment_score"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"News CSV ขาด columns: {missing}")

        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        self.df = df
        logger.info(f"✓ News loaded: {len(df)} articles ({path})")

    def get_news_for_candle(self, candle_ts: pd.Timestamp) -> List[Dict]:
        """
        คืน list ของ news articles ที่ publish ภายใน window ก่อน candle close

        Args:
            candle_ts: timestamp ของ candle (close time)

        Returns:
            List[Dict] เรียง sentiment descending (สำคัญสุดก่อน)
        """
        if self.df is None:
            return []

        window_start = candle_ts - timedelta(minutes=self.window_minutes)
        mask = (self.df["datetime"] >= window_start) & (self.df["datetime"] <= candle_ts)
        news_df = self.df[mask].copy()

        if news_df.empty:
            return []

        # เรียงตาม abs(sentiment) สูงสุดก่อน → impact มากสุดก่อน
        news_df["_abs_sent"] = news_df["sentiment_score"].abs()
        news_df = news_df.sort_values("_abs_sent", ascending=False).head(5)

        return news_df[["title", "sentiment_score", "category"]].to_dict("records")

    def format_for_prompt(self, articles: List[Dict]) -> str:
        """แปลง articles เป็น text สำหรับ prompt"""
        if not articles:
            return "No recent news available."

        lines = []
        for a in articles:
            sent = a.get("sentiment_score", 0)
            cat  = a.get("category", "general")
            title = a.get("title", "")
            sign = "+" if sent >= 0 else ""
            lines.append(f"  [{cat}] {title[:80]} (sentiment: {sign}{sent:.2f})")

        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Prompt Builder สำหรับ Backtest
# ─────────────────────────────────────────────────────────────────

def build_backtest_prompt(
    row: pd.Series,
    portfolio: SimPortfolio,
    news_text: str,
    interval: str = "1h",
) -> Tuple[str, str]:
    """
    สร้าง (system_prompt, user_prompt) สำหรับ 1 candle

    Args:
        row:        Series จาก agg_df (ต้องมี open/high/low/close_thai, rsi, ema_20, ema_50, macd)
        portfolio:  SimPortfolio state ก่อน candle นี้
        news_text:  formatted news text จาก NewsLoader
        interval:   timeframe string

    Returns:
        (system, user) tuple ที่ใช้กับ OllamaClient โดยตรง
    """

    system = (
        "/no_think\n"                             # ← Qwen3.5: skip thinking mode
        "You are a Thai Gold Trading Analyst. "
        "Analyze the market state and return ONLY a single JSON object. "
        "No markdown, no explanation outside JSON.\n"
        "Required JSON format:\n"
        '{"action": "FINAL_DECISION", '
        '"signal": "BUY"|"SELL"|"HOLD", '
        '"confidence": 0.0-1.0, '
        '"rationale": "brief reason max 100 chars"}'
    )

    # ── portfolio context ─────────────────────────────────────────
    p = portfolio.to_dict()
    can_buy  = "YES" if portfolio.can_buy()  else "NO (insufficient cash)"
    can_sell = "YES" if portfolio.can_sell() else "NO (no gold held)"

    # ── indicators (handle NaN gracefully) ───────────────────────
    def fmt(val, dec=2):
        return f"{val:.{dec}f}" if pd.notna(val) else "N/A"

    rsi_val  = row.get("rsi", float("nan"))
    rsi_sig  = (
        "overbought" if pd.notna(rsi_val) and rsi_val > 70
        else "oversold" if pd.notna(rsi_val) and rsi_val < 30
        else "neutral"
    )

    macd_hist = row.get("macd_hist", float("nan"))
    macd_sig  = (
        "bullish" if pd.notna(macd_hist) and macd_hist > 0
        else "bearish" if pd.notna(macd_hist) and macd_hist < 0
        else "neutral"
    )

    ema20 = row.get("ema_20", float("nan"))
    ema50 = row.get("ema_50", float("nan"))
    trend = (
        "uptrend"   if pd.notna(ema20) and pd.notna(ema50) and ema20 > ema50
        else "downtrend" if pd.notna(ema20) and pd.notna(ema50) and ema20 < ema50
        else "sideways"
    )

    user = f"""### MARKET STATE [{interval}] — {row.get('timestamp', 'N/A')}
Gold (THB/unit): O={fmt(row.get('open_thai'))} H={fmt(row.get('high_thai'))} L={fmt(row.get('low_thai'))} C={fmt(row.get('close_thai'))}
RSI(14): {fmt(rsi_val)} [{rsi_sig}]
MACD: hist={fmt(macd_hist)} [{macd_sig}]
Trend: EMA20={fmt(ema20)} EMA50={fmt(ema50)} [{trend}]

── News ──
{news_text}

── Portfolio ──
Cash: ฿{p['cash_balance']:,.2f} | Gold: {p['gold_grams']:.4f}g
can_buy: {can_buy} | can_sell: {can_sell}
── End Portfolio ──

Give your trading decision as JSON only."""

    return system, user


# ─────────────────────────────────────────────────────────────────
# Response Parser
# ─────────────────────────────────────────────────────────────────

def parse_llm_response(raw: str) -> BacktestSignal:
    """
    Parse LLM response → BacktestSignal

    Handles:
    - Clean JSON
    - JSON wrapped in markdown
    - Residual <think> blocks (safety net)
    - Missing keys → สร้าง HOLD fallback
    """
    # Strip think blocks (safety net นอกจาก OllamaClient แล้ว strip)
    cleaned = _THINK_RE.sub("", raw).strip()

    # Extract JSON block
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if brace:
            cleaned = brace.group(0)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return BacktestSignal(
            signal="HOLD",
            confidence=0.5,
            rationale="parse_error",
            error=f"JSONDecodeError: {e} | raw={raw[:100]}",
        )

    raw_signal = str(data.get("signal", "HOLD")).upper().strip()
    signal = raw_signal if raw_signal in {"BUY", "SELL", "HOLD"} else "HOLD"

    try:
        conf = float(data.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        conf = 0.5

    rationale = str(data.get("rationale", ""))[:200]

    return BacktestSignal(signal=signal, confidence=conf, rationale=rationale)


# ─────────────────────────────────────────────────────────────────
# LLM Backtest Mixin
# ─────────────────────────────────────────────────────────────────

class LLMBacktestMixin:
    """
    Mixin เพิ่ม provider='local_llm' ให้ SignalOnlyBacktest

    การใช้งานแบบ Mixin:
        from backtest_signal_only import SignalOnlyBacktest
        from backtest_signal_only_llm import LLMBacktestMixin

        class BacktestWithLLM(LLMBacktestMixin, SignalOnlyBacktest):
            pass

        bt = BacktestWithLLM(csv_path="...", news_csv="news_historical.csv")
        bt.load_csv()
        bt.aggregate_candles(timeframe="1h", days=90)
        bt.generate_signals(providers=["local_llm", "ma_crossover", "buy_hold"])
        bt.validate_signals()
        metrics = bt.calculate_metrics()
    """

    def init_llm_options(
        self,
        ollama_model:  str  = "qwen2.5:9b",
        ollama_url:    str  = "http://localhost:11434",
        news_csv:      str  = "",
        cache_dir:     str  = DEFAULT_CACHE_DIR,
        news_window:   int  = DEFAULT_NEWS_WINDOW,
        request_delay: float = 0.5,   # วินาที หน่วงระหว่าง candle (ให้ Ollama พัก)
        stateful_portfolio: bool = True,
    ):
        """
        เรียกหลัง __init__() เพื่อตั้งค่า LLM options

        Args:
            ollama_model:  ชื่อ model ใน Ollama (qwen2.5:9b, qwen3.5:9b)
            ollama_url:    URL ของ Ollama server
            news_csv:      path ของ news CSV (ถ้าไม่มีจะใช้ no-news mode)
            cache_dir:     directory เก็บ cache JSON
            news_window:   หน้าต่าง (นาที) สำหรับ match news กับ candle
            request_delay: หน่วงระหว่าง Ollama calls (ป้องกัน overload)
            stateful_portfolio: simulate portfolio state ตาม signal จริง
        """
        self._ollama_model  = ollama_model
        self._ollama_url    = ollama_url
        self._cache         = SignalCache(cache_dir=cache_dir, model=ollama_model)
        self._news_loader   = NewsLoader(csv_path=news_csv, window_minutes=news_window)
        self._request_delay = request_delay
        self._stateful      = stateful_portfolio
        self._llm_client    = None   # lazy init

    def _get_llm_client(self):
        """Lazy init OllamaClient เมื่อจำเป็น"""
        if self._llm_client is None:
            try:
                from agent_core.llm.client import LLMClientFactory
                # register OllamaClient ถ้ายังไม่ได้ทำ
                if "ollama" not in LLMClientFactory.available_providers():
                    from backtest_signal_only_llm import OllamaClient  # noqa
                    LLMClientFactory.register("ollama", OllamaClient)

                self._llm_client = LLMClientFactory.create(
                    "ollama",
                    model=self._ollama_model,
                    base_url=self._ollama_url,
                )
                logger.info(f"✓ OllamaClient initialized: {self._llm_client}")
            except Exception as e:
                logger.error(f"✗ Failed to init OllamaClient: {e}")
                raise
        return self._llm_client

    def _mock_prompt_package(self, system: str, user: str, label: str):
        """สร้าง PromptPackage-like object ที่ compatible กับ LLMClient.call()"""
        from dataclasses import dataclass

        @dataclass
        class _PP:
            system: str
            user: str
            step_label: str

        return _PP(system=system, user=user, step_label=label)

    def _generate_local_llm_signals(
        self, df: pd.DataFrame
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Generate signals สำหรับแต่ละ candle โดยใช้ OllamaClient จริง
        พร้อม cache + news + stateful portfolio

        Returns:
            (signals_series, confidences_series)
        """
        signals:     List[str]   = []
        confidences: List[float] = []
        portfolio = SimPortfolio()

        client = self._get_llm_client()

        total = len(df)
        for idx, row in df.iterrows():
            ts = row["timestamp"]

            # ── 1. Check cache ──────────────────────────────────────
            cached = self._cache.get(ts)
            if cached:
                signals.append(cached.signal)
                confidences.append(cached.confidence)
                logger.debug(f"  [CACHE HIT] {ts} → {cached.signal}")
                # อัปเดต portfolio ด้วย cached signal
                if self._stateful:
                    self._apply_signal_to_portfolio(portfolio, cached.signal, row)
                continue

            # ── 2. Build news context ───────────────────────────────
            articles  = self._news_loader.get_news_for_candle(ts)
            news_text = self._news_loader.format_for_prompt(articles)

            # ── 3. Build prompt ─────────────────────────────────────
            system, user = build_backtest_prompt(
                row=row,
                portfolio=portfolio if self._stateful else SimPortfolio(),
                news_text=news_text,
                interval=getattr(self, "_current_interval", "1h"),
            )
            pkg = self._mock_prompt_package(system, user, "BACKTEST_SIGNAL")

            # ── 4. Call Ollama ──────────────────────────────────────
            progress = f"[{idx+1}/{total}]"
            logger.info(f"  {progress} {ts} → calling Ollama...")

            try:
                raw = client.call(pkg)
                result = parse_llm_response(raw)

                if result.error:
                    logger.warning(f"    ⚠ Parse error: {result.error}")

            except Exception as e:
                logger.error(f"    ✗ Ollama error: {e} → fallback HOLD")
                result = BacktestSignal(signal="HOLD", confidence=0.5,
                                        rationale="ollama_error", error=str(e))

            # ── 5. Cache result ─────────────────────────────────────
            self._cache.set(ts, result)

            signals.append(result.signal)
            confidences.append(result.confidence)

            # ── 6. Update portfolio ─────────────────────────────────
            if self._stateful:
                self._apply_signal_to_portfolio(portfolio, result.signal, row)

            # ── 7. Rate limit ───────────────────────────────────────
            if self._request_delay > 0:
                time.sleep(self._request_delay)

        logger.info(f"✓ LLM signals complete | cache stats: {self._cache.stats}")
        return pd.Series(signals), pd.Series(confidences)

    @staticmethod
    def _apply_signal_to_portfolio(
        portfolio: SimPortfolio, signal: str, row: pd.Series
    ) -> None:
        """Update portfolio state ตาม signal และ candle close price"""
        price = row.get("close_thai", 0)
        if price <= 0:
            return
        if signal == "BUY":
            portfolio.execute_buy(price)
        elif signal == "SELL":
            portfolio.execute_sell(price)

    def generate_signals(self, providers: List[str] = None) -> pd.DataFrame:
        """
        Override generate_signals() ของ SignalOnlyBacktest
        เพิ่ม routing สำหรับ 'local_llm'

        ถ้า providers ไม่มี 'local_llm' → เรียก super() ตามปกติ
        """
        if providers is None:
            providers = ["local_llm", "ma_crossover", "buy_hold", "random"]

        # แยก local_llm ออกก่อน
        llm_providers = [p for p in providers if p == "local_llm"]
        other_providers = [p for p in providers if p != "local_llm"]

        # รัน providers เดิม (parent class)
        if other_providers:
            super().generate_signals(providers=other_providers)  # type: ignore

        # รัน local_llm
        if llm_providers:
            if self.agg_df is None:  # type: ignore
                raise ValueError("Must call aggregate_candles() first")

            # ตั้งค่า interval สำหรับ prompt builder
            self._current_interval = getattr(self, "_last_timeframe", "1h")

            logger.info(f"Generating local_llm signals for {len(self.agg_df)} candles...")  # type: ignore
            sigs, confs = self._generate_local_llm_signals(self.agg_df)  # type: ignore
            self.agg_df["local_llm_signal"] = sigs.values      # type: ignore
            self.agg_df["local_llm_confidence"] = confs.values  # type: ignore

        return self.agg_df  # type: ignore


# ─────────────────────────────────────────────────────────────────
# Standalone runner (ไม่ต้องใช้ Mixin)
# ─────────────────────────────────────────────────────────────────

def run_llm_backtest(
    csv_path:     str,
    news_csv:     str  = "",
    timeframe:    str  = "1h",
    days:         int  = 30,
    ollama_model: str  = "qwen3.5:9b",
    ollama_url:   str  = "http://localhost:11434",
    cache_dir:    str  = DEFAULT_CACHE_DIR,
    output_dir:   str  = "backtest_results",
    compare_providers: List[str] = None,
) -> Dict:
    """
    Standalone runner สำหรับ LLM backtest พร้อม comparison กับ baselines

    Args:
        csv_path:          path ของ 1-minute OHLC CSV
        news_csv:          path ของ historical news CSV (optional)
        timeframe:         '1h' หรือ '4h'
        days:              จำนวนวันย้อนหลัง
        ollama_model:      model name ใน Ollama
        ollama_url:        Ollama server URL
        cache_dir:         directory เก็บ cache
        output_dir:        output directory
        compare_providers: provider เดิมที่จะ compare (default: ma_crossover, buy_hold, random)

    Returns:
        metrics dict
    """
    # import ที่นี่เพื่อหลีกเลี่ยง circular import
    from backtest_signal_only import SignalOnlyBacktest, run_backtest

    if compare_providers is None:
        compare_providers = ["ma_crossover", "buy_hold", "random"]

    # สร้าง Mixin class แบบ dynamic
    class BacktestWithLLM(LLMBacktestMixin, SignalOnlyBacktest):
        pass

    bt = BacktestWithLLM(csv_path=csv_path)
    bt.init_llm_options(
        ollama_model=ollama_model,
        ollama_url=ollama_url,
        news_csv=news_csv,
        cache_dir=cache_dir,
        stateful_portfolio=True,
    )

    # Run pipeline
    bt.load_csv()
    bt._last_timeframe = timeframe
    bt.aggregate_candles(timeframe=timeframe, days=days)

    all_providers = ["local_llm"] + compare_providers
    bt.generate_signals(providers=all_providers)
    bt.validate_signals(validation_horizon=1)
    metrics = bt.calculate_metrics()

    # Export
    import os
    os.makedirs(output_dir, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"llm_backtest_{timeframe}_{days}d_{ts}.csv"
    bt.export_csv(output_dir=output_dir, filename=fname)

    # Print cache stats
    logger.info(f"Cache stats: {bt._cache.stats}")

    return metrics


# ─────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM Backtest Runner (Ollama)")
    parser.add_argument("--csv",        default="data_XAU_THB/thai_gold_1m_dataset.csv")
    parser.add_argument("--news-csv",   default="",              help="Historical news CSV")
    parser.add_argument("--timeframe",  default="1h",            choices=["1h", "4h"])
    parser.add_argument("--days",       default=30,  type=int)
    parser.add_argument("--model",      default="qwen3.5:9b",    help="Ollama model name")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--cache-dir",  default="backtest_cache")
    parser.add_argument("--output-dir", default="backtest_results")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    print("\n" + "=" * 65)
    print("  LLM BACKTEST — Local Ollama")
    print("=" * 65)
    print(f"  CSV:       {args.csv}")
    print(f"  News CSV:  {args.news_csv or '(none)'}")
    print(f"  Timeframe: {args.timeframe} | Days: {args.days}")
    print(f"  Model:     {args.model}")
    print(f"  Ollama:    {args.ollama_url}")
    print("=" * 65 + "\n")

    metrics = run_llm_backtest(
        csv_path=args.csv,
        news_csv=args.news_csv,
        timeframe=args.timeframe,
        days=args.days,
        ollama_model=args.model,
        ollama_url=args.ollama_url,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
    )

    print("\n" + "=" * 65)
    print("  RESULTS")
    print("=" * 65)
    for provider, m in metrics.items():
        print(f"\n{provider.upper()}:")
        for k, v in m.items():
            print(f"  {k:<35} {v}")
    print("\n✓ Done!")
