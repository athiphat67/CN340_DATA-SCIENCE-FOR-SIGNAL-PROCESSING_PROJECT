"""
execution/position_sizer.py
Calculates position size from Phase 2 (Agent Core) output
using Expected Value (EV) analysis and the Kelly Criterion.

Slide reference:
  - Slide 1 : Expected Value and Win-Rate Analysis
               𝔼[V] = (W × R_W) − (L × R_L)
  - Slide 2 : Optimal Position Sizing — The Kelly Criterion
               f* = W − (1 − W) / R   →  use Half-Kelly (f*/2) in practice
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class EVResult:
    """Result from Expected Value analysis (Slide 1)."""
    win_rate: float          # W
    loss_rate: float         # L = 1 - W
    avg_profit: float        # R_W  ($/lot)
    avg_loss: float          # R_L  ($/lot)
    expected_value: float    # 𝔼[V]  ($/lot)
    risk_reward_ratio: float # R_W / R_L
    is_positive_ev: bool     # 𝔼[V] > 0


@dataclass
class KellyResult:
    """Result from Kelly Criterion sizing (Slide 2)."""
    full_kelly_fraction: float   # f*
    half_kelly_fraction: float   # f*/2  (used in practice)
    capped_fraction: float       # min(half_kelly, hard_cap)
    capital_to_use: float        # balance × capped_fraction  ($)
    recommended_lots: float      # capital_to_use / gold_price


@dataclass
class SizingDecision:
    """Full output handed to router.py / risk_manager.py."""
    action: str
    quantity: float              # lots — ready for TradeDecision
    reasoning: str
    ev: EVResult
    kelly: KellyResult


# ---------------------------------------------------------------------------
# PositionSizer
# ---------------------------------------------------------------------------
class PositionSizer:
    """
    Translates a Phase 2 final_decision dict into a sized trade.

    Parameters
    ----------
    balance      : Portfolio balance in USD (default 100,000).
    hard_cap_pct : Maximum fraction allowed by RiskManager (default 10 %).
    half_kelly   : Use Half-Kelly to reduce volatility (default True).
    min_ev       : Reject trade if 𝔼[V] is below this threshold (default 0).
    """

    def __init__(
        self,
        balance: float = 100_000.0,
        hard_cap_pct: float = 0.10,
        half_kelly: bool = True,
        min_ev: float = 0.0,
    ):
        self.balance = balance
        self.hard_cap_pct = hard_cap_pct
        self.half_kelly = half_kelly
        self.min_ev = min_ev

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process(self, phase2_decision: dict) -> SizingDecision | None:
        """
        Main entry point.  Pass in the ``final_decision`` dict from Phase 2.

        Returns a SizingDecision ready for router.py, or None if the trade
        has negative EV and should be skipped.

        Expected keys in phase2_decision
        ---------------------------------
        signal       : "BUY" | "SELL" | "HOLD"
        confidence   : float  0‥1   (used as win-rate W)
        entry_price  : float  ($/lot)
        stop_loss    : float  ($/lot)
        take_profit  : float  ($/lot)
        rationale    : str    (optional)
        """
        signal      = phase2_decision.get("signal", "HOLD").upper()
        confidence  = float(phase2_decision.get("confidence", 0.5))
        entry       = float(phase2_decision.get("entry_price", 0))
        stop_loss   = float(phase2_decision.get("stop_loss", 0))
        take_profit = float(phase2_decision.get("take_profit", 0))
        rationale   = phase2_decision.get("rationale", "")

        # --- derive R_W and R_L from price levels ---
        r_w = abs(take_profit - entry)   # avg profit / lot
        r_l = abs(entry - stop_loss)     # avg loss  / lot

        if r_l == 0:
            logger.warning("[PositionSizer] stop_loss == entry_price; cannot size.")
            return None

        # --- Slide 1: Expected Value ---
        ev = self._calc_ev(win_rate=confidence, r_w=r_w, r_l=r_l)
        logger.info(
            f"[PositionSizer] EV = ${ev.expected_value:.4f}/lot  "
            f"(W={ev.win_rate}, R_W={r_w:.2f}, R_L={r_l:.2f})"
        )

        if ev.expected_value <= self.min_ev:
            logger.warning(
                f"[PositionSizer] Non-positive EV ({ev.expected_value:.4f}) "
                "— trade rejected."
            )
            return None

        # --- Slide 2: Kelly Criterion ---
        kelly = self._calc_kelly(
            win_rate=confidence,
            r_w=r_w,
            r_l=r_l,
            gold_price=entry,
        )
        logger.info(
            f"[PositionSizer] Full Kelly={kelly.full_kelly_fraction:.4f}  "
            f"Half Kelly={kelly.half_kelly_fraction:.4f}  "
            f"Capped={kelly.capped_fraction:.4f}  "
            f"Lots={kelly.recommended_lots:.2f}"
        )

        reasoning = (
            f"EV=${ev.expected_value:.2f}/lot | "
            f"R:R={ev.risk_reward_ratio:.2f} | "
            f"Half-Kelly={kelly.half_kelly_fraction:.2%} → "
            f"capped at {kelly.capped_fraction:.2%} → "
            f"{kelly.recommended_lots:.2f} lots | "
            f"Original rationale: {rationale}"
        )

        return SizingDecision(
            action=signal,
            quantity=kelly.recommended_lots,
            reasoning=reasoning,
            ev=ev,
            kelly=kelly,
        )

    def to_router_dict(self, sizing: SizingDecision) -> dict:
        """Convert SizingDecision → dict accepted by TradeRouter.route()."""
        return {
            "action":    sizing.action,
            "quantity":  sizing.quantity,
            "reasoning": sizing.reasoning,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _calc_ev(self, win_rate: float, r_w: float, r_l: float) -> EVResult:
        """
        Slide 1 formula:
            𝔼[V] = (W × R_W) − (L × R_L)
        """
        loss_rate = 1.0 - win_rate
        ev = (win_rate * r_w) - (loss_rate * r_l)
        rr = r_w / r_l if r_l else float("inf")
        return EVResult(
            win_rate=win_rate,
            loss_rate=loss_rate,
            avg_profit=r_w,
            avg_loss=r_l,
            expected_value=round(ev, 6),
            risk_reward_ratio=round(rr, 4),
            is_positive_ev=ev > self.min_ev,
        )

    def _calc_kelly(
        self,
        win_rate: float,
        r_w: float,
        r_l: float,
        gold_price: float,
    ) -> KellyResult:
        """
        Slide 2 formula:
            f* = W − (1 − W) / R        where R = R_W / R_L
            practical fraction = f*/2   (Half-Kelly)
            capped at hard_cap_pct
        """
        R = r_w / r_l
        full_kelly = win_rate - (1.0 - win_rate) / R
        full_kelly = max(full_kelly, 0.0)          # never negative

        half_kelly = full_kelly / 2.0 if self.half_kelly else full_kelly

        capped = min(half_kelly, self.hard_cap_pct)

        capital = self.balance * capped
        lots = round(capital / gold_price, 2) if gold_price > 0 else 0.0

        return KellyResult(
            full_kelly_fraction=round(full_kelly, 6),
            half_kelly_fraction=round(half_kelly, 6),
            capped_fraction=round(capped, 6),
            capital_to_use=round(capital, 2),
            recommended_lots=lots,
        )