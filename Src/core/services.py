"""
services.py — Business logic layer (independent from Gradio/UI)
Gold Trading Agent v3.2

Services are reusable across:
- dashboard.py (live trading)
- backtest.py (historical testing)
- CLI scripts
"""
import time
from typing import Optional, Dict, List
from datetime import datetime, timezone
from agent_core.core.prompt import AIRole
from logger_setup import sys_logger
from core.config import SERVICE_CONFIG, VALIDATION, INTERVAL_CHOICES, DEFAULT_PORTFOLIO
from core.utils import calculate_weighted_vote, validate_portfolio_update

try:
    from data_engine.orchestrator import GoldTradingOrchestrator
    from agent_core.core.react import ReactOrchestrator, ReactConfig
    from agent_core.llm.client import LLMClientFactory
    from agent_core.core.prompt import PromptBuilder, RoleRegistry, SkillRegistry
except ImportError as e:
    sys_logger.error(f"Import error: {e}")
    raise


# ─────────────────────────────────────────────
# Analysis Service
# ─────────────────────────────────────────────

class AnalysisService:
    """
    Main analysis service for trading signals
    
    Responsibilities:
    ✅ Input validation
    ✅ Data fetching (abstracted via orchestrator)
    ✅ LLM orchestration (ReAct loop)
    ✅ Weighted voting across intervals
    ✅ Result validation
    ✅ Retry logic with exponential backoff
    ✅ Error logging
    ✅ Optional database persistence
    
    Can be used by:
    - dashboard.py (live trading + persist to DB)
    - backtest.py (historical + no persistence)
    - CLI scripts (command-line with/without DB)
    """
    
    def __init__(self, 
                 skill_registry: SkillRegistry,
                 role_registry: RoleRegistry,
                 data_orchestrator: GoldTradingOrchestrator,
                 persistence=None):
        """
        Initialize analysis service
        
        Args:
            skill_registry: Tool/skill registry from config
            role_registry: AI role registry
            data_orchestrator: Data source (live, historical, mock)
            persistence: Optional database connection for saving runs
        """
        self.skill_registry = skill_registry
        self.role_registry = role_registry
        self.data_orchestrator = data_orchestrator
        self.persistence = persistence
        self.max_retries = SERVICE_CONFIG["max_retries"]
        sys_logger.info(f"AnalysisService initialized (max_retries={self.max_retries})")
    
    def run_analysis(self, 
                    provider: str, 
                    period: str, 
                    intervals: List[str]) -> Dict:
        """
        Run analysis for multiple intervals with weighted voting
        
        Args:
            provider: LLM provider (gemini, groq, anthropic, openai, mock)
            period: Data period (1d, 3d, 5d, 7d, 14d, 1mo, 2mo, 3mo)
            intervals: List of intervals (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
        
        Returns:
            {
                "status": "success" | "error",
                "data": {
                    "market_state": {...},
                    "interval_results": {...}
                },
                "voting_result": {
                    "final_signal": "BUY" | "SELL" | "HOLD",
                    "weighted_confidence": 0.822,
                    "voting_breakdown": {...},
                    "interval_details": [...]
                },
                "run_id": 123 (if saved to DB),
                "attempt": 1,
                "error": "..." (if status=error),
                "error_type": "validation" | "api_failure"
            }
        """
        
        # ✅ Step 1: Input Validation
        validation_error = self._validate_inputs(provider, period, intervals)
        if validation_error:
            sys_logger.error(f"Validation failed: {validation_error}")
            return {
                "status": "error",
                "error": validation_error,
                "error_type": "validation",
                "attempt": 0
            }
        
        # ✅ Step 2: Retry Loop
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                sys_logger.info(
                    f"Starting analysis (Attempt {attempt}/{self.max_retries}) "
                    f"provider={provider}, period={period}, intervals={intervals}"
                )
                
                # ✅ Step 2a: Fetch market data
                _PERIOD_TO_DAYS = {
                    "1d": 1, "3d": 3, "5d": 5, "7d": 7,
                    "14d": 14, "1mo": 30, "2mo": 60, "3mo": 90
                }
                sys_logger.info(f"Fetching market data (period={period})...")
                self.data_orchestrator.interval = intervals[0]  # ✅ set interval ก่อน fetch
                market_state = self.data_orchestrator.run(
                    history_days=_PERIOD_TO_DAYS.get(period, 90),
                    save_to_file=True
                )
                
                # ✅ Step 2b: Validate data quality
                if not market_state or "market_data" not in market_state:
                    raise ValueError("Failed to fetch market data")
                
                sys_logger.info(f"Market data fetched successfully")
                
                # ✅ Step 2c: Run analysis on each interval
                sys_logger.info(f"Running analysis on {len(intervals)} intervals...")
                interval_results = {}
                
                for interval in intervals:
                    sys_logger.info(f"  → Analyzing {interval} interval...")
                    interval_result = self._run_single_interval(
                        provider=provider,
                        market_state=market_state,
                        interval=interval
                    )
                    interval_results[interval] = interval_result
                
                sys_logger.info("Interval analysis complete")
                
                # ✅ Step 2d: Calculate weighted voting
                sys_logger.info("Calculating weighted voting...")
                voting_result = calculate_weighted_vote(interval_results)
                
                # ✅ Step 2e: Validate final decision
                if voting_result.get("error"):
                    raise ValueError(f"Voting error: {voting_result['error']}")
                
                sys_logger.info(
                    f"Weighted voting complete: "
                    f"final_signal={voting_result['final_signal']}, "
                    f"confidence={voting_result['weighted_confidence']:.1%}"
                )
                
                # ✅ Step 2f: Persist if configured
                run_id = None
                if self.persistence:
                    sys_logger.info("Saving run to database...")
                    run_id = self.persistence.save_run(
                        provider=provider,
                        result={
                            "signal": voting_result["final_signal"],
                            "confidence": voting_result["weighted_confidence"],
                            "voting_breakdown": voting_result["voting_breakdown"]
                        },
                        market_state=market_state,
                        interval_tf=",".join(intervals),
                        period=period
                    )
                    sys_logger.info(f"Run saved with ID: {run_id}")
                
                # ✅ Success!
                return {
                    "status": "success",
                    "data": {
                        "market_state": market_state,
                        "interval_results": interval_results,
                    },
                    "voting_result": voting_result,
                    "run_id": run_id,
                    "attempt": attempt
                }
            
            except ValueError as e:
                # ❌ Validation error → don't retry
                sys_logger.error(f"Validation error: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "error_type": "validation",
                    "attempt": attempt
                }
            
            except Exception as e:
                last_error = e
                sys_logger.warning(f"Attempt {attempt} failed: {type(e).__name__}: {e}")
                
                if attempt < self.max_retries:
                    # Exponential backoff
                    wait_time = SERVICE_CONFIG["retry_delay"] ** attempt
                    sys_logger.info(f"Retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                continue
        
        # ❌ All retries failed
        sys_logger.error(f"Failed after {self.max_retries} attempts: {last_error}")
        return {
            "status": "error",
            "error": str(last_error),
            "error_type": "api_failure",
            "attempt": self.max_retries
        }
    
    def _run_single_interval(self, 
                            provider: str, 
                            market_state: dict,
                            interval: str) -> Dict:
        """Run analysis for single interval using ReAct loop"""
        try:
            # Initialize LLM client
            llm_client = LLMClientFactory.create(provider)
            if not llm_client.is_available():
                raise ValueError(f"LLM provider {provider} not available")
            
            # Setup ReAct orchestration
            prompt_builder = PromptBuilder(self.role_registry, AIRole.ANALYST)
            react_config = ReactConfig(max_iterations=10)
            react_orchestrator = ReactOrchestrator(
                llm_client=llm_client,
                prompt_builder=prompt_builder,
                tool_registry=self.skill_registry,
                config=react_config
            )
            
            # Run ReAct loop
            react_result = react_orchestrator.run(market_state)
            
            # Extract decision
            decision = react_result.get("final_decision", {})
            
            return {
                "signal": decision.get("signal", "HOLD"),
                "confidence": decision.get("confidence", 0.0),
                "reasoning": decision.get("reasoning", ""),
                "entry_price": decision.get("entry_price"),
                "stop_loss": decision.get("stop_loss"),
                "take_profit": decision.get("take_profit"),
                "trace": react_result.get("trace", [])
            }
        
        except Exception as e:
            sys_logger.error(f"Error analyzing interval {interval}: {type(e).__name__}: {e}")
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: {str(e)}",
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "trace": []
            }
    
    def _validate_inputs(self, provider: str, period: str, intervals: List[str]) -> Optional[str]:
        """Validate input parameters. Return error message if invalid, None if OK"""
        from core.config import validate_provider, validate_period, validate_intervals
        
        if not validate_provider(provider):
            return f"Invalid provider: {provider}"
        
        if not validate_period(period):
            return f"Invalid period: {period}"
        
        if not validate_intervals(intervals):
            return f"Invalid intervals: {intervals}"
        
        if not intervals:
            return "At least one interval must be selected"
        
        return None


