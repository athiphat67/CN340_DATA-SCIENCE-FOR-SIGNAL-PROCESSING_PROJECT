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
import pprint
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
import pandas as pd
import numpy as np
from data.csv_loader import load_gold_csv
from engine.market_state_builder import MarketStateBuilder
from engine.news_provider import (
    NewsProvider, NullNewsProvider, create_news_provider
)
from engine.session_manager import TradingSessionManager
from engine.portfolio import (
    SimPortfolio, PortfolioBustException,
    DEFAULT_CASH, BUST_THRESHOLD, WIN_THRESHOLD,
    SPREAD_THB, COMMISSION_THB, GOLD_GRAM_PER_BAHT,
)
from metrics.calculator import calculate_trade_metrics, add_calmar
from metrics.deploy_gate import deploy_gate, print_gate_report

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

# NOTE: GOLD_GRAM_PER_BAHT, SPREAD_THB, COMMISSION_THB, DEFAULT_CASH
#       imported จาก backtest.engine.portfolio — ห้าม redefine ที่นี่
DEFAULT_CACHE_DIR  = "backtest_cache_main"
DEFAULT_OUTPUT_DIR = "backtest_results_main"
MIN_CONFIDENCE     = 0.6

# ★ [B-helper] จำนวน candle ต่อปี (gold ~24/5 ~252 วัน)
_PERIODS_PER_YEAR: Dict[str, int] = {
    "1m":  362_880,
    "5m":   72_576,
    "15m":  24_192,
    "30m":  12_096,
    "1h":    6_048,
    "4h":    1_512,
    "1d":      252,
}


# ══════════════════════════════════════════════════════════════════
# Time Estimator
# ══════════════════════════════════════════════════════════════════


class TimeEstimator:
    """คาดเดาเวลาที่เหลือจาก rolling average ของ candle ที่ผ่านมา"""

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
        return (
            f"  ⏱ {speed}/candle | "
            f"elapsed={se_h:02d}:{se_m:02d}:{se_s:02d} | "
            f"ETA={r_h:02d}:{r_m:02d}:{r_s:02d} | "
            f"avg={avg:.1f}s"
        )


# ══════════════════════════════════════════════════════════════════
# Ollama Client
# ══════════════════════════════════════════════════════════════════


@dataclass
class _LLMResponse:
    """
    Local LLMResponse — interface เดียวกับ agent_core LLMResponse
    Bug D fix: ReactOrchestrator ทำ llm_resp.text → ต้องคืน object ที่มี .text
    """
    text:         str
    prompt_text:  str = ""
    token_input:  int = 0
    token_output: int = 0
    token_total:  int = 0
    model:        str = ""
    provider:     str = ""


class OllamaClient:
    """Ollama local client — call() คืน _LLMResponse (ไม่ใช่ str) Bug D fixed"""

    PROVIDER_NAME = "ollama"

    def __init__(
        self,
        model: str = "qwen3.5:9b",
        base_url: str = "http://localhost:11434",
        timeout: int = 600,
    ):
        self.model    = model
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self._think_re = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

    def call(self, prompt_package) -> _LLMResponse:
        """คืน _LLMResponse (มี .text) — Bug D fix"""
        system = getattr(prompt_package, "system", "")
        user   = getattr(prompt_package, "user", "") or getattr(
            prompt_package, "user_message", ""
        )
        payload = {
            "model": self.model,
            "think": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream": False,
        }
        resp = requests.post(
            f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        data  = resp.json()
        raw   = data["message"]["content"]
        clean = self._think_re.sub("", raw).strip()

        prompt_tokens     = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        logger.info(
            f"🪙 Token Usage -> Input: {prompt_tokens} | "
            f"Output: {completion_tokens} | Total: {prompt_tokens + completion_tokens}"
        )
        return _LLMResponse(
            text         = clean,
            prompt_text  = f"SYSTEM:\n{system}\n\nUSER:\n{user}",
            token_input  = prompt_tokens,
            token_output = completion_tokens,
            token_total  = prompt_tokens + completion_tokens,
            model        = self.model,
            provider     = self.PROVIDER_NAME,
        )

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False


# ── Provider defaults (ตรงกับ provider_adapter.py) ─────────────────
_PROVIDER_MODEL_DEFAULTS: dict = {
    # "gemini":  "gemini-3.1-flash-lite-preview",
    "gemini":"gemini-2.5-flash-lite",
    "groq":    "llama-3.3-70b-versatile",
    "openai":  "gpt-4o-mini",
    "claude":  "claude-opus-4-1",
    "ollama":  "qwen3.5:9b",
}


def _create_llm_client(
    provider: str,
    model: str        = "",
    ollama_model: str = "qwen3.5:9b",
    ollama_url: str   = "http://localhost:11434",
) -> object:
    """
    Factory สร้าง LLM client ที่คืน LLMResponse-compatible object
    ไม่ import จาก provider_adapter (หลีกเลี่ยง circular import)

    - ollama  → OllamaClient local (Bug D fixed)
    - others  → LLMClientFactory จาก agent_core (production path)
    """
    provider = provider.lower().strip()

    if provider == "ollama":
        return OllamaClient(
            model    = model or ollama_model,
            base_url = ollama_url,
        )

    # Non-ollama: ใช้ production LLMClientFactory
    try:
        from agent_core.llm.client import LLMClientFactory
        resolved_model = model or _PROVIDER_MODEL_DEFAULTS.get(provider, "")
        kwargs = {"model": resolved_model} if resolved_model else {}
        client = LLMClientFactory.create(provider, **kwargs)
        logger.info(
            f"✓ LLMClient: {provider} via LLMClientFactory "
            f"(model={getattr(client, 'model', '?')})"
        )
        return client
    except ImportError:
        raise ImportError(
            f"agent_core ไม่พบ — provider='{provider}' ต้องใช้ LLMClientFactory\n"
            "  ตรวจสอบว่า agent_core/ อยู่ใน sys.path หรือใช้ --provider ollama"
        )

# ══════════════════════════════════════════════════════════════════
# Cache Layer
# ══════════════════════════════════════════════════════════════════


class CandleCache:
    def __init__(self, cache_dir: str, model: str):
        self.dir  = Path(cache_dir)
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
            "hits":     self._hits,
            "misses":   self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }

