"""
aggregator.py
-------------
Merges NLP sentiment signals and quantitative math signals into a single
weighted feature vector passed to orchestrator.py.

Default weights come from input.json math_overrides.custom_weights.
The final composite score is in [-1, +1]:
  +1 = maximum bullish conviction → predict price rise
  -1 = maximum bearish conviction → predict price fall
"""

from dataclasses import dataclass
from nlp_signals import NLPResult
from math_signals import MathSignals


# ---------------------------------------------------------------------------
# Default weights (overridden by input.json)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "sentiment_score":   0.25,
    "dxy_signal":        0.20,
    "yield_signal":      0.20,
    "momentum_signal":   0.15,
    "volatility_signal": 0.10,
    "etf_flow_signal":   0.10,
}

# Signals not in custom_weights are included with equal share of remainder
EXTENDED_SIGNALS = ["rsi_signal", "z_score_signal"]


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

@dataclass
class FeatureVector:
    # Raw named signals
    sentiment_score:   float
    dxy_signal:        float
    yield_signal:      float
    momentum_signal:   float
    volatility_signal: float
    etf_flow_signal:   float
    rsi_signal:        float
    z_score_signal:    float

    # Weights applied
    weights_used: dict[str, float]

    # Final composite score
    composite_score: float          # [-1, +1]
    composite_direction: str        # "bullish" | "bearish" | "neutral"
    conviction_level: str           # "high" | "medium" | "low"

    # Metadata for the orchestrator
    dominant_theme: str
    signal_summary: dict[str, float]


def _direction(score: float) -> str:
    if score > 0.05:
        return "bullish"
    if score < -0.05:
        return "bearish"
    return "neutral"


def _conviction(score: float) -> str:
    abs_score = abs(score)
    if abs_score >= 0.55:
        return "high"
    if abs_score >= 0.30:
        return "medium"
    return "low"


def _normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    """Ensure weights sum to 1.0."""
    total = sum(weights.values())
    if total == 0:
        return weights
    return {k: v / total for k, v in weights.items()}


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------

def build_feature_vector(
    nlp: NLPResult,
    math: MathSignals,
    custom_weights: dict[str, float] | None = None,
) -> FeatureVector:
    """
    Combine all signals into a weighted FeatureVector.

    Args:
        nlp:            NLPResult from nlp_signals.extract_nlp_signals()
        math:           MathSignals from math_signals.compute_math_signals()
        custom_weights: Optional weight overrides from input.json

    Returns:
        FeatureVector ready for orchestrator.py
    """
    # Resolve weights
    weights = dict(custom_weights) if custom_weights else dict(DEFAULT_WEIGHTS)

    # If extended signals not covered by custom_weights, distribute remainder
    covered = set(weights.keys())
    missing = [s for s in EXTENDED_SIGNALS if s not in covered]
    if missing:
        remainder = max(0.0, 1.0 - sum(weights.values()))
        share = remainder / len(missing) if missing else 0.0
        for sig in missing:
            weights[sig] = share

    weights = _normalise_weights(weights)

    # Collect signal values
    signal_values: dict[str, float] = {
        "sentiment_score":   nlp.composite_sentiment,
        "dxy_signal":        math.dxy_signal,
        "yield_signal":      math.yield_signal,
        "momentum_signal":   math.momentum_signal,
        "volatility_signal": math.volatility_signal,
        "etf_flow_signal":   math.etf_flow_signal,
        "rsi_signal":        math.rsi_signal,
        "z_score_signal":    math.z_score_signal,
    }

    # Weighted composite
    composite = sum(
        signal_values.get(name, 0.0) * weight
        for name, weight in weights.items()
    )
    composite = max(-1.0, min(1.0, composite))

    return FeatureVector(
        sentiment_score   = nlp.composite_sentiment,
        dxy_signal        = math.dxy_signal,
        yield_signal      = math.yield_signal,
        momentum_signal   = math.momentum_signal,
        volatility_signal = math.volatility_signal,
        etf_flow_signal   = math.etf_flow_signal,
        rsi_signal        = math.rsi_signal,
        z_score_signal    = math.z_score_signal,
        weights_used      = weights,
        composite_score   = round(composite, 4),
        composite_direction = _direction(composite),
        conviction_level  = _conviction(composite),
        dominant_theme    = nlp.dominant_theme,
        signal_summary    = {k: round(v, 4) for k, v in signal_values.items()},
    )


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from parser import load_input
    from nlp_signals import extract_nlp_signals
    from math_signals import compute_math_signals

    path = sys.argv[1] if len(sys.argv) > 1 else "input.json"
    parsed = load_input(path)

    nlp    = extract_nlp_signals(parsed.news)
    math   = compute_math_signals(
        parsed.market_state,
        parsed.historical_prices,
        parsed.current_price_usd,
    )
    fv = build_feature_vector(
        nlp, math,
        custom_weights=parsed.math_overrides.custom_weights,
    )

    print(f"\n[aggregator] Composite score : {fv.composite_score:+.4f}")
    print(f"[aggregator] Direction       : {fv.composite_direction.upper()}")
    print(f"[aggregator] Conviction      : {fv.conviction_level.upper()}")
    print(f"[aggregator] Dominant theme  : {fv.dominant_theme}")
    print("\n[aggregator] Signal breakdown:")
    for sig, val in fv.signal_summary.items():
        w = fv.weights_used.get(sig, 0.0)
        contribution = val * w
        bar = "█" * int(abs(contribution) * 50)
        print(f"  {sig:<22} val={val:+.3f}  w={w:.2f}  contrib={contribution:+.4f}  {bar}")