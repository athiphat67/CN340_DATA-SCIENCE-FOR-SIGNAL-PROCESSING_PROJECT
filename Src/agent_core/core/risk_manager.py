"""
risk_manager.py — Validates and adjusts trading signals based on risk parameters.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Constants for risk limits
MIN_BUY_THB = 1000.0
MAX_DRAWDOWN_PCT = 0.05  # 5% max risk per trade
MAX_POSITION_SIZE_PCT = 1.0  # 100% of cash can be used by default

@dataclass
class RiskConfig:
    min_buy_thb: float = MIN_BUY_THB
    max_drawdown_pct: float = MAX_DRAWDOWN_PCT
    max_position_size_pct: float = MAX_POSITION_SIZE_PCT
    require_sl_tp: bool = False

class RiskManager:
    """
    Acts as a filter between the AI Agent's final decision and the execution/backtester.
    It ensures that trades comply with portfolio constraints and risk management rules.
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()

    def validate_and_adjust(self, decision: Dict[str, Any], portfolio_state: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """
        Validates the decision from the LLM.
        
        decision: output from ReactOrchestrator's final_decision
        portfolio_state: dict containing cash_balance, gold_grams, etc.
        current_price: current market price per gram (or oz) used for reference
        """
        signal = decision.get("signal", "HOLD").upper()
        if signal not in ("BUY", "SELL", "HOLD"):
            signal = "HOLD"

        adjusted_decision = decision.copy()
        adjusted_decision["signal"] = signal
        adjusted_decision["risk_adjusted"] = False
        adjusted_decision["risk_notes"] = []

        cash_balance = portfolio_state.get("cash_balance", 0.0)
        gold_grams = portfolio_state.get("gold_grams", 0.0)

        if signal == "BUY":
            # 1. Check Cash Balance Constraints
            if cash_balance < self.config.min_buy_thb:
                return self._reject_to_hold(adjusted_decision, f"Insufficient cash (฿{cash_balance:.2f} < ฿{self.config.min_buy_thb})")

            # 2. Determine Amount
            # If agent didn't specify amount, or specified too much, cap it at cash_balance * max_position_size_pct
            amount_thb = decision.get("amount_thb", cash_balance)
            if amount_thb is None:
                amount_thb = cash_balance
            
            max_allowed_buy = cash_balance * self.config.max_position_size_pct
            if amount_thb > max_allowed_buy:
                amount_thb = max_allowed_buy
                adjusted_decision["risk_adjusted"] = True
                adjusted_decision["risk_notes"].append(f"Capped buy amount to max allowed (฿{amount_thb:.2f})")

            if amount_thb < self.config.min_buy_thb:
                if cash_balance >= self.config.min_buy_thb:
                    amount_thb = self.config.min_buy_thb
                    adjusted_decision["risk_adjusted"] = True
                    adjusted_decision["risk_notes"].append(f"Increased buy amount to minimum required (฿{amount_thb:.2f})")
                else:
                    return self._reject_to_hold(adjusted_decision, "Buy amount < min and cannot be increased")

            adjusted_decision["amount_thb"] = amount_thb

            # 3. Validate Stop Loss / Take Profit (if present)
            entry_price = decision.get("entry_price") or current_price
            stop_loss = decision.get("stop_loss")
            take_profit = decision.get("take_profit")

            if self.config.require_sl_tp and (not stop_loss or not take_profit):
                return self._reject_to_hold(adjusted_decision, "Missing SL/TP which is required by RiskManager")

            if stop_loss:
                # For long spot, SL must be below entry
                if float(stop_loss) >= float(entry_price):
                    adjusted_decision["risk_adjusted"] = True
                    adjusted_decision["risk_notes"].append(f"Invalid SL ({stop_loss}) >= Entry ({entry_price}). Removing SL.")
                    adjusted_decision["stop_loss"] = None
                else:
                    # Check Max Drawdown
                    risk_pct = (float(entry_price) - float(stop_loss)) / float(entry_price)
                    if risk_pct > self.config.max_drawdown_pct:
                        adjusted_sl = float(entry_price) * (1 - self.config.max_drawdown_pct)
                        adjusted_decision["risk_adjusted"] = True
                        adjusted_decision["risk_notes"].append(f"SL risk ({risk_pct:.1%}) exceeded max ({self.config.max_drawdown_pct:.1%}). Adjusted SL to {adjusted_sl:.2f}")
                        adjusted_decision["stop_loss"] = adjusted_sl

            if take_profit:
                if float(take_profit) <= float(entry_price):
                    adjusted_decision["risk_adjusted"] = True
                    adjusted_decision["risk_notes"].append(f"Invalid TP ({take_profit}) <= Entry ({entry_price}). Removing TP.")
                    adjusted_decision["take_profit"] = None

        elif signal == "SELL":
            # 1. Check Gold Balance Constraints
            if gold_grams <= 0:
                return self._reject_to_hold(adjusted_decision, "No gold to sell")

            # 2. Determine Grams
            grams = decision.get("grams", gold_grams)
            if grams is None:
                grams = gold_grams
            
            if grams > gold_grams:
                grams = gold_grams
                adjusted_decision["risk_adjusted"] = True
                adjusted_decision["risk_notes"].append(f"Capped sell grams to max available ({grams:.4f}g)")

            adjusted_decision["grams"] = grams

        return adjusted_decision

    def _reject_to_hold(self, decision: Dict[str, Any], reason: str) -> Dict[str, Any]:
        decision["signal"] = "HOLD"
        decision["risk_adjusted"] = True
        decision["risk_notes"].append(f"Rejected to HOLD: {reason}")
        # Clean up action fields
        if "amount_thb" in decision:
            del decision["amount_thb"]
        if "grams" in decision:
            del decision["grams"]
        logger.warning(f"RiskManager rejected trade: {reason}")
        return decision
