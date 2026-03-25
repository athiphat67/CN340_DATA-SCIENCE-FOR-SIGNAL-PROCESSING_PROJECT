"""
execution/router.py
Validates the raw LLM decision dict and routes it to the risk manager.
This layer sits between the agent brain and the actual order execution.
"""

import logging
from pydantic import BaseModel, field_validator, ValidationError
from execution.risk_manager import RiskManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class TradeDecision(BaseModel):
    action: str
    quantity: float
    reasoning: str = ""

    @field_validator("action")
    @classmethod
    def action_must_be_valid(cls, v: str) -> str:
        allowed = {"BUY", "SELL", "HOLD"}
        v = v.upper().strip()
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}, got {v!r}")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("quantity must be >= 0")
        return v


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
class TradeRouter:
    def __init__(self, risk_manager: RiskManager | None = None):
        self.risk_manager = risk_manager or RiskManager()

    def route(self, raw_decision: dict) -> dict:
        """
        1. Validate JSON schema with Pydantic.
        2. Pass through risk manager.
        3. Return a structured result dict.
        """
        # --- Step 1: Schema validation ---
        try:
            decision = TradeDecision(**raw_decision)
        except (ValidationError, TypeError) as exc:
            logger.warning(f"[Router] Schema validation failed: {exc}")
            return {
                "status": "REJECTED",
                "reason": f"Invalid decision format: {exc}",
                "original": raw_decision,
            }

        # --- Step 2: Risk check ---
        ok, reason = self.risk_manager.validate_trade(decision.model_dump())
        if not ok:
            logger.warning(f"[Router] Risk check failed: {reason}")
            return {
                "status": "REJECTED",
                "reason": reason,
                "decision": decision.model_dump(),
            }

        logger.info(
            f"[Router] Trade approved — {decision.action} {decision.quantity} lots"
        )
        return {
            "status": "APPROVED",
            "reason": "All checks passed",
            "decision": decision.model_dump(),
        }
