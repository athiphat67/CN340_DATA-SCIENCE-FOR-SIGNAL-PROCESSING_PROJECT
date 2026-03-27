"""
execution/router.py
Validates the raw LLM decision dict and routes it to the risk manager.
This layer sits between the agent brain and the actual order execution.
"""

import logging
import math  #for temperature scaling
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
    confidence: float | None = None # LLM confidence score
    sampling_params: dict = {}  # {"temperature": τ, "top_p": p}

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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Sampling-aware validation methods
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @staticmethod
    def _apply_temperature(confidence: float, tau: float) -> float:
        """
        Apply temperature scaling to confidence score.
        
        τ → 0: Greedy (deterministic, higher confidence)
        τ = 1: Standard softmax
        τ > 1: More exploratory (lower confidence)
        """
        if tau == 1.0 or confidence <= 0:
            return confidence
        
        try:
            # Softmax with temperature: exp(log(c) / τ)
            scaled = math.exp(math.log(confidence) / tau)
            return min(1.0, max(0.0, scaled))  # Clamp to [0, 1]
        except (ValueError, ZeroDivisionError):
            return confidence

    @staticmethod
    def _should_reject_by_nucleus(confidence: float, top_p: float) -> bool:
        """
        Check if signal falls outside top-p nucleus.
        
        top-p nucleus = highest probability tokens that sum to p
        if confidence < (1 - top_p), reject
        """
        threshold = 1.0 - top_p
        return confidence < threshold
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def route(self, raw_decision: dict) -> dict:
        """
        1. Validate JSON schema with Pydantic.
        2. Apply sampling validation (Temperature + Top-p).
        3. Pass through risk manager.
        4. Return a structured result dict.
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

        # --- Step 2: Sampling Validation (Temperature + Top-p) ---
        sampling_params = decision.sampling_params or {}
        if sampling_params and decision.confidence is not None:  # เพิ่มเงื่อนไข
            temperature = sampling_params.get("temperature", 1.0)
            top_p = sampling_params.get("top_p", 0.9)
            
            # Apply temperature scaling
            original_confidence = decision.confidence
            scaled_confidence = self._apply_temperature(original_confidence, temperature)
            
            # Check nucleus threshold
            if self._should_reject_by_nucleus(scaled_confidence, top_p):
                logger.warning(
                    f"[Router] Sampling rejection: confidence={original_confidence:.2f} "
                    f"(scaled={scaled_confidence:.2f}) below nucleus threshold {1-top_p:.2f}"
                )
                return {
                    "status": "REJECTED",
                    "reason": (
                        f"Confidence {original_confidence:.2f} (scaled {scaled_confidence:.2f}) "
                        f"below nucleus threshold {1-top_p:.2f}"
                    ),
                    "decision": decision.model_dump(),
                    "sampling_info": {
                        "temperature": temperature,
                        "top_p": top_p,
                        "original_confidence": original_confidence,
                        "scaled_confidence": scaled_confidence,
                    }
                }
            
            logger.debug(
                f"[Router] Sampling passed: confidence={original_confidence:.2f} "
                f"→ {scaled_confidence:.2f} (τ={temperature:.2f}, p={top_p:.1f})"
            )

        # --- Step 3: Risk check ---
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