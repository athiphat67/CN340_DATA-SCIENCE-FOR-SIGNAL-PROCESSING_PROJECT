"""
backtest/llm_pricing.py
ราคา token แบบง่ายสำหรับคำนวณต้นทุน backtest เป็น USD
อ้างอิงราคาจากหน้า pricing/model docs ทางการของแต่ละ provider
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPricing:
    provider: str
    model_match: str
    input_per_million_usd: float
    output_per_million_usd: float
    source_url: str


@dataclass(frozen=True)
class TokenCostEstimate:
    provider: str
    model: str
    pricing: TokenPricing | None
    prompt_tokens: int
    completion_tokens: int

    @property
    def input_cost_usd(self) -> float:
        if not self.pricing:
            return 0.0
        return round(
            (self.prompt_tokens / 1_000_000) * self.pricing.input_per_million_usd,
            6,
        )

    @property
    def output_cost_usd(self) -> float:
        if not self.pricing:
            return 0.0
        return round(
            (self.completion_tokens / 1_000_000) * self.pricing.output_per_million_usd,
            6,
        )

    @property
    def total_cost_usd(self) -> float:
        return round(self.input_cost_usd + self.output_cost_usd, 6)


_PRICING_RULES: dict[str, list[TokenPricing]] = {
    "gemini": [
        TokenPricing(
            provider="gemini",
            model_match="gemini-2.5-flash-lite-preview-09-2025",
            input_per_million_usd=0.10,
            output_per_million_usd=0.40,
            source_url="https://ai.google.dev/gemini-api/docs/pricing",
        ),
        TokenPricing(
            provider="gemini",
            model_match="gemini-2.5-flash-lite",
            input_per_million_usd=0.10,
            output_per_million_usd=0.40,
            source_url="https://ai.google.dev/gemini-api/docs/pricing",
        ),
        TokenPricing(
            provider="gemini",
            model_match="gemini-2.5-flash",
            input_per_million_usd=0.30,
            output_per_million_usd=2.50,
            source_url="https://ai.google.dev/gemini-api/docs/pricing",
        ),
        TokenPricing(
            provider="gemini",
            model_match="gemini-2.0-flash-lite",
            input_per_million_usd=0.075,
            output_per_million_usd=0.30,
            source_url="https://ai.google.dev/gemini-api/docs/pricing",
        ),
        TokenPricing(
            provider="gemini",
            model_match="gemini-2.0-flash",
            input_per_million_usd=0.10,
            output_per_million_usd=0.40,
            source_url="https://ai.google.dev/gemini-api/docs/pricing",
        ),
    ],
    "groq": [
        TokenPricing(
            provider="groq",
            model_match="openai/gpt-oss-20b",
            input_per_million_usd=0.075,
            output_per_million_usd=0.30,
            source_url="https://console.groq.com/docs/model/openai/gpt-oss-20b",
        ),
        TokenPricing(
            provider="groq",
            model_match="openai/gpt-oss-120b",
            input_per_million_usd=0.15,
            output_per_million_usd=0.60,
            source_url="https://console.groq.com/docs/models",
        ),
        TokenPricing(
            provider="groq",
            model_match="meta-llama/llama-4-scout-17b-16e-instruct",
            input_per_million_usd=0.11,
            output_per_million_usd=0.34,
            source_url="https://console.groq.com/docs/model/llama-4-scout-17b-16e-instruct",
        ),
        TokenPricing(
            provider="groq",
            model_match="llama-3.3-70b-specdec",
            input_per_million_usd=0.59,
            output_per_million_usd=0.99,
            source_url="https://console.groq.com/docs/model/llama-3.3-70b-specdec",
        ),
        TokenPricing(
            provider="groq",
            model_match="llama-3.3-70b-versatile",
            input_per_million_usd=0.59,
            output_per_million_usd=0.79,
            source_url="https://console.groq.com/docs/model/llama-3.3-70b-versatile",
        ),
    ],
    "openai": [
        TokenPricing(
            provider="openai",
            model_match="gpt-4o-mini",
            input_per_million_usd=0.15,
            output_per_million_usd=0.60,
            source_url="https://developers.openai.com/api/docs/models/gpt-4o-mini",
        ),
        TokenPricing(
            provider="openai",
            model_match="gpt-4o",
            input_per_million_usd=2.50,
            output_per_million_usd=10.00,
            source_url="https://developers.openai.com/api/docs/models/gpt-4o",
        ),
        TokenPricing(
            provider="openai",
            model_match="gpt-5-mini",
            input_per_million_usd=0.25,
            output_per_million_usd=2.00,
            source_url="https://openai.com/api/pricing/",
        ),
        TokenPricing(
            provider="openai",
            model_match="gpt-5",
            input_per_million_usd=2.50,
            output_per_million_usd=15.00,
            source_url="https://openai.com/api/pricing/",
        ),
    ],
    "claude": [
        TokenPricing(
            provider="claude",
            model_match="claude-opus-4-1",
            input_per_million_usd=15.00,
            output_per_million_usd=75.00,
            source_url="https://www.anthropic.com/pricing",
        ),
        TokenPricing(
            provider="claude",
            model_match="claude-opus-4.1",
            input_per_million_usd=15.00,
            output_per_million_usd=75.00,
            source_url="https://www.anthropic.com/pricing",
        ),
        TokenPricing(
            provider="claude",
            model_match="claude-sonnet-4",
            input_per_million_usd=3.00,
            output_per_million_usd=15.00,
            source_url="https://www.anthropic.com/pricing",
        ),
        TokenPricing(
            provider="claude",
            model_match="claude-3-5-haiku",
            input_per_million_usd=0.80,
            output_per_million_usd=4.00,
            source_url="https://www.anthropic.com/pricing",
        ),
    ],
    "deepseek": [
        TokenPricing(
            provider="deepseek",
            model_match="deepseek-chat",
            input_per_million_usd=0.28,
            output_per_million_usd=0.42,
            source_url="https://api-docs.deepseek.com/quick_start/pricing/",
        ),
        TokenPricing(
            provider="deepseek",
            model_match="deepseek-reasoner",
            input_per_million_usd=0.55,
            output_per_million_usd=2.19,
            source_url="https://api-docs.deepseek.com/quick_start/pricing-details-usd",
        ),
    ],
}


def get_token_pricing(provider: str, model: str) -> TokenPricing | None:
    provider_key = provider.strip().lower()
    model_key = model.strip().lower()
    candidates = _PRICING_RULES.get(provider_key, [])

    for pricing in candidates:
        if model_key == pricing.model_match.lower():
            return pricing

    for pricing in candidates:
        if model_key.startswith(pricing.model_match.lower()):
            return pricing

    return None


def estimate_token_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> TokenCostEstimate:
    return TokenCostEstimate(
        provider=provider,
        model=model,
        pricing=get_token_pricing(provider=provider, model=model),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
