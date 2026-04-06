"""
services.py — Business logic layer (independent from Gradio/UI)
Gold Trading Agent v3.3

Changes v3.3:
  - Fix: provider name normalization (gemini_2.5_flash → gemini)
  - Fix: save_run double-call — @log_method removed from db.save_run
  - New: save llm_logs per interval after each run (thinking log → DB)
  - New: llm_log data extracted from react_result and interval result
"""

import time
from typing import Optional, Dict, List
from datetime import datetime, timezone
from agent_core.core.prompt import AIRole
from logs.logger_setup import sys_logger, log_method
from ui.core.config import (
    SERVICE_CONFIG,
    VALIDATION,
    INTERVAL_CHOICES,
    DEFAULT_PORTFOLIO,
    is_thailand_market_open,
)
from ui.core.utils import calculate_weighted_vote, validate_portfolio_update
from notification.discord_notifer import DiscordNotifier

try:
    from data_engine.orchestrator import GoldTradingOrchestrator
    from agent_core.core.react import ReactOrchestrator, ReactConfig
    from agent_core.llm.client import LLMClientFactory, LLMClient
    from agent_core.core.prompt import PromptBuilder, RoleRegistry, SkillRegistry
except ImportError as e:
    sys_logger.error(f"Import error: {e}")
    raise


# ─────────────────────────────────────────────
# Provider Name Normalization
# ─────────────────────────────────────────────
# FIX: UI อาจส่งชื่อที่ไม่ตรงกับ config เช่น "gemini_2.5_flash" แทน "gemini"
# map ทุก variant ที่เป็นไปได้ → canonical name

_PROVIDER_ALIASES: dict[str, str] = {
    # Gemini variants
    "gemini_2.5_flash":             "gemini",
    "gemini_2.5_flash_lite":        "gemini",
    "gemini_3.1_flash_lite":        "gemini",
    "gemini-2.5-flash":             "gemini",
    "gemini-2.5-flash-preview":     "gemini",
    "gemini-3.1-flash-lite":        "gemini",
    "gemini 2.5 flash":             "gemini",
    "gemini 3.1 flash lite":        "gemini",
    # Groq variants
    "groq_llama":                   "groq",
    "llama-3.3-70b-versatile":      "groq",
    "groq llama 3.3 70b versatile": "groq",
    # Others
    "mock-v1":                      "mock",
    "mock_v1":                      "mock",
}


def _normalize_provider(provider: str) -> str:
    """
    แปลง provider name จาก UI ให้เป็น canonical name ที่ config รู้จัก
    case-insensitive, underscore/hyphen-tolerant
    """
    if not provider:
        return provider
    # ลอง exact match ก่อน
    normalized = _PROVIDER_ALIASES.get(provider)
    if normalized:
        return normalized
    # ลอง lowercase
    normalized = _PROVIDER_ALIASES.get(provider.lower())
    if normalized:
        return normalized
    # ลอง strip/replace
    cleaned = provider.lower().strip().replace("-", "_").replace(" ", "_")
    normalized = _PROVIDER_ALIASES.get(cleaned)
    if normalized:
        return normalized
    # ไม่เจอ → คืนตัวเดิม (ให้ validate ทีหลัง)
    return provider


# ─────────────────────────────────────────────
# Analysis Service
# ─────────────────────────────────────────────


