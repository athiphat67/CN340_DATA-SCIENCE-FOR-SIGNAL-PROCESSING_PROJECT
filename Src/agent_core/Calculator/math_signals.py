"""
math_signals.py
---------------
Computes quantitative signals from market_state and historical_prices.
Each signal is normalised to [-1, +1] where:
  +1 = strong bullish pressure on gold
  -1 = strong bearish pressure on gold

Signals:
  dxy_signal       — dollar strength (inverse of gold)
  yield_signal     — US 10Y yield pressure (higher yield = bearish)
  momentum_signal  — price momentum across timeframes
  volatility_signal — market fear (VIX) → safe-haven demand
  etf_flow_signal  — ETF capital flows
  rsi_signal       — relative strength index (overbought/oversold)
  z_score_signal   — statistical deviation from 252d baseline
"""

import math
from dataclasses import dataclass
from parser import MarketState, HistoricalPrices


# ---------------------------------------------------------------------------
# Individual signal calculators
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def dxy_signal(market: MarketState) -> float:
    """
    DXY inverse signal.
    Baseline ~100. Each 1-point move ≈ 0.05 impact.
    Strong dollar (DXY >> 100) → bearish gold → negative signal.
    """
    baseline = 100.0
    deviation = market.dxy_index - baseline
    raw = -deviation * 0.05          # inverse relationship
    return _clamp(raw)


def yield_signal(market: MarketState) -> float:
    """
    US 10Y yield signal.
    Neutral zone ≈ 3.5%–4.5%. Above neutral = bearish (opportunity cost).
    """
    neutral = 4.0
    deviation = market.us10y_yield - neutral
    raw = -deviation * 0.4
    return _clamp(raw)


def momentum_signal(current: float, hist: HistoricalPrices) -> float:
    """
    Multi-timeframe momentum.
    Weighted blend: 1d (30%), 5d (30%), 20d (25%), 60d (15%).
    """
    def pct_return(base: float) -> float:
        if base == 0:
            return 0.0
        return (current - base) / base

    r1   = pct_return(hist.d1)
    r5   = pct_return(hist.d5)
    r20  = pct_return(hist.d20)
    r60  = pct_return(hist.d60)

    blended = (0.30 * r1) + (0.30 * r5) + (0.25 * r20) + (0.15 * r60)
    # Scale: ±10% move → ±1 signal
    raw = blended / 0.10
    return _clamp(raw)


def volatility_signal(market: MarketState) -> float:
    """
    VIX-based fear/safe-haven signal.
    VIX > 20 = fear → bullish gold. VIX < 15 = complacency → mildly bearish.
    Scaled around VIX = 18 neutral.
    """
    neutral_vix = 18.0
    deviation = market.vix - neutral_vix
    raw = deviation * 0.06
    return _clamp(raw)


def etf_flow_signal(market: MarketState) -> float:
    """
    Gold ETF net flow signal.
    ±$500M threshold for max signal. Positive inflow = bullish.
    """
    raw = market.gold_etf_flow_m_usd / 500.0
    return _clamp(raw)


def rsi_signal(current: float, hist: HistoricalPrices) -> float:
    """
    Simplified RSI approximation using available price snapshots.
    Uses 5d and 20d periods. RSI > 70 = overbought (bearish), < 30 = oversold (bullish).
    """
    gains_5d  = max(0, current - hist.d5)
    losses_5d = max(0, hist.d5 - current)

    gains_20d  = max(0, current - hist.d20)
    losses_20d = max(0, hist.d20 - current)

    # Blend periods
    avg_gain = (gains_5d + gains_20d) / 2
    avg_loss = (losses_5d + losses_20d) / 2

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    # Convert RSI to [-1, +1]: oversold → bullish, overbought → bearish
    raw = (50 - rsi) / 50.0   # 0=neutral, 30→+0.4 oversold, 70→-0.4 overbought
    return _clamp(raw)


def z_score_signal(current: float, hist: HistoricalPrices) -> float:
    """
    Z-score vs 252d baseline.
    Uses 252d price as mean proxy and derives stddev from 60d range.
    High positive z-score = extended above mean → mild bearish reversion pressure.
    """
    mean = hist.d252
    # Approximate stddev from 60d–252d price range
    stddev_proxy = abs(hist.d60 - hist.d252) / 2.0

    if stddev_proxy < 1.0:
        return 0.0

    z = (current - mean) / stddev_proxy
    # Invert: far above mean = bearish (mean reversion expectation)
    raw = -z / 3.0   # ±3 sigma → ±1 signal
    return _clamp(raw)


# ---------------------------------------------------------------------------
# Composite output
# ---------------------------------------------------------------------------

@dataclass
class MathSignals:
    dxy_signal: float
    yield_signal: float
    momentum_signal: float
    volatility_signal: float
    etf_flow_signal: float
    rsi_signal: float
    z_score_signal: float

    def to_dict(self) -> dict[str, float]:
        return {
            "dxy_signal":        self.dxy_signal,
            "yield_signal":      self.yield_signal,
            "momentum_signal":   self.momentum_signal,
            "volatility_signal": self.volatility_signal,
            "etf_flow_signal":   self.etf_flow_signal,
            "rsi_signal":        self.rsi_signal,
            "z_score_signal":    self.z_score_signal,
        }


def compute_math_signals(
    market: MarketState,
    hist: HistoricalPrices,
    current_price: float,
) -> MathSignals:
    """
    Compute all quantitative signals.

    Returns:
        MathSignals with each value in [-1, +1]
    """
    return MathSignals(
        dxy_signal        = dxy_signal(market),
        yield_signal      = yield_signal(market),
        momentum_signal   = momentum_signal(current_price, hist),
        volatility_signal = volatility_signal(market),
        etf_flow_signal   = etf_flow_signal(market),
        rsi_signal        = rsi_signal(current_price, hist),
        z_score_signal    = z_score_signal(current_price, hist),
    )


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from parser import load_input

    path = sys.argv[1] if len(sys.argv) > 1 else "input.json"
    parsed = load_input(path)
    signals = compute_math_signals(
        parsed.market_state,
        parsed.historical_prices,
        parsed.current_price_usd,
    )

    print("\n[math_signals] All signals (−1 bearish → +1 bullish):")
    for name, val in signals.to_dict().items():
        bar = "█" * int(abs(val) * 10)
        direction = "▲" if val >= 0 else "▼"
        print(f"  {name:<22} {direction} {val:+.4f}  {bar}")