# ══════════════════════════════════════════════════════════════════
# Main Backtest Class
# ══════════════════════════════════════════════════════════════════


class MainPipelineBacktest:

    def __init__(
        self,
        gold_csv: str,
        news_provider: NewsProvider = None,
        news_csv: str          = "",
        external_csv: str      = "",   # CSV ที่มี gold_spot_usd, usd_thb_rate (optional)
        provider: str          = "ollama",
        model: str             = "",
        ollama_model: str      = "qwen3.5:9b",
        ollama_url: str        = "http://localhost:11434",
        timeframe: str         = "1h",
        days: int              = 30,
        cache_dir: str         = DEFAULT_CACHE_DIR,
        output_dir: str        = DEFAULT_OUTPUT_DIR,
        react_max_iter: int    = 5,
        request_delay: float   = 0.3,
    ):
        self.gold_csv       = gold_csv
        self.external_csv   = external_csv
        self.timeframe      = timeframe
        self.days           = days
        self.output_dir     = output_dir
        self.react_max_iter = react_max_iter
        self.request_delay  = request_delay

        # ── LLM Client (Bug D fixed: คืน _LLMResponse ไม่ใช่ str) ──────────
        self.ollama = _create_llm_client(
            provider=provider, model=model,
            ollama_model=ollama_model, ollama_url=ollama_url,
        )
        # Bug fix: cache slug ต้องสะท้อน provider จริง ไม่ใช่ ollama_model เสมอ
        if provider == "ollama":
            _model_slug = model or ollama_model
        else:
            _model_slug = model or _PROVIDER_MODEL_DEFAULTS.get(provider, provider)
        self.cache       = CandleCache(cache_dir=cache_dir, model=_model_slug)
        self.timer       = TimeEstimator()

        self.raw_df: Optional[pd.DataFrame]  = None
        self.agg_df: Optional[pd.DataFrame]  = None
        self.result_df: Optional[pd.DataFrame] = None
        self.results: List[dict]              = []
        self.metrics: dict                    = {}

        self._prompt_builder = None
        self._react          = None
        self._risk_mgr       = None

        # Session Engine — Phase 2
        self.session_manager = TradingSessionManager()
        
        # News provider — backward compat: ถ้าส่ง news_csv มา ใช้ CSV mode
        if news_provider is not None:
            self.news_provider = news_provider
        elif news_csv:
            self.news_provider = create_news_provider("csv", csv_path=news_csv)
        else:
            self.news_provider = NullNewsProvider()

        # SimPortfolio v2 — ใหม่
        self.portfolio = SimPortfolio(
            initial_cash=DEFAULT_CASH,
            bust_threshold=BUST_THRESHOLD,
            win_threshold=WIN_THRESHOLD,   # Bug B fix: WIN_THRESHOLD ไม่ใช่ DEFAULT_CASH
        )

    # ── External data merge (spot USD, USDTHB) ─────────────────

    def _merge_external_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge external CSV (gold_spot_usd, usd_thb_rate) เข้า df หลัก
        ใช้ pd.merge_asof — nearest timestamp backward ป้องกัน look-ahead

        CSV format ที่รองรับ (column names flexible):
          timestamp | gold_spot_usd | usd_thb_rate
          หรือ: datetime | xau_usd | usdthb
          หรือ: datetime | spot | thb
        """
        if not self.external_csv:
            return df

        from pathlib import Path as _Path
        if not _Path(self.external_csv).exists():
            logger.warning(f"⚠ external_csv ไม่พบ: {self.external_csv} → ข้าม")
            return df

        try:
            ext = pd.read_csv(self.external_csv, encoding="utf-8-sig")
            ext.columns = ext.columns.str.strip().str.lower()

            # หา timestamp column
            ts_candidates = ["timestamp", "datetime", "time", "date"]
            ts_col = next((c for c in ts_candidates if c in ext.columns), None)
            if ts_col is None:
                logger.warning("⚠ external_csv ไม่มี timestamp column → ข้าม")
                return df
            ext["timestamp"] = pd.to_datetime(ext[ts_col], errors="coerce")
            ext = ext.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

            # map column aliases → ชื่อมาตรฐาน
            _alias = {
                "gold_spot_usd": ["gold_spot_usd", "xau_usd", "xauusd", "spot_usd", "spot", "price_usd"],
                "usd_thb_rate":  ["usd_thb_rate", "usdthb", "usd_thb", "thb", "thbrate"],
            }
            rename_map = {}
            for std_name, aliases in _alias.items():
                for a in aliases:
                    if a in ext.columns and std_name not in ext.columns:
                        rename_map[a] = std_name
                        break
            if rename_map:
                ext = ext.rename(columns=rename_map)

            merge_cols = [c for c in ["gold_spot_usd", "usd_thb_rate"] if c in ext.columns]
            if not merge_cols:
                logger.warning("⚠ external_csv ไม่มี gold_spot_usd หรือ usd_thb_rate → ข้าม")
                return df

            ext_slim = ext[["timestamp"] + merge_cols].copy()

            # merge_asof: backward = ใช้ข้อมูลล่าสุดที่ <= candle timestamp (ไม่มี look-ahead)
            df_sorted = df.sort_values("timestamp").reset_index(drop=True)
            merged = pd.merge_asof(
                df_sorted,
                ext_slim,
                on="timestamp",
                direction="backward",
                tolerance=pd.Timedelta(hours=4),   # ถ้าห่างเกิน 4h → NaN
            )
            # fill NaN ด้วย 0.0 (build_market_state รับ 0.0 ได้)
            for c in merge_cols:
                merged[c] = merged[c].fillna(0.0)

            logger.info(
                f"✓ Merged external data: {merge_cols} | "
                f"rows={len(merged)} | "
                f"non-zero spot={( merged.get('gold_spot_usd', pd.Series([0])) > 0).sum()}"
            )
            return merged

        except Exception as e:
            logger.error(f"✗ _merge_external_data failed: {e} → ใช้ 0.0 แทน")
            return df

    # ── Load & aggregate data ───────────────────────────────────

    def load_and_aggregate(self):
        df = load_gold_csv(self.gold_csv, external_csv=self.external_csv or None)

        # csv_loader ใช้ close/open/high/low/macd_signal → rename ให้ตรงกับที่ใช้ใน backtest
        df = df.rename(columns={
            "close":       "close_thai",
            "open":        "open_thai",
            "high":        "high_thai",
            "low":         "low_thai",
            "macd_signal": "signal_line",
        })

        cutoff = df["timestamp"].max() - pd.Timedelta(days=self.days)
        df = df[df["timestamp"] >= cutoff].reset_index(drop=True)

        if self.timeframe == "5m":
            self.raw_df = self.agg_df = df.copy()
            logger.info(f"✓ Data ready: {len(df):,} candles (5m)")
            return

        freq_map = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1D"}
        freq = freq_map.get(self.timeframe, "1h")

        agg_rules = {
            "open_thai": "first", "high_thai": "max",
            "low_thai": "min",    "close_thai": "last",
            "volume": "sum",
            "rsi": "last",        "macd_line": "last",
            "signal_line": "last","macd_hist": "last",
            "ema_20": "last",     "ema_50": "last",
            "bb_upper": "last",   "bb_lower": "last",
            "bb_mid": "last",     "atr": "last",
            "CLOSE_XAUUSD": "last", "CLOSE_USDTHB": "last",
            "SPREAD_XAUUSD": "last","SPREAD_USDTHB": "last",
            "Mock_HSH_Buy_Close": "last", "Mock_HSH_Sell_Close": "last",
            "premium_buy": "last","premium_sell": "last",
            "pred_premium_buy": "last", "pred_premium_sell": "last",
        }
        valid_rules = {k: v for k, v in agg_rules.items() if k in df.columns}
        df.set_index("timestamp", inplace=True)
        agg = df.resample(freq).agg(valid_rules).dropna(subset=["close_thai"]).reset_index()
        self.raw_df = df.reset_index()
        self.agg_df = agg
        logger.info(f"✓ Data ready: {len(agg):,} candles ({self.timeframe})")
 

    # ── Load main components ────────────────────────────────────
    

   # ── Main system components ─────────────────────────────────

    def _load_main_components(self):
        """Import และ init ReactOrchestrator + PromptBuilder + RiskManager จาก main"""
        if self._react is not None:
            return

        try:
            import json
            from agent_core.core.prompt import (
                PromptBuilder,
                RoleRegistry,
                SkillRegistry,
                Skill,
                AIRole,
                RoleDefinition,
            )
            from agent_core.core.react import ReactOrchestrator, ReactConfig
            from agent_core.core.risk import RiskManager

            # ── Load skills.json ────────────────────────────────────
            skill_registry = SkillRegistry()
            # __file__ = Src/backtest/run_main_backtest.py → .parent.parent = Src/
            _src_root   = Path(__file__).parent.parent
            skills_path = _src_root / "agent_core/config/skills.json"
            if skills_path.exists():
                with open(skills_path, "r", encoding="utf-8") as f:
                    skills_config = json.load(f)
                    for skill_name, skill_data in skills_config.items():
                        # สร้าง Skill object แล้ว register
                        # รองรับกรณีที่ skill_data เป็น list หรือ dict
                        if isinstance(skill_data, list):
                            skill = Skill(
                                name=skill_name,
                                description="",
                                tools=skill_data,
                                constraints=None,
                            )
                        else:
                            skill = Skill(
                                name=skill_name,
                                description=skill_data.get("description", ""),
                                tools=skill_data.get("tools", []),
                                constraints=skill_data.get("constraints", None),
                            )
                        skill_registry.register(skill)
                logger.info(f"✓ Loaded {len(skills_config)} skills from {skills_path}")
            else:
                logger.warning(f"skills.json not found at {skills_path}")

            # ── Load roles.json ────────────────────────────────────
            role_registry = RoleRegistry(skill_registry)
            roles_path = _src_root / "agent_core/config/roles.json"
            if roles_path.exists():
                # ✅ Fix 1: ใช้ load_from_json() ที่ handle structure ถูกต้อง
                # roles.json format: {"roles": [{"name": "analyst", ...}]}
                role_registry.load_from_json(str(roles_path))
                logger.info(f"✓ Loaded {len(role_registry.roles)} roles from {roles_path}")
            else:
                logger.warning(f"roles.json not found at {roles_path}")

            # ── เลือก role และ fallback ────────────────────────────
            trading_role = AIRole.ANALYST
            if not role_registry.get(trading_role):
                registered = list(role_registry.roles.keys())
                logger.warning(f"⚠ Role {trading_role} ไม่พบ | registered: {registered}")
                if registered:
                    trading_role = registered[0]
                    logger.info(f"  → fallback to: {trading_role}")
                else:
                    raise ValueError(
                        "ไม่มี role ใดถูก register — ตรวจสอบ roles.json\n"
                        '  Expected format: {"roles": [{"name": "analyst", "title": "...", ...}]}'
                    )

            # ── Create RiskManager ──────────────────────────────────
            risk_manager = RiskManager()

            # ── Create ReactConfig ──────────────────────────────────
            config = ReactConfig(max_iterations=self.react_max_iter)

            # ── Create ReactOrchestrator ────────────────────────────
            tool_registry = {}
            self._react = ReactOrchestrator(
                llm_client=self.ollama,
                # ✅ Fix 2: PromptBuilder(role_registry, current_role)
                # ไม่ใช่ PromptBuilder(skill_registry, role_registry)
                prompt_builder=PromptBuilder(role_registry, trading_role),
                tool_registry=tool_registry,
                config=config,
            )
            self._risk_manager = risk_manager
            logger.info(
                f"✓ Main components loaded | role={trading_role} "
                f"(ReactOrchestrator, PromptBuilder, RiskManager)"
            )

        except ImportError as e:
            raise ImportError(
                f"ไม่พบ agent_core: {e}\n"
                "ตรวจสอบว่า sys.path ชี้ไปที่ Src/ ที่มีโฟลเดอร์ agent_core/"
            ) from e


    # ── Per-candle runner ───────────────────────────────────────

    def _run_candle(self, row: pd.Series) -> dict:
        ts     = pd.Timestamp(row["timestamp"])
        # session check ต้องก่อน cache เสมอ — ทำให้ session tracking ถูกต้องแม้ cache hit
        session_info = self.session_manager.process_candle(ts)
        cached = self.cache.get(ts)
        if cached:
            # inject session_info ใหม่ทุกครั้ง (ไม่เชื่อ cached value ที่อาจ stale)
            cached["session_id"]  = session_info.session_id
            cached["can_execute"] = session_info.can_execute
            return {**cached, "from_cache": True}

        news = self.news_provider.get(ts)
        price = float(row["close_thai"])
        self.portfolio.reset_daily(ts.strftime("%Y-%m-%d"))
        past_5 = self.agg_df[self.agg_df["timestamp"] <= ts].tail(5)
        market_state = MarketStateBuilder.build(
            row=row,
            past_5_rows=past_5,
            current_time=ts,
            portfolio_dict=self.portfolio.to_market_state_dict(price),
            news_data=news,
            interval=self.timeframe,
        )

        try:
            result = self._react.run(market_state)
        except Exception as e:
            logger.error(f"  ✗ React error at {ts}: {e}")
            result = {
                "final_decision": {
                    "signal": "HOLD", "confidence": 0.5,
                    "rationale": f"error: {e}", "rejection_reason": str(e),
                    "position_size_thb": 0.0, "stop_loss": 0.0, "take_profit": 0.0,
                },
                "react_trace": [], "iterations_used": 0,
            }

        fd    = result.get("final_decision", {})
        trace = result.get("react_trace", [])
        llm_signal = "HOLD"; llm_confidence = 0.5; llm_rationale = ""
        for step in reversed(trace):
            resp = step.get("response", {})
            if isinstance(resp, dict) and "signal" in resp:
                llm_signal     = resp.get("signal", "HOLD")
                llm_confidence = float(resp.get("confidence", 0.5))
                llm_rationale  = resp.get("rationale", "")
                break

        # ── Session check ────────────────────────────────────
        candle_result = {
            "timestamp":        str(ts),
            "close_thai":       price,
            "llm_signal":       llm_signal,
            "llm_confidence":   llm_confidence,
            "llm_rationale":    llm_rationale[:200],
            "final_signal":     fd.get("signal", "HOLD"),
            "final_confidence": fd.get("confidence", llm_confidence),
            "rejection_reason": fd.get("rejection_reason"),
            "position_size_thb":fd.get("position_size_thb", 0.0),
            "stop_loss":        fd.get("stop_loss", 0.0),
            "take_profit":      fd.get("take_profit", 0.0),
            "iterations_used":  result.get("iterations_used", 1),
            "news_sentiment":   news.get("overall_sentiment", 0.0),
            "from_cache":       False,
            "session_id":       session_info.session_id,
            "can_execute":      session_info.can_execute,
        }
        self.cache.set(ts, candle_result)
        return candle_result

    def _apply_to_portfolio(self, candle_result: dict, timestamp: str = ""):
        signal      = candle_result["final_signal"]
        price       = candle_result["close_thai"]
        pos_size    = candle_result["position_size_thb"]
        can_execute = candle_result.get("can_execute", True)

        # นอก session → override เป็น HOLD ไม่ execute
        if not can_execute:
            logger.debug(
                f"  [OUT] {timestamp} outside session → HOLD (was {signal})"
            )
            return

        if signal == "BUY":
            # Bug C fix: ถ้า LLM ไม่ set position_size → fallback ใช้ 60% ของ cash
            if pos_size <= 0:
                pos_size = round(self.portfolio.cash_balance * 0.6, 2)
                logger.debug(f"  BUY pos_size=0 → fallback {pos_size:.0f} THB (60% cash)")
            ok = self.portfolio.execute_buy(price, pos_size, timestamp=timestamp)
            if not ok:
                logger.debug(f"  BUY skipped: {self.portfolio.cash_balance:.0f} THB")
            else:
                # บันทึก trade เข้า session compliance
                self.session_manager.record_trade(
                    pd.Timestamp(timestamp), 
                )
        elif signal == "SELL":
            self.portfolio.execute_sell(price, timestamp=timestamp)
            # บันทึก trade เข้า session compliance
            self.session_manager.record_trade(pd.Timestamp(timestamp))
        # PortfolioBustException propagates ขึ้น run() อัตโนมัติ

    # ── Full run ────────────────────────────────────────────────

    def run(self):
        if self.agg_df is None:
            self.load_and_aggregate()
        self._load_main_components()

        total = len(self.agg_df)
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting backtest: {total} candles | {self.timeframe} | {self.days}d")
        logger.info(f"{'='*60}")

        for idx, row in self.agg_df.iterrows():
            self.timer.tick_start()
            ts = row["timestamp"]

            result = self._run_candle(row)
            try:
                self._apply_to_portfolio(result, timestamp=str(ts))
            except PortfolioBustException as bust:
                logger.error(f"\n{'='*60}")
                logger.error(f"🔴 PORTFOLIO BUST at candle [{idx+1}/{total}]")
                logger.error(str(bust))
                logger.error(f"{'='*60}\n")
                result["bust"] = True
                result["portfolio_total_value"] = round(self.portfolio.bust_equity or 0, 2)
                result["portfolio_cash"]        = round(self.portfolio.cash_balance, 2)
                result["portfolio_gold_grams"]  = round(self.portfolio.gold_grams, 4)
                self.results.append(result)
                break

            # ────────────────────────────────────────────────────────────
            port_val = self.portfolio.total_value(result["close_thai"])

            result["portfolio_total_value"] = round(float(port_val), 2)
            result["portfolio_cash"]        = round(float(self.portfolio.cash_balance), 2)
            result["portfolio_gold_grams"]  = round(float(self.portfolio.gold_grams), 4)

            self.results.append(result)

            cache_tag = "[CACHE]" if result["from_cache"] else ""
            eta_str   = self.timer.tick_end(idx + 1, total, result["from_cache"])
            logger.info(
                f"  [{idx+1}/{total}] {ts} | "
                f"LLM={result['llm_signal']}({result['llm_confidence']:.2f}) → "
                f"FINAL={result['final_signal']} "
                f"{'[REJECTED]' if result['rejection_reason'] else ''} "
                f"{'[OUT]' if not result.get('can_execute', True) else result.get('session_id','') or ''} "
                f"{cache_tag} | "
                f"Equity={result['portfolio_total_value']:.0f} THB"
            )
            logger.info(eta_str)

            if not result["from_cache"] and self.request_delay > 0:
                time.sleep(self.request_delay)

        # Session Engine: finalize ปิด session สุดท้าย
        self.session_manager.finalize()
        logger.info(f"\n✓ Backtest complete | cache: {self.cache.stats}")
        self._add_validation()

    def _add_validation(self):
        df = pd.DataFrame(self.results)
        df["timestamp"]  = pd.to_datetime(df["timestamp"])
        df["next_close"] = df["close_thai"].shift(-1)
        df["price_change"]    = df["next_close"] - df["close_thai"]
        df["actual_direction"] = df["price_change"].apply(
            lambda x: "UP" if x > 0 else ("DOWN" if x < 0 else "FLAT")
        )
        df["net_pnl_thb"] = df["price_change"] - SPREAD_THB - COMMISSION_THB

        for col_prefix in ["llm", "final"]:
            sig_col  = f"{col_prefix}_signal"
            corr_col = f"{col_prefix}_correct"
            prof_col = f"{col_prefix}_profitable"
            df[corr_col] = df.apply(
                lambda r: _signal_correct(r[sig_col], r["actual_direction"]), axis=1
            )
            df[prof_col] = df[corr_col] & (df["net_pnl_thb"] > 0)

        self.result_df = df

    # ★ [B] Risk metrics method ────────────────────────────────────────

    def _compute_risk_metrics(self, df: pd.DataFrame) -> dict:
        """
        คำนวณ MDD / Sharpe / Sortino จาก equity curve ใน portfolio_total_value

        สูตร:
          MDD     = max drawdown จาก running peak
          Sharpe  = mean(excess_return) / std(excess_return) * sqrt(ppy)
          Sortino = mean(excess_return) / downside_std * sqrt(ppy)
                    โดย downside_std คำนวณจากเฉพาะ return ที่ต่ำกว่า risk-free
        """
        if "portfolio_total_value" not in df.columns:
            logger.warning("portfolio_total_value column missing — skip risk metrics")
            return {"note": "portfolio_total_value column missing (see patch [A])"}

        equity = df["portfolio_total_value"].astype(float).values
        n      = len(equity)
        if n < 2:
            return {"note": "not enough candles"}

        # annualization factor ตาม timeframe
        ppy           = _PERIODS_PER_YEAR.get(self.timeframe, 6_048)
        rf_per_period = 0.02 / ppy    # risk-free rate 2% ต่อปี

        # ── Total Return ─────────────────────────────────────────────
        initial = equity[0]
        final   = equity[-1]
        total_return = (final - initial) / initial if initial else 0.0

        # ── Per-candle returns ────────────────────────────────────────
        returns = pd.Series(equity).pct_change().dropna()

        # ── Maximum Drawdown ─────────────────────────────────────────
        peak      = pd.Series(equity).cummax()
        drawdown  = (pd.Series(equity) - peak) / peak

        mdd        = float(drawdown.min())              # ค่าลบ เช่น -0.12 = -12%
        trough_idx = int(drawdown.idxmin())

        # หา peak index ก่อน trough — idxmax() หาตำแหน่ง equity สูงสุดก่อนถึง trough
        equity_s = pd.Series(equity)
        peak_idx = int(equity_s.iloc[: trough_idx + 1].idxmax())

        def _get_ts(i: int) -> str:
            try:
                return str(df["timestamp"].iloc[i])
            except Exception:
                return str(i)

        # ── Sharpe Ratio ──────────────────────────────────────────────
        excess = returns - rf_per_period
        sharpe = 0.0
        std_e  = excess.std(ddof=1)
        if std_e > 1e-12:
            sharpe = float((excess.mean() / std_e) * (ppy ** 0.5))

        # ── Sortino Ratio ─────────────────────────────────────────────
        downside = excess[excess < 0]
        sortino  = 0.0
        if len(downside) > 0:
            downside_std = float((downside ** 2).mean() ** 0.5)  # semi-deviation
            if downside_std > 1e-12:
                sortino = float((excess.mean() / downside_std) * (ppy ** 0.5))

        # ── Annualized metrics ────────────────────────────────────────
        ann_return = float((1 + returns.mean()) ** ppy - 1) if n > 1 else 0.0
        volatility = float(returns.std(ddof=1) * (ppy ** 0.5))  if n > 1 else 0.0

        # Warning: annualized extrapolation จาก data สั้นไม่น่าเชื่อถือ
        actual_days = int((df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).days) if "timestamp" in df.columns else self.days
        ann_reliable = actual_days >= 60
        if not ann_reliable:
            logger.warning(
                f"⚠ annualized_return ({ann_return*100:.1f}%) extrapolated จาก {actual_days} วัน "
                f"→ ไม่น่าเชื่อถือ ต้องการอย่างน้อย 60 วัน"
            )

        return {
            "initial_portfolio_thb":     round(initial, 2),
            "final_portfolio_thb":       round(final, 2),
            "total_return_pct":          round(total_return * 100, 2),
            "annualized_return_pct":     round(ann_return * 100, 2),
            "annualized_reliable":       ann_reliable,   # False = extrapolated จาก data < 60 วัน
            "annualized_volatility_pct": round(volatility * 100, 2),
            # ── MDD ──────────────────────────────────────────────────
            "mdd_pct":               round(mdd * 100, 2),   # ลบ = ขาดทุน
            "mdd_peak_timestamp":    _get_ts(peak_idx),
            "mdd_trough_timestamp":  _get_ts(trough_idx),
            # ── Risk-adjusted returns ─────────────────────────────────
            "sharpe_ratio":          round(sharpe, 3),
            "sortino_ratio":         round(sortino, 3),
            # ── Meta ──────────────────────────────────────────────────
            "candles_total":         n,
            "periods_per_year":      ppy,
            "risk_free_rate_pct":    2.0,
        }

    # ── Metrics & export ─────────────────────────────────────────

    def calculate_metrics(self) -> dict:
        df      = self.result_df.copy()
        metrics = {}

        for prefix in ["llm", "final"]:
            active = df[df[f"{prefix}_signal"] != "HOLD"]
            total  = len(active)

            if total == 0:
                metrics[prefix] = {"note": "all HOLD"}
                continue

            correct    = active[f"{prefix}_correct"].sum()
            profitable = active[f"{prefix}_profitable"].sum()
            accuracy   = correct / total * 100
            sensitivity = total / len(df) * 100

            correct_rows = active[active[f"{prefix}_correct"]]
            avg_pnl      = correct_rows["net_pnl_thb"].mean() if len(correct_rows) else 0.0

            buy_count  = (active[f"{prefix}_signal"] == "BUY").sum()
            sell_count = (active[f"{prefix}_signal"] == "SELL").sum()
            rejected   = df["rejection_reason"].notna().sum() if prefix == "final" else 0

            metrics[prefix] = {
                "directional_accuracy_pct": round(accuracy, 2),
                "signal_sensitivity_pct":   round(sensitivity, 2),
                "total_signals":            total,
                "buy_signals":              int(buy_count),
                "sell_signals":             int(sell_count),
                "correct_signals":          int(correct),
                "correct_profitable":       int(profitable),
                "avg_net_pnl_thb":          round(avg_pnl, 2),
                "rejected_by_risk":         int(rejected),
                "avg_confidence":           round(active[f"{prefix}_confidence"].mean(), 3),
            }

        # ★ [C] คำนวณ MDD / Sharpe / Sortino ─────────────────────────
        risk = self._compute_risk_metrics(df)
        metrics["risk"] = risk

        # Phase 2: Session compliance
        compliance = self.session_manager.compliance_report()
        metrics["session_compliance"] = {
            "total_sessions":    compliance["total_sessions"],
            "passed_sessions":   compliance["passed_sessions"],
            "failed_sessions":   compliance["failed_sessions"],
            "no_data_sessions":  compliance["no_data_sessions"],
            "compliance_pct":    compliance["compliance_pct"],
            "session_fail_flag": compliance["session_fail_flag"],
        }

        # Phase 4: Trade-based metrics (Win Rate, Profit Factor, Calmar)
        trade_m = calculate_trade_metrics(self.portfolio.closed_trades)
        trade_m = add_calmar(trade_m, risk)          # เพิ่ม calmar_ratio
        metrics["trade"] = trade_m

        # bust_flag ที่ top-level — deploy_gate ดึงจากนี้
        metrics["bust_flag"] = self.portfolio.bust_flag
        # ────────────────────────────────────────────────────────────

        self.metrics = metrics

        # ── Print summary ─────────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("METRICS SUMMARY")
        logger.info("=" * 60)

        for name, m in metrics.items():
            logger.info(f"\n{name.upper()}:")
            if not isinstance(m, dict):
                logger.info(f"  {m}")
                continue
            
            if name == "risk":
                # ★ จัด format พิเศษสำหรับ risk section
                logger.info(f"  {'initial_portfolio_thb':<40} {m.get('initial_portfolio_thb', '-')} THB")
                logger.info(f"  {'final_portfolio_thb':<40} {m.get('final_portfolio_thb', '-')} THB")
                logger.info(f"  {'total_return_pct':<40} {m.get('total_return_pct', '-')}%")
                logger.info(f"  {'annualized_return_pct':<40} {m.get('annualized_return_pct', '-')}%")
                logger.info(f"  {'annualized_volatility_pct':<40} {m.get('annualized_volatility_pct', '-')}%")
                logger.info(f"  {'─'*50}")
                logger.info(f"  {'mdd_pct':<40} {m.get('mdd_pct', '-')}%  ← จุดเจ็บปวดสุด")
                logger.info(f"  {'mdd_peak_timestamp':<40} {m.get('mdd_peak_timestamp', '-')}")
                logger.info(f"  {'mdd_trough_timestamp':<40} {m.get('mdd_trough_timestamp', '-')}")
                logger.info(f"  {'─'*50}")
                logger.info(f"  {'sharpe_ratio':<40} {m.get('sharpe_ratio', '-')}  ← >1 ดี / >2 ดีมาก")
                logger.info(f"  {'sortino_ratio':<40} {m.get('sortino_ratio', '-')}  ← >2 ดี / >3 ยอดเยี่ยม")
            elif name == "trade":
                logger.info(f"  {'total_trades':<40} {m.get('total_trades', '-')}")
                logger.info(f"  {'winning_trades':<40} {m.get('winning_trades', '-')}")
                logger.info(f"  {'losing_trades':<40} {m.get('losing_trades', '-')}")
                logger.info(f"  {'win_rate_pct':<40} {m.get('win_rate_pct', '-')}%  ← >50% ดี")
                logger.info(f"  {'profit_factor':<40} {m.get('profit_factor', '-')}  ← >1.2 ดี / >2.0 ดีมาก")
                logger.info(f"  {'calmar_ratio':<40} {m.get('calmar_ratio', '-')}  ← >1.0 ดี")
                logger.info(f"  {'─'*50}")
                logger.info(f"  {'avg_win_thb':<40} {m.get('avg_win_thb', '-')} THB")
                logger.info(f"  {'avg_loss_thb':<40} {m.get('avg_loss_thb', '-')} THB")
                logger.info(f"  {'expectancy_thb':<40} {m.get('expectancy_thb', '-')} THB/trade")
                logger.info(f"  {'max_consec_losses':<40} {m.get('max_consec_losses', '-')}  ← สาย loss ยาวสุด")
                logger.info(f"  {'net_pnl_thb':<40} {m.get('net_pnl_thb', '-')} THB")
                logger.info(f"  {'total_cost_thb':<40} {m.get('total_cost_thb', '-')} THB  ← spread+commission")
            else:
                for k, v in m.items():
                    logger.info(f"  {k:<40} {v}")

        return metrics

    def export_csv(self, filename: str = None) -> str:
        os.makedirs(self.output_dir, exist_ok=True)

        if filename is None:
            ts_str     = datetime.now().strftime("%Y%m%d_%H%M%S")
            _model_name = getattr(self.ollama, 'model', getattr(self.ollama, 'PROVIDER_NAME', 'unknown'))
            model_slug  = re.sub(r"[^a-zA-Z0-9_-]", "_", _model_name)
            filename   = f"main_{model_slug}_{self.timeframe}_{self.days}d_{ts_str}.csv"

        path = os.path.join(self.output_dir, filename)
        df   = self.result_df.copy()

        # ★ [D] เพิ่ม portfolio columns ──────────────────────────────
        export_cols = [
            "timestamp",
            "close_thai",
            "portfolio_total_value",   # ★ equity curve
            "portfolio_cash",          # ★ cash component
            "portfolio_gold_grams",    # ★ gold held
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
            "session_id",      # Phase 2
            "can_execute",     # Phase 2
        ]
        # ────────────────────────────────────────────────────────────
        export_cols = [c for c in export_cols if c in df.columns]

        with open(path, "w", encoding="utf-8-sig") as f:
            _hdr_model = getattr(self.ollama, "model", getattr(self.ollama, "PROVIDER_NAME", "unknown"))
            f.write(f"=== MAIN PIPELINE BACKTEST — SUMMARY ({_hdr_model}) ===\n")
            if hasattr(self, "metrics"):
                for name, m in self.metrics.items():
                    if isinstance(m, dict):
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
    if signal == "HOLD":  return actual == "FLAT"
    if signal == "BUY":   return actual == "UP"
    if signal == "SELL":  return actual == "DOWN"
    return False


# ══════════════════════════════════════════════════════════════════
# Standalone runner
# ══════════════════════════════════════════════════════════════════


def run_main_backtest(
    gold_csv: str,
    news_csv: str       = "",
    external_csv: str   = "",   # CSV ที่มี gold_spot_usd, usd_thb_rate
    timeframe: str      = "1h",
    days: int           = 30,
    provider: str       = "ollama",
    model: str          = "",
    ollama_model: str   = "qwen3.5:9b",
    ollama_url: str     = "http://localhost:11434",
    cache_dir: str      = DEFAULT_CACHE_DIR,
    output_dir: str     = DEFAULT_OUTPUT_DIR,
    react_max_iter: int = 5,
) -> dict:
    bt = MainPipelineBacktest(
        gold_csv=gold_csv, news_csv=news_csv,
        external_csv=external_csv,
        provider=provider, model=model,
        ollama_model=ollama_model, ollama_url=ollama_url,
        timeframe=timeframe, days=days,
        cache_dir=cache_dir, output_dir=output_dir,
        react_max_iter=react_max_iter,
    )
    bt.run()
    metrics = bt.calculate_metrics()
    bt.export_csv()

    # Phase 4: Deploy Gate — พิมพ์ PASS/FAIL report ท้าย backtest
    gate = deploy_gate(metrics)
    print_gate_report(gate)
    metrics["deploy_gate"] = gate

    return metrics


# ══════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    parser = argparse.ArgumentParser(
        description="Main Pipeline Backtest — GoldTrader v3.2"
    )
    parser.add_argument("--gold-csv",      default="backtest/data_XAU_THB/Final_Merged_Backtest_Data_M5.csv")
    parser.add_argument("--news-csv",      default="", help="CSV: timestamp, overall_sentiment, news_count, top_headlines_summary")
    parser.add_argument("--external-csv",  default="", help="CSV: timestamp, gold_spot_usd, usd_thb_rate (optional columns)")
    parser.add_argument("--timeframe",  default="1h", choices=["1m","5m","15m","30m","1h","4h","1d"])
    parser.add_argument("--days",       default=30, type=int)
    parser.add_argument("--provider",   default="ollama",
                        choices=["gemini","groq","ollama","openai","claude","mock"],
                        help="LLM provider")
    parser.add_argument("--model",      default="",
                        help="Override model (ถ้าว่างใช้ default ของ provider)")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--cache-dir",  default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--react-iter", default=5, type=int)
    args = parser.parse_args()

    effective_model = args.model or _PROVIDER_MODEL_DEFAULTS.get(args.provider, args.provider)
    print("=" * 65)
    print(f"  MAIN PIPELINE BACKTEST — {args.provider} / {effective_model}")
    print("=" * 65)
    for k, v in vars(args).items():
        print(f"  {k:<15} {v}")
    print("=" * 65)

    # Availability check เฉพาะ Ollama (providers อื่นใช้ API key ใน env var)
    if args.provider == "ollama":
        _chk = OllamaClient(model=effective_model, base_url=args.ollama_url)
        if not _chk.is_available():
            print(f"✗ Ollama not reachable at {args.ollama_url}")
            sys.exit(1)
        print(f"✓ Ollama online | url: {args.ollama_url}\n")

    try:
        metrics = run_main_backtest(
            gold_csv=args.gold_csv, news_csv=args.news_csv,
            external_csv=args.external_csv,
            timeframe=args.timeframe, days=args.days,
            provider=args.provider, model=args.model,
            ollama_url=args.ollama_url,
            cache_dir=args.cache_dir, output_dir=args.output_dir,
            react_max_iter=args.react_iter,
        )
        print("\n✓ Done.")
        return metrics
    except Exception as e:
        logging.exception(f"✗ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()