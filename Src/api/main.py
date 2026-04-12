import os
import sys
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Ensure we can import from Src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logs.logger_setup import sys_logger
from ui.core import (
    init_services,
    UI_CONFIG,
    PROVIDER_CHOICES,
    PERIOD_CHOICES,
    INTERVAL_CHOICES,
    AUTO_RUN_INTERVALS,
    DEFAULT_AUTO_RUN,
)
from ui.core.chart_service import chart_service

try:
    from data_engine.orchestrator import GoldTradingOrchestrator
    from backtest.engine.csv_orchestrator import CSVOrchestrator
    from agent_core.core.prompt import RoleRegistry, SkillRegistry
    from database.database import RunDatabase
except ImportError as e:
    sys_logger.error(f"⚠️  Import error: {e}")
    raise

# ─────────────────────────────────────────────
# Global Initialization
# ─────────────────────────────────────────────
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Registries
skill_registry = SkillRegistry()
skill_registry.load_from_json(os.path.join(base_dir, "agent_core", "config", "skills.json"))

role_registry = RoleRegistry(skill_registry)
role_registry.load_from_json(os.path.join(base_dir, "agent_core", "config", "roles.json"))

# Data + Database
orchestrator = GoldTradingOrchestrator()
db = RunDatabase()

# Services (business logic)
services = init_services(skill_registry, role_registry, orchestrator, db)

sys_logger.info("FastAPI backend initialized")

app = FastAPI(title="GoldTrader API", version="3.4")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────

class RunAnalysisRequest(BaseModel):
    provider: str
    period: str
    intervals: List[str]
    bypass_session_gate: bool = False

class SavePortfolioRequest(BaseModel):
    cash: float
    gold: float
    cost: float
    cur_val: float
    pnl: float
    trades: int

# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/api/home")
def get_home_overview():
    """Home page data: latest signal, portfolio snapshot, recent runs, gold price, market status."""
    try:
        from ui.core.config import is_thailand_market_open
        runs = services["history"].get_recent_runs(limit=7)
        latest = runs[0] if runs else {}
        pf = services["portfolio"].load_portfolio().get("data", {})
        price_data = chart_service.fetch_price(currency="THB")
        stats = services["history"].get_statistics()
        is_open = is_thailand_market_open()

        total_runs = len(runs)
        win_rate = sum(1 for r in runs if r.get("signal") == "BUY") / total_runs if total_runs else 0
        avg_conf = sum(float(r.get("confidence", 0)) for r in runs) / total_runs if total_runs else 0

        return {
            "latest_signal": {
                "signal": latest.get("signal", "HOLD"),
                "confidence": float(latest.get("confidence", 0)),
                "provider": latest.get("provider", "—"),
                "run_at": latest.get("run_at", "—"),
            },
            "gold_price": price_data,
            "portfolio": pf,
            "recent_runs": runs,
            "stats": stats,
            "market_open": is_open,
            "kpi": {
                "total_runs": total_runs,
                "win_rate": win_rate,
                "avg_confidence": avg_conf,
                "market_status": "OPEN" if is_open else "CLOSED",
            }
        }
    except Exception as e:
        sys_logger.error(f"Error in home overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analysis")
def run_analysis(req: RunAnalysisRequest):
    try:
        result = services["analysis"].run_analysis(
            req.provider,
            req.period,
            req.intervals,
            bypass_session_gate=req.bypass_session_gate,
        )
        return result
    except Exception as e:
        sys_logger.error(f"Error in analysis API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
def get_history(
    limit: int = Query(50, ge=1, le=500),
    signal: Optional[str] = Query(None, description="Filter by signal: BUY, SELL, HOLD"),
    search: Optional[str] = Query(None, description="Search by provider or signal"),
):
    try:
        runs = services["history"].get_recent_runs(limit=limit)
        # Filter by signal
        if signal and signal != "ALL":
            runs = [r for r in runs if r.get("signal") == signal]
        # Search filter
        if search:
            s = search.lower()
            runs = [r for r in runs if s in str(r.get("signal", "")).lower()
                    or s in str(r.get("provider", "")).lower()]
        stats = services["history"].get_statistics()
        return {"runs": runs, "stats": stats}
    except Exception as e:
        sys_logger.error(f"Error refreshing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/{run_id}")
def get_run_detail(run_id: int):
    try:
        detail = services["history"].get_run_detail(run_id)
        if detail["status"] == "error":
            raise HTTPException(status_code=404, detail=detail["message"])
        return detail["data"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/{run_id}/llm-logs")
def get_llm_logs(run_id: int):
    """Return LLM call logs for a specific run."""
    try:
        if hasattr(services["history"], "get_llm_logs_for_run"):
            logs = services["history"].get_llm_logs_for_run(run_id)
            return {"logs": logs}
        # Fallback: extract from trace in run detail
        detail = services["history"].get_run_detail(run_id)
        if detail["status"] == "error":
            raise HTTPException(status_code=404, detail=detail["message"])
        trace = detail["data"].get("trace", [])
        return {"logs": [], "trace": trace}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chart/price")
def get_gold_price(currency: str = Query("THB")):
    """Fetch live gold price via chart_service."""
    try:
        return chart_service.fetch_price(currency=currency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chart/providers")
def get_providers():
    """Return list of LLM provider metadata."""
    try:
        return {"providers": chart_service.get_providers_info()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
def load_portfolio():
    try:
        result = services["portfolio"].load_portfolio()
        return result["data"]
    except Exception as e:
        sys_logger.error(f"Load portfolio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio")
def save_portfolio(req: SavePortfolioRequest):
    try:
        result = services["portfolio"].save_portfolio(
            cash=req.cash,
            gold_grams=req.gold,
            cost_basis=req.cost,
            current_value=req.cur_val,
            pnl=req.pnl,
            trades_today=req.trades,
        )
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return {"message": result["message"], "data": result["data"]}
    except Exception as e:
        sys_logger.error(f"Save portfolio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
def get_config():
    return {
        "providers": PROVIDER_CHOICES,
        "periods": PERIOD_CHOICES,
        "intervals": INTERVAL_CHOICES,
        "auto_run_intervals": AUTO_RUN_INTERVALS,
        "default_auto_run": DEFAULT_AUTO_RUN
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting API on port {port}")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
