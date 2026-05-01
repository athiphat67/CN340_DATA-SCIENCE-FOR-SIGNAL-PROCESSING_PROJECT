"""
run_main_backtest.py  ← PATCHED: เพิ่ม MDD / Sharpe / Sortino
══════════════════════════════════════════════════════════════════════
การเปลี่ยนแปลงจาก version เดิม (ค้นหา # ★ เพื่อดู diff):
  [A] run()               → บันทึก portfolio_total_value ต่อ candle
  [B] _compute_risk_metrics() → method ใหม่
  [C] calculate_metrics() → รวม risk metrics
  [D] export_csv()        → เพิ่ม 3 portfolio columns
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from config.config_loader import load_config
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
from data.csv_loader import load_gold_csv, merge_external_data  # รวม import ไว้ที่เดียว
from engine.market_state_builder import MarketStateBuilder
from engine.news_provider import NewsProvider, NullNewsProvider, create_news_provider
from engine.session_manager import TradingSessionManager
from engine.portfolio import (
    SimPortfolio,
    PortfolioBustException,
    DEFAULT_CASH,
    BUST_THRESHOLD,
    WIN_THRESHOLD,
    SPREAD_THB,
    COMMISSION_THB,
    GOLD_GRAM_PER_BAHT,
)
from metrics.calculator import calculate_trade_metrics, add_calmar
from metrics.deploy_gate import deploy_gate, print_gate_report
from metrics.evaluator import BacktestEvaluator
from engine.directive_builder import DirectiveBuilder

# ── path setup ─────────────────────────────────────────────────────
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

DEFAULT_CACHE_DIR = "output/backtest_cache_main"
DEFAULT_OUTPUT_DIR = "output/backtest_results_main"
MIN_CONFIDENCE = 0.6

_PERIODS_PER_YEAR: Dict[str, int] = {
    "1m": 362_880, "5m": 72_576, "15m": 24_192, "30m": 12_096,
    "1h": 6_048, "4h": 1_512, "1d": 252,
}


# ══════════════════════════════════════════════════════════════════
# Time Estimator
# ══════════════════════════════════════════════════════════════════

class TimeEstimator:
    def __init__(self, window: int = 10):
        from collections import deque
        self.times: deque = deque(maxlen=window)
        self._start: float = 0.0
        self.session_start: float = time.time()

    def tick_start(self):
        self._start = time.time()

    def tick_end(self, current: int, total: int, from_cache: bool = False) -> str:
        elapsed = time.time() - self._start
        if not from_cache:
            self.times.append(elapsed)
        session_elapsed = time.time() - self.session_start
        se_h = int(session_elapsed // 3600)
        se_m = int((session_elapsed % 3600) // 60)
        se_s = int(session_elapsed % 60)
        if not self.times:
            return f"  ⏱ elapsed={se_h:02d}:{se_m:02d}:{se_s:02d}"
        avg = sum(self.times) / len(self.times)
        remaining_sec = (total - current) * avg
        r_h = int(remaining_sec // 3600)
        r_m = int((remaining_sec % 3600) // 60)
        r_s = int(remaining_sec % 60)
        speed = f"{elapsed:.1f}s" if not from_cache else "CACHE"
        return (f"  ⏱ {speed}/candle | elapsed={se_h:02d}:{se_m:02d}:{se_s:02d} | "
                f"ETA={r_h:02d}:{r_m:02d}:{r_s:02d} | avg={avg:.1f}s")


# ══════════════════════════════════════════════════════════════════
# Cache Layer
# ══════════════════════════════════════════════════════════════════

class CandleCache:
    # 🟢 [FIX] เพิ่ม Version เพื่อบังคับ Invalidates Cache เก่าทุกครั้งที่อัพเดท Logic
    _CACHE_VERSION = "v3_sniper" 
    
    def __init__(self, cache_dir: str, model: str):
        self.dir = Path(cache_dir)
        self.slug = re.sub(r"[^a-zA-Z0-9_-]", "_", model)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._hits = self._misses = 0

    def _path(self, ts: pd.Timestamp) -> Path:
        # 🟢 [FIX] ต่อ _CACHE_VERSION เข้าไปในชื่อไฟล์
        return self.dir / f"{self.slug}_{self._CACHE_VERSION}_{ts.strftime('%Y%m%dT%H%M')}.json"

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
        p = self._path(ts)
        p.parent.mkdir(parents=True, exist_ok=True) 
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits, "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }


# ══════════════════════════════════════════════════════════════════
# Main Backtest Class
# ══════════════════════════════════════════════════════════════════

class MainPipelineBacktest:
    def __init__(
        self, gold_csv: str, news_provider: NewsProvider = None, news_csv: str = "",
        external_csv: str = "", provider: str = "gemini", model: str = "",
        timeframe: str = "1h", days: int = 30, start_date: str = None, 
        end_date: str = None, cache_dir: str = DEFAULT_CACHE_DIR,
        output_dir: str = DEFAULT_OUTPUT_DIR, react_max_iter: int = 5, 
        request_delay: float = 0.3,
    ):
        self.gold_csv = gold_csv
        self.external_csv = external_csv
        self.timeframe = timeframe
        self.days = days
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = output_dir
        self.react_max_iter = react_max_iter
        self.request_delay = request_delay

        from agent_core.llm.client import LLMClientFactory
        kwargs = {"model": model} if model else {}
        self.llm_client = LLMClientFactory.create(provider, **kwargs)
        _model_slug = model or getattr(self.llm_client, "model", provider)
        self.cache = CandleCache(cache_dir=cache_dir, model=_model_slug)
        self.timer = TimeEstimator()

        self.raw_df: Optional[pd.DataFrame] = None
        self.agg_df: Optional[pd.DataFrame] = None
        self.result_df: Optional[pd.DataFrame] = None
        self.results: List[dict] = []
        self.metrics: dict = {}

        self._prompt_builder = None
        self._react = None
        self._risk_mgr = None
        self.session_manager = TradingSessionManager()

        if news_provider is not None:
            self.news_provider = news_provider
        elif news_csv:
            self.news_provider = create_news_provider("csv", csv_path=news_csv)
        else:
            self.news_provider = NullNewsProvider()

        self.portfolio = SimPortfolio(
            initial_cash=DEFAULT_CASH, bust_threshold=BUST_THRESHOLD,
            win_threshold=WIN_THRESHOLD,
        )

    def load_and_aggregate(self):
        df = load_gold_csv(self.gold_csv, external_csv=self.external_csv or None, timeframe=self.timeframe)

        if "sell_price" in df.columns:
            df = df.rename(columns={
                "sell_price": "Mock_HSH_Sell_Close", "buy_price": "Mock_HSH_Buy_Close",
                "spot_price_usd": "CLOSE_XAUUSD", "usd_thb": "CLOSE_USDTHB",
                "news_overall_sentiment": "news_sentiment", "open": "Mock_HSH_Sell_Open",
                "high": "Mock_HSH_Sell_High", "low": "Mock_HSH_Sell_Low",
            })
        else:
            df = df.rename(columns={
                "close": "Mock_HSH_Sell_Close", "open": "Mock_HSH_Sell_Open",
                "high": "Mock_HSH_Sell_High", "low": "Mock_HSH_Sell_Low",
            })

        df = df.loc[:, ~df.columns.duplicated()].copy()

        if self.start_date and self.end_date:
            start_ts = pd.to_datetime(self.start_date)
            end_ts = pd.to_datetime(self.end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            df_tz = df["timestamp"].dt.tz
            if df_tz is not None:
                start_ts = start_ts.tz_localize("UTC").tz_convert(df_tz)
                end_ts = end_ts.tz_localize("UTC").tz_convert(df_tz)
            df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)].reset_index(drop=True)
            logger.info(f"📅 [Data Filter] Train/Test Mode: {self.start_date} ถึง {self.end_date}")
        else:
            safe_days = self.days if self.days is not None else 7 
            cutoff = df["timestamp"].max() - pd.Timedelta(days=safe_days)
            df = df[df["timestamp"] >= cutoff].reset_index(drop=True)
            logger.info(f"📅 [Data Filter] Recent Mode: ย้อนหลัง {safe_days} วันล่าสุด")

        if df.empty:
            raise ValueError("❌ ไม่พบข้อมูลในช่วงเวลาที่กำหนด")

        is_merged_file = "merged" in str(self.gold_csv).lower()
        if self.timeframe == "5m" or is_merged_file:
            self.raw_df = self.agg_df = df.copy()
            return

        freq_map = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1D"}
        freq = freq_map.get(self.timeframe, "1h")
        agg_rules = {
            "open_thai": "first", "high_thai": "max", "low_thai": "min", "close_thai": "last",
            "volume": "sum", "rsi": "last", "macd_line": "last", "signal_line": "last",
            "macd_hist": "last", "ema_20": "last", "ema_50": "last", "bb_upper": "last",
            "bb_lower": "last", "bb_mid": "last", "atr": "last", "CLOSE_XAUUSD": "last",
            "CLOSE_USDTHB": "last", "SPREAD_XAUUSD": "last", "SPREAD_USDTHB": "last",
            "Mock_HSH_Buy_Close": "last", "Mock_HSH_Sell_Close": "last", "premium_buy": "last",
            "premium_sell": "last", "pred_premium_buy": "last", "pred_premium_sell": "last",
        }
        valid_rules = {k: v for k, v in agg_rules.items() if k in df.columns}
        df.set_index("timestamp", inplace=True)
        agg = df.resample(freq).agg(valid_rules).dropna(subset=["Mock_HSH_Sell_Close"]).reset_index()
        self.raw_df = df.reset_index()
        self.agg_df = agg

    def _load_main_components(self):
        if self._react is not None:
            return
        from agent_core.core.prompt import SkillRegistry, RoleRegistry, PromptBuilder, AIRole
        from agent_core.core.react import ReactOrchestrator, ReactConfig
        from agent_core.core.risk import RiskManager

        _src_root = Path(__file__).parent.parent
        skill_registry = SkillRegistry()
        skills_path = _src_root / "agent_core/config/skills.json"
        if skills_path.exists():
            skill_registry.load_from_json(str(skills_path))

        role_registry = RoleRegistry(skill_registry)
        roles_path = _src_root / "agent_core/config/roles.json"
        if roles_path.exists():
            role_registry.load_from_json(str(roles_path))

        trading_role = AIRole.ANALYST
        if not role_registry.get(trading_role):
            registered = list(role_registry.roles.keys())
            if not registered:
                raise ValueError("ไม่มี role ใดถูก register — ตรวจสอบ roles.json")
            trading_role = registered[0]

        self.risk_manager = RiskManager()
        self._react = ReactOrchestrator(
            llm_client=self.llm_client,
            prompt_builder=PromptBuilder(role_registry, trading_role),
            tool_registry={}, config=ReactConfig(max_iterations=self.react_max_iter),
            risk_manager=self.risk_manager,
        )
        self._risk_manager = self.risk_manager

    def _run_candle(self, row: pd.Series, session_info=None, is_golden_setup: bool = False) -> dict:
        ts = pd.Timestamp(row["timestamp"])
        if session_info is None:
            session_info = self.session_manager.process_candle(ts)

        price = float(row["Mock_HSH_Sell_Close"]) 
        current_bid = float(row.get("Mock_HSH_Buy_Close", row.get("Buy", price))) 
        
        atr_val = float(row.get("atr", 110.0))
        trailing_dist = max(110.0, atr_val * 1.0)
        self.portfolio.update_trailing_stop(current_bid, trailing_dist)

        exit_reason = self.portfolio.check_auto_exit(current_bid)

        if exit_reason and session_info.can_execute:
            return {
                "timestamp": str(ts), "close_thai": price,
                "llm_signal": f"AUTO_{exit_reason}", "llm_confidence": 1.0,
                "llm_rationale": f"System forced execution: Hit {exit_reason} at {current_bid}",
                "final_signal": "SELL", "final_confidence": 1.0,
                "rejection_reason": f"Auto-closed by {exit_reason}",
                "position_size_thb": 0.0, "stop_loss": 0.0, "take_profit": 0.0,
                "iterations_used": 0, "news_sentiment": float(row.get("news_sentiment", 0.0)),
                "from_cache": False, "session_id": session_info.session_id,
                "can_execute": session_info.can_execute,
            }
            
        if not session_info.can_execute:
            return {
                "timestamp": str(ts), "close_thai": price, "llm_signal": "HOLD",
                "llm_confidence": 1.0, "llm_rationale": "Market is closed (Dead Zone). Sleeping...",
                "final_signal": "HOLD", "final_confidence": 1.0,
                "rejection_reason": "Outside trading hours", "position_size_thb": 0.0,
                "stop_loss": 0.0, "take_profit": 0.0, "iterations_used": 0,
                "news_sentiment": float(row.get("news_sentiment", 0.0)), "from_cache": False,
                "session_id": session_info.session_id, "can_execute": False,
            }

        cached = self.cache.get(ts)
        if cached:
            cached["session_id"] = session_info.session_id
            cached["can_execute"] = session_info.can_execute
            return {**cached, "from_cache": True}

        news = self.news_provider.get(ts)
        today_str = ts.strftime("%Y-%m-%d")
        if getattr(self, "_last_reset_date", None) != today_str:
            self.portfolio.reset_daily(today_str)
            self._last_reset_date = today_str
            
        past_5 = self.agg_df[self.agg_df["timestamp"] <= ts].tail(5)
        market_state = MarketStateBuilder.build(
            row=row, past_5_rows=past_5, current_time=ts,
            portfolio_dict=self.portfolio.to_market_state_dict(price),
            news_data=news, interval=self.timeframe,
        )

        market_state["time"] = ts.strftime("%H:%M")
        market_state["date"] = ts.strftime("%Y-%m-%d")

        quota_ctx = self.session_manager.get_session_quota_context(ts)
        base_directive = DirectiveBuilder.build_session_directive(
            portfolio=self.portfolio, quota_ctx=quota_ctx
        )

        if is_golden_setup:
            sniper_prompt = (
                "\n\n⚡ [SNIPER MODE ACTIVATED - GOLDEN SETUP DETECTED] ⚡\n"
                "This specific candle was mathematically pre-scanned and identified as the "
                "'DEEPEST PRICE DIP' of the current trading session against a 5-candle rolling high.\n"
                "- IMPORTANT: Do NOT automatically output HOLD just because the short-term trend looks bearish or price is dropping. Catching this specific dip is the core strategy.\n"
                "- Your task: Analyze if this dip has underlying support (e.g., near EMA/Bollinger Lower Band, RSI oversold, support level) to justify a CONTRARIAN BUY.\n"
                "- You are allowed to BUY here even if momentum looks red, as long as risk/reward ratio is acceptable. Only reject (HOLD) if there is a severe fundamental reason (e.g., extremely bad news) or if technical indicators are completely broken (not just 'dropping')."
            )
            market_state["backtest_directive"] = base_directive + sniper_prompt
            market_state["is_golden_setup"] = True 
        else:
            market_state["backtest_directive"] = base_directive

        try:
            result = self._react.run(market_state)
        except Exception as e:
            logger.error(f"  ✗ React error at {ts}: {e}")
            result = {
                "final_decision": {"signal": "HOLD", "confidence": 0.5, "rationale": f"error: {e}",
                                   "rejection_reason": str(e), "position_size_thb": 0.0,
                                   "stop_loss": 0.0, "take_profit": 0.0},
                "react_trace": [], "iterations_used": 0,
            }

        fd = result.get("final_decision", {})
        trace = result.get("react_trace", [])
        llm_signal, llm_confidence, llm_rationale = "HOLD", 0.5, ""
        for step in reversed(trace):
            resp = step.get("response", {})
            if isinstance(resp, dict) and "signal" in resp:
                llm_signal = resp.get("signal", "HOLD")
                llm_confidence = float(resp.get("confidence", 0.5))
                llm_rationale = resp.get("rationale") or ""
                break

        candle_result = {
            "timestamp": str(ts), "close_thai": price, "llm_signal": llm_signal,
            "llm_confidence": llm_confidence, "llm_rationale": llm_rationale[:200],
            "final_signal": fd.get("signal", "HOLD"),
            "final_confidence": fd.get("confidence", llm_confidence),
            "rejection_reason": fd.get("rejection_reason"),
            "position_size_thb": fd.get("position_size_thb", 0.0),
            "stop_loss": fd.get("stop_loss", 0.0), "take_profit": fd.get("take_profit", 0.0),
            "iterations_used": result.get("iterations_used", 1),
            "news_sentiment": news.get("overall_sentiment", 0.0) if news else 0.0,
            "from_cache": False, "session_id": session_info.session_id,
            "can_execute": session_info.can_execute,
        }
        self.cache.set(ts, candle_result)
        return candle_result

    def _apply_to_portfolio(self, candle_result: dict, timestamp: str = ""):
        signal = candle_result["final_signal"]
        price = candle_result["close_thai"]
        pos_size = candle_result["position_size_thb"]
        can_execute = candle_result.get("can_execute", True)

        if not can_execute:
            return

        if signal == "BUY":
            if pos_size <= 0:
                pos_size = round(self.portfolio.cash_balance * 0.6, 2)
            ok = self.portfolio.execute_buy(price, pos_size, timestamp=timestamp)
            if ok:
                _tp = float(candle_result.get("take_profit", 0.0) or 0.0)
                _sl = float(candle_result.get("stop_loss", 0.0) or 0.0)
                self.portfolio.set_open_tp_sl(_tp, _sl)
                self.session_manager.record_trade(pd.Timestamp(timestamp))
        elif signal == "SELL":
            ok = self.portfolio.execute_sell(price, timestamp=timestamp)
            if ok:
                self.session_manager.record_trade(pd.Timestamp(timestamp))
                _pnl = float(getattr(self.portfolio, "last_trade_pnl", 0.0) or 0.0)
                self._risk_manager.record_trade_result(_pnl, pd.Timestamp(timestamp).strftime("%Y-%m-%d"))

    def _find_best_dip_per_session(self) -> set:
        df = self.agg_df.copy()
        if "session_id" not in df.columns:
            df["session_id"] = df["timestamp"].apply(lambda ts: self.session_manager.process_candle(pd.Timestamp(ts)).session_id)
            df["_can_execute"] = df["timestamp"].apply(lambda ts: self.session_manager.process_candle(pd.Timestamp(ts)).can_execute)
            self.session_manager = TradingSessionManager()
        else:
            df["_can_execute"] = df.get("can_execute", True)

        df = df[df["_can_execute"] == True].copy()
        if df.empty:
            return set()

        df["_rolling_high"] = df["Mock_HSH_Sell_Close"].rolling(window=5, min_periods=1).max()
        df["_dip_score"] = df["Mock_HSH_Sell_Close"] / df["_rolling_high"]

        if "atr" in df.columns:
            atr_avg = df["atr"].mean() or 110.0
            min_drop = atr_avg * 0.3
            df["_price_drop_abs"] = df["_rolling_high"] - df["Mock_HSH_Sell_Close"]
            df = df[df["_price_drop_abs"] >= min_drop].copy()
            if df.empty:
                df = self.agg_df.copy()
                df["_rolling_high"] = df["Mock_HSH_Sell_Close"].rolling(window=5, min_periods=1).max()
                df["_dip_score"] = df["Mock_HSH_Sell_Close"] / df["_rolling_high"]
                if "session_id" not in df.columns: df["session_id"] = None
                if "_can_execute" not in df.columns: df["_can_execute"] = True

        df["_date"] = df["timestamp"].dt.date
        group_key = ["_date", "session_id"] if "session_id" in df.columns and not df["session_id"].isna().all() else "_date"
        
        best_indices: set = set()
        for _, group in df.groupby(group_key):
            if not group.empty:
                best_indices.add(group["_dip_score"].idxmin())
        return best_indices

    def run(self):
        if self.agg_df is None:
            self.load_and_aggregate()
        self._load_main_components()

        golden_indices = self._find_best_dip_per_session()
        total = len(self.agg_df)
        
        period_str = f"{self.start_date} → {self.end_date}" if (self.start_date and self.end_date) else f"{self.days or 7}d"
        logger.info(f"\n{'=' * 60}\nStarting backtest: {total} candles | {self.timeframe} | {period_str}\n{'=' * 60}")

        for idx, row in self.agg_df.iterrows():
            self.timer.tick_start()
            ts = row["timestamp"]
            session_info = self.session_manager.process_candle(ts)

            if golden_indices and idx not in golden_indices:
                self.results.append({
                    "timestamp": str(ts), "close_thai": float(row["Mock_HSH_Sell_Close"]),
                    "llm_signal": "HOLD", "llm_confidence": 1.0,
                    "llm_rationale": "Pre-filter: ไม่ใช่ Golden Setup ของ session นี้",
                    "final_signal": "HOLD", "final_confidence": 1.0,
                    "rejection_reason": "Not best dip in session", "position_size_thb": 0.0,
                    "stop_loss": 0.0, "take_profit": 0.0, "iterations_used": 0,
                    "news_sentiment": float(row.get("news_sentiment", 0.0)), "from_cache": False,
                    "session_id": session_info.session_id, "can_execute": session_info.can_execute,
                    "portfolio_total_value": round(float(self.portfolio.total_value(float(row["Mock_HSH_Sell_Close"]))), 2),
                    "portfolio_cash": round(float(self.portfolio.cash_balance), 2),
                    "portfolio_gold_grams": round(float(self.portfolio.gold_grams), 4),
                })
                self.timer.tick_end(idx + 1, total, from_cache=True)
                continue

            result = self._run_candle(row, session_info, is_golden_setup=True)
            try:
                self._apply_to_portfolio(result, timestamp=str(ts))
            except PortfolioBustException as bust:
                logger.error(f"\n{'=' * 60}\n🔴 PORTFOLIO BUST at candle [{idx + 1}/{total}]\n{str(bust)}\n{'=' * 60}\n")
                result["bust"] = True
                result["portfolio_total_value"] = round(self.portfolio.bust_equity or 0, 2)
                self.results.append(result)
                break

            result["portfolio_total_value"] = round(float(self.portfolio.total_value(result["close_thai"])), 2)
            result["portfolio_cash"] = round(float(self.portfolio.cash_balance), 2)
            result["portfolio_gold_grams"] = round(float(self.portfolio.gold_grams), 4)
            self.results.append(result)

            cache_tag = "[CACHE]" if result["from_cache"] else ""
            logger.info(f"  [{idx + 1}/{total}] {ts} | LLM={result['llm_signal']}({result['llm_confidence']:.2f}) → FINAL={result['final_signal']} {'[REJECTED]' if result['rejection_reason'] else ''} {cache_tag} | Equity={result['portfolio_total_value']:.0f}")
            self.timer.tick_end(idx + 1, total, result["from_cache"])

        self.session_manager.finalize()
        self._add_validation()

    def _add_validation(self):
        df = pd.DataFrame(self.results)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["next_close"] = df["close_thai"].shift(-1)
        df["price_change"] = df["next_close"] - df["close_thai"]
        df["actual_direction"] = df["price_change"].apply(lambda x: "UP" if x > 0 else ("DOWN" if x < 0 else "FLAT"))
        df["net_pnl_thb"] = df["price_change"] - SPREAD_THB - COMMISSION_THB

        for col_prefix in ["llm", "final"]:
            sig_col = f"{col_prefix}_signal"
            corr_col = f"{col_prefix}_correct"
            prof_col = f"{col_prefix}_profitable"
            df[corr_col] = df.apply(lambda r: _signal_correct(r[sig_col], r["actual_direction"]), axis=1)
            df[prof_col] = df[corr_col] & (df["net_pnl_thb"] > 0)
        self.result_df = df

    def calculate_metrics(self) -> dict:
        evaluator = BacktestEvaluator(timeframe=self.timeframe, days=self.days, portfolio=self.portfolio, session_manager=self.session_manager)
        self.metrics = evaluator.calculate_all(self.result_df)
        return self.metrics

    def export_csv(self, filename: str = None) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        if filename is None:
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            _model_name = getattr(self.llm_client, "model", getattr(self.llm_client, "PROVIDER_NAME", "unknown"))
            model_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", _model_name)
            filename = f"main_{model_slug}_{self.timeframe}_{self.days}d_{ts_str}.csv"

        path = os.path.join(self.output_dir, filename)
        df = self.result_df.copy()
        export_cols = [c for c in ["timestamp", "close_thai", "portfolio_total_value", "portfolio_cash", "portfolio_gold_grams", "actual_direction", "price_change", "net_pnl_thb", "news_sentiment", "llm_signal", "llm_confidence", "llm_rationale", "llm_correct", "llm_profitable", "final_signal", "final_confidence", "final_correct", "final_profitable", "rejection_reason", "position_size_thb", "stop_loss", "take_profit", "iterations_used", "from_cache", "session_id", "can_execute"] if c in df.columns]

        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(f"=== MAIN PIPELINE BACKTEST ===\n")
            if hasattr(self, "metrics"):
                for name, m in self.metrics.items():
                    if isinstance(m, dict):
                        for k, v in m.items(): f.write(f"{name}_{k},{v}\n")
            f.write("\n=== DETAILED SIGNAL LOG ===\n")
            df[export_cols].to_csv(f, index=False)
        return path

def _signal_correct(signal: str, actual: str) -> bool:
    return (signal == "HOLD" and actual == "FLAT") or (signal == "BUY" and actual == "UP") or (signal == "SELL" and actual == "DOWN")

def run_main_backtest(gold_csv: str, news_csv: str = "", external_csv: str = "", timeframe: str = "1h", days: int = 30, start_date: str = None, end_date: str = None, provider: str = "gemini", model: str = "", cache_dir: str = DEFAULT_CACHE_DIR, output_dir: str = DEFAULT_OUTPUT_DIR, react_max_iter: int = 5) -> dict:
    bt = MainPipelineBacktest(gold_csv=gold_csv, news_csv=news_csv, external_csv=external_csv, provider=provider, model=model, timeframe=timeframe, days=days, start_date=start_date, end_date=end_date, cache_dir=cache_dir, output_dir=output_dir, react_max_iter=react_max_iter)
    bt.run()
    metrics = bt.calculate_metrics()
    bt.export_csv()
    gate = deploy_gate(metrics)
    print_gate_report(gate)
    metrics["deploy_gate"] = gate
    return metrics

def main():
    import argparse, yaml
    from dotenv import load_dotenv
    _env_path = None
    for _parent in [Path(__file__).parent, Path(__file__).parent.parent, Path(__file__).parent.parent.parent]:
        _candidate = _parent / ".env"
        if _candidate.exists(): _env_path = _candidate; break
    load_dotenv(dotenv_path=_env_path, override=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)], force=True)
    config = load_config("config/config.yaml")
    cfg_start = cfg_end = None
    try:
        with open("config/config.yaml", "r", encoding="utf-8") as f:
            raw_yaml = yaml.safe_load(f)
            cfg_start = raw_yaml.get("backtest", {}).get("start_date")
            cfg_end = raw_yaml.get("backtest", {}).get("end_date")
    except Exception: pass

    parser = argparse.ArgumentParser(description="Main Pipeline Backtest")
    parser.add_argument("--days", type=int, default=config.days)
    parser.add_argument("--timeframe", default=config.timeframe)
    parser.add_argument("--start_date", type=str, default=cfg_start)
    parser.add_argument("--end_date", type=str, default=cfg_end)
    args = parser.parse_args()
    
    mode_text = f"{args.start_date} to {args.end_date}" if (args.start_date and args.end_date) else f"{args.days or 7} Days"
    print("=" * 65); print(f"  MAIN PIPELINE BACKTEST — {config.provider} / {args.timeframe} / {mode_text}"); print("=" * 65)
    try:
        run_main_backtest(gold_csv=config.gold_csv, news_csv=config.news_csv, external_csv=config.external_csv, timeframe=args.timeframe, days=args.days, start_date=args.start_date, end_date=args.end_date, provider=config.provider, model=config.model, cache_dir=config.cache_dir, output_dir=config.output_dir, react_max_iter=config.react_max_iter)
    except Exception as e:
        logging.exception(f"✗ Fatal error: {e}"); sys.exit(1)

if __name__ == "__main__":
    main()