class AnalysisService:
    """
    Main analysis service for trading signals

    Responsibilities:
    ✅ Input validation + provider normalization
    ✅ Data fetching (via orchestrator)
    ✅ LLM orchestration (ReAct loop)
    ✅ Weighted voting across intervals
    ✅ Retry logic with exponential backoff
    ✅ Database persistence (runs + llm_logs)
    """

    def __init__(
        self,
        skill_registry,
        role_registry,
        data_orchestrator,
        persistence=None,
        notifier: DiscordNotifier = None,       # ← ADD THIS PARAM
    ):
        self.skill_registry    = skill_registry
        self.role_registry     = role_registry
        self.data_orchestrator = data_orchestrator
        self.persistence       = persistence
        self.notifier          = notifier       # ← ADD THIS LINE
        self.max_retries       = SERVICE_CONFIG["max_retries"]
        sys_logger.info(f"AnalysisService initialized (max_retries={self.max_retries})")


    def run_analysis(self, provider: str, period: str, intervals: List[str]) -> Dict:
        """
        Run analysis for multiple intervals with weighted voting

        Returns:
            {
                "status": "success" | "error",
                "data": {
                    "market_state": {...},
                    "interval_results": {...}
                },
                "voting_result": {...},
                "run_id": int,          # ถ้า persist สำเร็จ
                "llm_log_ids": [int],   # IDs ของ llm_logs ที่บันทึก
                "attempt": int,
                "market_open": bool
            }
        """
        # ── Normalize provider name (fix: gemini_2.5_flash → gemini) ──────
        original_provider = provider
        provider = _normalize_provider(provider)
        if provider != original_provider:
            sys_logger.info(
                f"Provider normalized: '{original_provider}' → '{provider}'"
            )

        # ── Input validation ───────────────────────────────────────────────
        validation_error = self._validate_inputs(provider, period, intervals)
        if validation_error:
            sys_logger.error(f"Validation failed: {validation_error}")
            return {
                "status":     "error",
                "error":      validation_error,
                "error_type": "validation",
                "attempt":    0,
            }

        # ── Market hours check (warn only) ─────────────────────────────────
        market_open = is_thailand_market_open()
        if not market_open:
            sys_logger.warning(
                "Thailand gold market is closed (weekend/holiday) — running analysis anyway"
            )

        # ── Retry loop ─────────────────────────────────────────────────────
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                sys_logger.info(
                    f"Starting analysis (Attempt {attempt}/{self.max_retries}) "
                    f"provider={provider}, period={period}, intervals={intervals}"
                )

                # Step 2a: Fetch market data
                _PERIOD_TO_DAYS = {
                    "1d": 1, "3d": 3, "5d": 5, "7d": 7, "14d": 14,
                    "1mo": 30, "2mo": 60, "3mo": 90,
                }
                sys_logger.info(f"Fetching market data (period={period})...")
                market_state = self.data_orchestrator.run(
                    history_days=_PERIOD_TO_DAYS.get(period, 90), save_to_file=True
                )

                if not market_state or "market_data" not in market_state:
                    raise ValueError("Failed to fetch market data")

                sys_logger.info("Market data fetched successfully")

                # Attach portfolio to market state
                if self.persistence:
                    portfolio = self.persistence.get_portfolio()
                    if not portfolio:
                        from ui.core.config import DEFAULT_PORTFOLIO
                        portfolio = DEFAULT_PORTFOLIO.copy()
                    market_state["portfolio"] = portfolio
                sys_logger.info("Portfolio merged into market state")

                # Step 2c: Run analysis on each interval
                sys_logger.info(f"Running analysis on {len(intervals)} intervals...")
                interval_results = {}
                llm_logs_pending: List[dict] = []   # ← เก็บ log data รอ run_id

                for interval in intervals:
                    sys_logger.info(f"  → Analyzing {interval} interval...")
                    interval_result = self._run_single_interval(
                        provider=provider,
                        market_state=market_state,
                        interval=interval,
                    )
                    interval_results[interval] = interval_result

                    # ── Extract llm log data จาก interval result ────────────
                    llm_log = _extract_llm_log(interval_result, interval)
                    llm_logs_pending.append(llm_log)

                sys_logger.info("Interval analysis complete")

                # Step 2d: Weighted voting
                sys_logger.info("Calculating weighted voting...")
                voting_result = calculate_weighted_vote(interval_results)

                if voting_result.get("error"):
                    raise ValueError(f"Voting error: {voting_result['error']}")

                sys_logger.info(
                    f"Weighted voting complete: "
                    f"final_signal={voting_result['final_signal']}, "
                    f"confidence={voting_result['weighted_confidence']:.1%}"
                )

                # Step 2e: Provider label (แสดง fallback ถ้ามี)
                best_iv = max(
                    interval_results.items(),
                    key=lambda x: x[1].get("confidence", 0),
                )[0]
                actual_provider = interval_results[best_iv].get("provider_used", provider)
                provider_label  = (
                    f"{provider}→{actual_provider}" if actual_provider != provider
                    else provider
                )
                
                # ── Step 2e.5: Notify Discord (BEFORE DB save) ──────────────
                if self.notifier:
                    sent = self.notifier.notify(
                        voting_result    = voting_result,
                        interval_results = interval_results,
                        market_state     = market_state,
                        provider         = provider_label,
                        period           = period,
                        run_id           = None,   # ยังไม่มี run_id ตอนนี้
                    )
                    if sent:
                        sys_logger.info("Discord notification sent ✅")
                    elif self.notifier.last_error:
                        sys_logger.warning(
                            f"Discord notification failed: {self.notifier.last_error}"
                        )

                # Step 2f: Persist to DB (runs + llm_logs)
                run_id      = None
                llm_log_ids = []
                if self.persistence:
                    sys_logger.info("Saving run to database...")

                    # ── save_run (เรียกแค่ครั้งเดียว — ไม่มี @log_method บน db method) ──
                    run_id = self.persistence.save_run(
                        provider=provider_label,
                        result={
                            "signal":          voting_result["final_signal"],
                            "confidence":      voting_result["weighted_confidence"],
                            "voting_breakdown":voting_result["voting_breakdown"],
                            # ส่งราคาจาก best interval (THB/gram)
                            "entry_price":     interval_results[best_iv].get("entry_price"),
                            "stop_loss":       interval_results[best_iv].get("stop_loss"),
                            "take_profit":     interval_results[best_iv].get("take_profit"),
                            "react_trace":     interval_results[best_iv].get("trace", []),
                            "iterations_used": interval_results[best_iv].get("iterations_used", 0),
                            "tool_calls_used": interval_results[best_iv].get("tool_calls_used", 0),
                        },
                        market_state=market_state,
                        interval_tf=",".join(intervals),
                        period=period,
                    )
                    sys_logger.info(f"Run saved with ID: {run_id}")

                    # ── save llm_logs (กระบวนการคิดทั้งหมด) ─────────────────
                    llm_log_ids = self.persistence.save_llm_logs_batch(
                        run_id=run_id,
                        logs=llm_logs_pending,
                    )
                    sys_logger.info(
                        f"LLM logs saved: {len(llm_log_ids)} entries for run_id={run_id}"
                    )

                return {
                    "status":      "success",
                    "market_open": market_open,
                    "data": {
                        "market_state":    market_state,
                        "interval_results":interval_results,
                    },
                    "voting_result": voting_result,
                    "run_id":        run_id,
                    "llm_log_ids":   llm_log_ids,
                    "attempt":       attempt,
                }

            except ValueError as e:
                sys_logger.error(f"Validation error: {e}")
                return {
                    "status":     "error",
                    "error":      str(e),
                    "error_type": "validation",
                    "attempt":    attempt,
                }

            except Exception as e:
                last_error = e
                sys_logger.warning(
                    f"Attempt {attempt} failed: {type(e).__name__}: {e}"
                )
                if attempt < self.max_retries:
                    wait_time = SERVICE_CONFIG["retry_delay"] ** attempt
                    sys_logger.info(
                        f"Retrying in {wait_time}s... "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                continue

        sys_logger.error(f"Failed after {self.max_retries} attempts: {last_error}")
        return {
            "status":     "error",
            "error":      str(last_error),
            "error_type": "api_failure",
            "attempt":    self.max_retries,
        }

    def _run_single_interval(
        self, provider: str, market_state: dict, interval: str
    ) -> Dict:
        """Run analysis for single interval using ReAct loop with provider fallback chain"""
        t_start = time.time()
        try:
            from ui.core.config import (
                PROVIDER_FALLBACK_CHAIN,
                OPENROUTER_MODELS,
                get_openrouter_model,
            )
            from agent_core.llm.client import FallbackChainClient

            OLLAMA_MODELS = [
                "qwen3.5:9b", "qwen2.5:7b", "qwen2.5:3b",
                "deepseek-r1:7b", "deepseek-r1:8b", "ollama",
            ]

            chain_key     = "ollama" if provider in OLLAMA_MODELS else provider
            fallback_order = PROVIDER_FALLBACK_CHAIN.get(chain_key, [chain_key, "mock"])

            sys_logger.info(
                f"[{interval}] Building fallback chain: {' → '.join(fallback_order)}"
            )

            chain_clients: list[tuple[str, LLMClient]] = []
            for p in fallback_order:
                try:
                    if p in OLLAMA_MODELS or (p == "ollama" and provider in OLLAMA_MODELS):
                        model_name = provider if provider != "ollama" else "qwen3.5:9b"
                        client = LLMClientFactory.create(
                            "ollama", model=model_name,
                            base_url="http://localhost:11434",
                            temperature=0.1,
                        )
                    # ✨ NEW: OpenRouter models (openrouter_llama_70b, openrouter_qwen_72b, etc.)
                    elif p.startswith("openrouter_"):
                        model_config = get_openrouter_model(p)
                        if not model_config:
                            raise ValueError(f"Unknown OpenRouter model: {p}")
                        if not model_config.get("api_key"):
                            raise ValueError(f"OPENROUTER_API_KEY not set in .env for {p}")
                        
                        sys_logger.info(
                            f"  Creating OpenRouter client: {p} "
                            f"(model={model_config['model_id']})"
                        )
                        client = LLMClientFactory.create(
                            "openrouter",
                            api_key=model_config["api_key"],
                            model=model_config["model_id"],
                            temperature=0.1,
                        )
                    else:
                        client = LLMClientFactory.create(p)
                    chain_clients.append((p, client))
                    sys_logger.info(f"  ✅ Provider '{p}' ready")
                except Exception as e:
                    sys_logger.warning(f"  ⚠️ Provider '{p}' skipped: {e}")

            if not chain_clients:
                raise ValueError(f"No providers available for chain: {fallback_order}")

            llm_client = FallbackChainClient(chain_clients)

            if not llm_client.is_available():
                raise ValueError(
                    f"No provider in fallback chain available: {fallback_order}"
                )

            # ReAct orchestration
            prompt_builder   = PromptBuilder(self.role_registry, AIRole.ANALYST)
            react_config     = ReactConfig(max_iterations=3)
            react_orchestrator = ReactOrchestrator(
                llm_client=llm_client,
                prompt_builder=prompt_builder,
                tool_registry=self.skill_registry,
                config=react_config,
            )

            react_result = react_orchestrator.run(market_state)
            elapsed_ms   = int((time.time() - t_start) * 1000)

            used_provider = llm_client.active_provider
            fallback_log  = llm_client.errors

            if fallback_log:
                sys_logger.warning(
                    f"[{interval}] Fallback occurred — used '{used_provider}' "
                    f"after {len(fallback_log)} failure(s): "
                    + "; ".join(e["provider"] for e in fallback_log)
                )
            else:
                sys_logger.info(f"[{interval}] Used primary provider '{used_provider}'")

            decision = react_result.get("final_decision", {})

            return {
                "signal":          decision.get("signal", "HOLD"),
                "confidence":      decision.get("confidence", 0.0),
                "reasoning":       decision.get("reasoning", ""),
                "rationale":       decision.get("rationale", decision.get("reasoning", "")),
                "entry_price":     decision.get("entry_price"),    # THB/gram
                "stop_loss":       decision.get("stop_loss"),
                "take_profit":     decision.get("take_profit"),
                "trace":           react_result.get("trace", []),
                "provider_used":   used_provider,
                "fallback_log":    fallback_log,
                "is_fallback":     bool(fallback_log),
                "fallback_from":   fallback_log[0]["provider"] if fallback_log else None,
                "elapsed_ms":      elapsed_ms,
                # Token usage (มีถ้า react_result expose ไว้ — ไม่ error ถ้าไม่มี)
                "token_input":     react_result.get("token_input"),
                "token_output":    react_result.get("token_output"),
                "token_total":     react_result.get("token_total"),
                "iterations_used": react_result.get("iterations_used", 0),
                "tool_calls_used": react_result.get("tool_calls_used", 0),
                "full_prompt":     react_result.get("prompt_text"),
                "full_response":   react_result.get("response_raw"),
            }

        except Exception as e:
            elapsed_ms = int((time.time() - t_start) * 1000)
            sys_logger.error(
                f"Error analyzing interval {interval}: {type(e).__name__}: {e}"
            )
            return {
                "signal":          "HOLD",
                "confidence":      0.0,
                "reasoning":       f"Analysis failed: {str(e)}",
                "rationale":       f"Analysis failed: {str(e)}",
                "entry_price":     None,
                "stop_loss":       None,
                "take_profit":     None,
                "trace":           [],
                "provider_used":   "none",
                "fallback_log":    [],
                "is_fallback":     False,
                "fallback_from":   None,
                "elapsed_ms":      elapsed_ms,
                "token_input":     None,
                "token_output":    None,
                "token_total":     None,
                "iterations_used": 0,
                "tool_calls_used": 0,
                "full_prompt":     None,
                "full_response":   None,
            }

    def _validate_inputs(
        self, provider: str, period: str, intervals: List[str]
    ) -> Optional[str]:
        """Validate input parameters. Return error message if invalid, None if OK"""
        from ui.core.config import validate_provider, validate_period, validate_intervals

        if not validate_provider(provider):
            return f"Invalid provider: {provider}"

        if not validate_period(period):
            return f"Invalid period: {period}"

        if not intervals:
            return "At least one interval must be selected"

        if not validate_intervals(intervals):
            return f"Invalid intervals: {intervals}"

        return None


# ─────────────────────────────────────────────
# LLM Log Extractor (helper)
# ─────────────────────────────────────────────

def _extract_llm_log(interval_result: dict, interval: str) -> dict:
    """
    สกัด llm_log data จาก interval_result
    สำหรับบันทึกลง llm_logs table
    """
    fallback_log  = interval_result.get("fallback_log", [])
    is_fallback   = bool(fallback_log)
    fallback_from = fallback_log[0]["provider"] if fallback_log else None

    return {
        "interval_tf":     interval,
        "step_type":       "THOUGHT_FINAL",
        "iteration":       interval_result.get("iterations_used", 0),
        "provider":        interval_result.get("provider_used", ""),
        "signal":          interval_result.get("signal", "HOLD"),
        "confidence":      interval_result.get("confidence", 0.0),
        "rationale":       interval_result.get("rationale", interval_result.get("reasoning", "")),
        "entry_price":     interval_result.get("entry_price"),   # THB/gram
        "stop_loss":       interval_result.get("stop_loss"),
        "take_profit":     interval_result.get("take_profit"),
        "trace_json":      interval_result.get("trace", []),
        "token_input":     interval_result.get("token_input"),
        "token_output":    interval_result.get("token_output"),
        "token_total":     interval_result.get("token_total"),
        "elapsed_ms":      interval_result.get("elapsed_ms"),
        "iterations_used": interval_result.get("iterations_used", 0),
        "tool_calls_used": interval_result.get("tool_calls_used", 0),
        "is_fallback":     is_fallback,
        "fallback_from":   fallback_from,
        # จะมีข้อมูลเมื่อ react.py expose ออกมา
        "full_prompt":     interval_result.get("full_prompt"),
        "full_response":   interval_result.get("full_response"),
    }


# ─────────────────────────────────────────────
# Portfolio Service
# ─────────────────────────────────────────────


class PortfolioService:
    """Portfolio CRUD operations and validation"""

    def __init__(self, db):
        self.db = db
        sys_logger.info("PortfolioService initialized")

    def save_portfolio(
        self,
        cash: float,
        gold_grams: float,
        cost_basis: float,
        current_value: float,
        pnl: float,
        trades_today: int,
    ) -> Dict:
        try:
            portfolio_data = {
                "cash_balance":      float(cash),
                "gold_grams":        float(gold_grams),
                "cost_basis_thb":    float(cost_basis),
                "current_value_thb": float(current_value),
                "unrealized_pnl":    float(pnl),
                "trades_today":      int(trades_today),
                "updated_at":        datetime.now(timezone.utc).isoformat(),
            }

            is_valid, error_msg = validate_portfolio_update(None, portfolio_data)
            if not is_valid:
                return {
                    "status":  "error",
                    "message": f"Validation failed: {error_msg}",
                    "error":   error_msg,
                }

            self.db.save_portfolio(portfolio_data)
            sys_logger.info(
                f"Portfolio saved: cash=฿{cash}, gold={gold_grams}g, pnl=฿{pnl}"
            )

            return {
                "status":  "success",
                "message": "✅ Portfolio saved successfully",
                "data":    portfolio_data,
            }

        except Exception as e:
            sys_logger.error(f"Error saving portfolio: {type(e).__name__}: {e}")
            return {
                "status":  "error",
                "message": f"Failed to save: {e}",
                "error":   str(e),
            }

    def load_portfolio(self) -> Dict:
        try:
            portfolio = self.db.get_portfolio()
            if not portfolio:
                portfolio = DEFAULT_PORTFOLIO.copy()
                sys_logger.info("Portfolio loaded from defaults (DB was empty)")
            else:
                sys_logger.info(
                    f"Portfolio loaded: cash=฿{portfolio.get('cash_balance', 0)}, "
                    f"gold={portfolio.get('gold_grams', 0)}g"
                )
            return {"status": "success", "data": portfolio}

        except Exception as e:
            sys_logger.error(f"Error loading portfolio: {type(e).__name__}: {e}")
            return {
                "status": "error",
                "data":   DEFAULT_PORTFOLIO.copy(),
                "error":  str(e),
            }


# ─────────────────────────────────────────────
# History Service
# ─────────────────────────────────────────────


class HistoryService:
    """Run history, statistics, and LLM log retrieval"""

    def __init__(self, db):
        self.db = db
        sys_logger.info("HistoryService initialized")

    def get_recent_runs(self, limit: int = 50) -> List[Dict]:
        try:
            runs = self.db.get_recent_runs(limit=limit)
            sys_logger.info(f"Fetched {len(runs)} recent runs")
            return runs
        except Exception as e:
            sys_logger.error(f"Error fetching history: {type(e).__name__}: {e}")
            return []

    def get_statistics(self) -> Dict:
        try:
            stats = self.db.get_signal_stats()
            sys_logger.info(
                f"Stats: total={stats.get('total')}, "
                f"buy={stats.get('buy_count')}, sell={stats.get('sell_count')}"
            )
            return stats
        except Exception as e:
            sys_logger.error(f"Error computing stats: {type(e).__name__}: {e}")
            return {
                "total": 0, "buy_count": 0, "sell_count": 0,
                "hold_count": 0, "avg_confidence": 0.0, "avg_price": 0.0,
            }

    def get_run_detail(self, run_id: int) -> Dict:
        try:
            if hasattr(self.db, "get_run_by_id"):
                run = self.db.get_run_by_id(run_id)
            else:
                recent = self.db.get_recent_runs(limit=1000)
                run = next((r for r in recent if r.get("id") == run_id), None)

            if not run:
                sys_logger.warning(f"Run {run_id} not found")
                return {"status": "error", "message": f"Run #{run_id} not found"}

            sys_logger.info(f"Loaded run detail: #{run_id}")
            return {"status": "success", "data": run}

        except Exception as e:
            sys_logger.error(f"Error loading run detail: {type(e).__name__}: {e}")
            return {"status": "error", "message": str(e)}

    def get_llm_logs(self, run_id: int) -> List[Dict]:
        """ดึง LLM thinking logs ของ run_id หนึ่งๆ"""
        try:
            logs = self.db.get_llm_logs_for_run(run_id)
            sys_logger.info(f"Fetched {len(logs)} llm_logs for run_id={run_id}")
            return logs
        except Exception as e:
            sys_logger.error(f"Error fetching llm_logs: {type(e).__name__}: {e}")
            return []

    def get_recent_llm_logs(self, limit: int = 20) -> List[Dict]:
        """ดึง LLM thinking logs ล่าสุด (ข้ามรอบ)"""
        try:
            logs = self.db.get_recent_llm_logs(limit=limit)
            sys_logger.info(f"Fetched {len(logs)} recent llm_logs")
            return logs
        except Exception as e:
            sys_logger.error(f"Error fetching recent llm_logs: {type(e).__name__}: {e}")
            return []
    
    def get_llm_logs_for_run(self, run_id: int) -> list:
        return self.db.get_llm_logs_for_run(run_id)


# ─────────────────────────────────────────────
# Service Initialization
# ─────────────────────────────────────────────


def init_services(skill_registry, role_registry, data_orchestrator, db):
    """Initialize all services with dependency injection"""
 
    # สร้าง notifier instance เดียว (singleton) — re-use ทั้ง app
    notifier = DiscordNotifier()
    sys_logger.info(
        f"DiscordNotifier initialized — "
        f"enabled={notifier.enabled}, "
        f"notify_hold={notifier.notify_hold}, "
        f"webhook_set={bool(notifier.webhook_url)}"
    )
 
    analysis_service = AnalysisService(
        skill_registry    = skill_registry,
        role_registry     = role_registry,
        data_orchestrator = data_orchestrator,
        persistence       = db,
        notifier          = notifier,           # ← INJECT HERE
    )
    portfolio_service = PortfolioService(db)
    history_service   = HistoryService(db)
 
    sys_logger.info("All services initialized successfully")
 
    return {
        "analysis":  analysis_service,
        "portfolio": portfolio_service,
        "history":   history_service,
        "notifier":  notifier,                  # ← EXPOSE สำหรับ Dashboard toggle
    }