"""
execution/risk_manager.py
Enforces position-sizing and portfolio-level risk rules.
"""

import logging

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(
        self,
        balance: float = 100_000.0,
        max_pos_pct: float = 0.10,   # 10 % of portfolio per trade
        gold_price: float = 2_300.0, # updated externally each cycle
    ):
        self.balance = balance
        self.max_pos_pct = max_pos_pct
        self.gold_price = gold_price  # price of 1 troy-oz / 1 lot

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_gold_price(self, price: float) -> None:
        """Call this before validate_trade so the check uses the live price."""
        self.gold_price = price

    def validate_trade(self, decision: dict) -> tuple[bool, str]:
        action = decision.get("action", "").upper()
        quantity = decision.get("quantity", 0)

        # --- Basic field checks ---
        if action not in ("BUY", "SELL", "HOLD"):
            return False, f"Unknown action: {action!r}"

        if not isinstance(quantity, (int, float)) or quantity < 0:
            return False, "quantity must be a non-negative number"

        # HOLD with any quantity is fine
        if action == "HOLD":
            return True, "HOLD — no position taken"

        # --- Position-size check ---
        order_value = quantity * self.gold_price
        max_allowed = self.balance * self.max_pos_pct

        if order_value > max_allowed:
            return (
                False,
                (
                    f"Order value ${order_value:,.2f} exceeds "
                    f"{self.max_pos_pct * 100:.0f}% risk limit "
                    f"(${max_allowed:,.2f})"
                ),
            )

        # --- Zero-quantity guard ---
        if quantity == 0:
            return False, f"Cannot {action} 0 lots"

        logger.debug(
            f"[RiskManager] {action} {quantity} lots @ ${self.gold_price:,.2f} "
            f"= ${order_value:,.2f} (limit ${max_allowed:,.2f}) ✓"
        )
        return True, "Trade validated"

    def max_lots(self) -> float:
        """Convenience: how many lots can we trade at current price?"""
        return (self.balance * self.max_pos_pct) / self.gold_price