# ─────────────────────────────────────────────
# Portfolio Service
# ─────────────────────────────────────────────

class PortfolioService:
    """Portfolio CRUD operations and validation"""
    
    def __init__(self, db):
        """
        Args:
            db: RunDatabase instance
        """
        self.db = db
        sys_logger.info("PortfolioService initialized")
    
    def save_portfolio(self, 
                      cash: float, 
                      gold_grams: float,
                      cost_basis: float,
                      current_value: float,
                      pnl: float,
                      trades_today: int) -> Dict:
        """
        Save portfolio to database with validation
        
        Returns:
            {
                "status": "success" | "error",
                "message": "...",
                "data": {...}  (if success),
                "error": "..."  (if error)
            }
        """
        try:
            portfolio_data = {
                "cash_balance": float(cash),
                "gold_grams": float(gold_grams),
                "cost_basis_thb": float(cost_basis),
                "current_value_thb": float(current_value),
                "unrealized_pnl": float(pnl),
                "trades_today": int(trades_today),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Validate data quality
            is_valid, error_msg = validate_portfolio_update(None, portfolio_data)
            if not is_valid:
                return {
                    "status": "error",
                    "message": f"Validation failed: {error_msg}",
                    "error": error_msg
                }
            
            # Save to database
            self.db.save_portfolio(portfolio_data)
            sys_logger.info(f"Portfolio saved: cash=฿{cash}, gold={gold_grams}g, pnl=฿{pnl}")
            
            return {
                "status": "success",
                "message": "✅ Portfolio saved successfully",
                "data": portfolio_data
            }
        
        except Exception as e:
            sys_logger.error(f"Error saving portfolio: {type(e).__name__}: {e}")
            return {
                "status": "error",
                "message": f"Failed to save: {e}",
                "error": str(e)
            }
    
    def load_portfolio(self) -> Dict:
        """
        Load portfolio from database
        
        Returns:
            {
                "status": "success" | "error",
                "data": {...}  (if success),
                "error": "..."  (if error)
            }
        """
        try:
            portfolio = self.db.get_portfolio()
            
            # Use defaults if DB is empty
            if not portfolio:
                portfolio = DEFAULT_PORTFOLIO.copy()
                sys_logger.info("Portfolio loaded from defaults (DB was empty)")
            else:
                sys_logger.info(f"Portfolio loaded: cash=฿{portfolio.get('cash_balance', 0)}, gold={portfolio.get('gold_grams', 0)}g")
            
            return {
                "status": "success",
                "data": portfolio
            }
        
        except Exception as e:
            sys_logger.error(f"Error loading portfolio: {type(e).__name__}: {e}")
            return {
                "status": "error",
                "data": DEFAULT_PORTFOLIO.copy(),
                "error": str(e)
            }


# ─────────────────────────────────────────────
# History Service
# ─────────────────────────────────────────────

class HistoryService:
    """Run history and statistics operations"""
    
    def __init__(self, db):
        """
        Args:
            db: RunDatabase instance
        """
        self.db = db
        sys_logger.info("HistoryService initialized")
    
    def get_recent_runs(self, limit: int = 50) -> List[Dict]:
        """
        Get recent runs from database
        
        Args:
            limit: Maximum number of runs to return
        
        Returns:
            List of run records
        """
        try:
            runs = self.db.get_recent_runs(limit=limit)
            sys_logger.info(f"Fetched {len(runs)} recent runs")
            return runs
        except Exception as e:
            sys_logger.error(f"Error fetching history: {type(e).__name__}: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """
        Get signal statistics
        
        Returns:
            {
                "total": int,
                "buy_count": int,
                "sell_count": int,
                "hold_count": int,
                "avg_confidence": float,
                "avg_price": float
            }
        """
        try:
            stats = self.db.get_signal_stats()
            sys_logger.info(f"Stats: total={stats.get('total')}, buy={stats.get('buy_count')}, sell={stats.get('sell_count')}")
            return stats
        except Exception as e:
            sys_logger.error(f"Error computing stats: {type(e).__name__}: {e}")
            return {
                "total": 0,
                "buy_count": 0,
                "sell_count": 0,
                "hold_count": 0,
                "avg_confidence": 0.0,
                "avg_price": 0.0
            }
    
    def get_run_detail(self, run_id: int) -> Dict:
        """
        Get detailed information for a specific run
        
        Args:
            run_id: Run ID to fetch
        
        Returns:
            {
                "status": "success" | "error",
                "data": {...}  (if success),
                "message": "..."  (if error)
            }
        """
        try:
            # Assuming db has get_run_by_id method
            # If not, we can implement it or use get_recent_runs with filtering
            if hasattr(self.db, 'get_run_by_id'):
                run = self.db.get_run_by_id(run_id)
            else:
                # Fallback: search in recent runs
                recent = self.db.get_recent_runs(limit=1000)
                run = next((r for r in recent if r.get('id') == run_id), None)
            
            if not run:
                sys_logger.warning(f"Run {run_id} not found")
                return {"status": "error", "message": f"Run #{run_id} not found"}
            
            sys_logger.info(f"Loaded run detail: #{run_id}")
            return {
                "status": "success",
                "data": run
            }
        except Exception as e:
            sys_logger.error(f"Error loading run detail: {type(e).__name__}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


# ─────────────────────────────────────────────
# Service Initialization
# ─────────────────────────────────────────────

def init_services(skill_registry, role_registry, data_orchestrator, db):
    """
    Initialize all services with proper dependency injection
    
    Args:
        skill_registry: Skill registry from config
        role_registry: Role registry from config
        data_orchestrator: GoldTradingOrchestrator instance
        db: RunDatabase instance
    
    Returns:
        {
            "analysis": AnalysisService,
            "portfolio": PortfolioService,
            "history": HistoryService
        }
    """
    analysis_service = AnalysisService(
        skill_registry=skill_registry,
        role_registry=role_registry,
        data_orchestrator=data_orchestrator,
        persistence=db
    )
    
    portfolio_service = PortfolioService(db)
    history_service = HistoryService(db)
    
    sys_logger.info("All services initialized successfully")
    
    return {
        "analysis": analysis_service,
        "portfolio": portfolio_service,
        "history": history_service
    }