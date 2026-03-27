"""
backtest/llm_signal_generator.py
สร้างสัญญาณ BUY/SELL/HOLD จาก LLM โดยใช้ข้อมูลย้อนหลังจริงทีละวัน
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass

import pandas as pd

from agent_core.llm.client import LLMCallResult, LLMClientFactory, PromptPackage
from backtest.llm_pricing import estimate_token_cost, get_token_pricing
from backtest.portfolio_engine import PortfolioSignal

logger = logging.getLogger(__name__)


@dataclass
class UsageSummary:
    """สรุปการใช้ token ของการรัน backtest 1 รอบ"""

    provider: str
    model: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    last_error: str = ""

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return round(self.total_latency_ms / self.successful_calls, 2)

    @property
    def pricing(self):
        return get_token_pricing(provider=self.provider, model=self.model)

    @property
    def input_cost_usd(self) -> float:
        return estimate_token_cost(
            provider=self.provider,
            model=self.model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        ).input_cost_usd

    @property
    def output_cost_usd(self) -> float:
        return estimate_token_cost(
            provider=self.provider,
            model=self.model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        ).output_cost_usd

    @property
    def total_cost_usd(self) -> float:
        return estimate_token_cost(
            provider=self.provider,
            model=self.model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        ).total_cost_usd

    @property
    def pricing_source(self) -> str:
        pricing = self.pricing
        return pricing.source_url if pricing else ""

    @property
    def pricing_available(self) -> bool:
        return self.pricing is not None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["avg_latency_ms"] = self.avg_latency_ms
        data["pricing_available"] = self.pricing_available
        data["input_cost_usd"] = self.input_cost_usd
        data["output_cost_usd"] = self.output_cost_usd
        data["total_cost_usd"] = self.total_cost_usd
        data["pricing_source"] = self.pricing_source
        return data


class LLMBacktestSignalGenerator:
    """
    สร้าง signal รายวันจาก LLM พร้อมสะสม usage metadata
    """

    def __init__(
        self,
        provider: str,
        model: str | None = None,
        temperature: float = 0.2,
        lookback_bars: int = 10,
        use_mock: bool = False,
    ):
        kwargs: dict = {}
        if model:
            kwargs["model"] = model
        if provider in {"openai", "groq", "deepseek"}:
            kwargs["temperature"] = temperature
        if provider == "gemini" and use_mock:
            kwargs["use_mock"] = True

        self.provider = provider
        self.client = LLMClientFactory.create(provider, **kwargs)
        self.model = getattr(self.client, "model", model or provider)
        self.lookback_bars = max(3, lookback_bars)
        self.usage_summary = UsageSummary(provider=provider, model=self.model)
        self.call_records: list[LLMCallResult] = []

    def generate_signals(
        self,
        train_data: pd.DataFrame,
        test_data: pd.DataFrame,
    ) -> tuple[list[PortfolioSignal], UsageSummary]:
        """
        สร้าง signal รายวัน โดยให้โมเดลเห็นข้อมูลถึงวันปัจจุบันเท่านั้น
        """
        all_data = (
            pd.concat([train_data, test_data], ignore_index=True)
            .sort_values("date")
            .reset_index(drop=True)
        )

        signals: list[PortfolioSignal] = []
        has_position = False

        for _, row in test_data.iterrows():
            as_of_date = pd.to_datetime(row["date"])
            visible_data = all_data[all_data["date"] <= as_of_date].tail(self.lookback_bars)
            prompt = self._build_prompt(visible_data, has_position)

            self.usage_summary.total_calls += 1
            try:
                result = self.client.call_with_metadata(prompt)
                self.call_records.append(result)
                self._accumulate_usage(result)
                parsed = self._extract_json(result.text)
                signal_type, confidence, rationale = self._normalise_decision(
                    parsed,
                    has_position=has_position,
                )
                self.usage_summary.successful_calls += 1
            except Exception as exc:
                logger.warning(
                    "[LLMBacktestSignalGenerator] %s failed on %s: %s",
                    self.provider,
                    as_of_date.date(),
                    exc,
                )
                self.usage_summary.failed_calls += 1
                signal_type = "HOLD"
                confidence = 0.0
                rationale = f"LLM fallback HOLD: {exc}"

            signals.append(
                PortfolioSignal(
                    date=as_of_date.strftime("%Y-%m-%d"),
                    signal=signal_type,
                    confidence=confidence,
                    model_name=self.provider,
                    rationale=rationale,
                )
            )

            if signal_type == "BUY":
                has_position = True
            elif signal_type == "SELL":
                has_position = False

        return signals, self.usage_summary

    def _accumulate_usage(self, result: LLMCallResult) -> None:
        self.usage_summary.prompt_tokens += result.prompt_tokens
        self.usage_summary.completion_tokens += result.completion_tokens
        self.usage_summary.total_tokens += result.total_tokens
        self.usage_summary.total_latency_ms += result.latency_ms

    def _build_prompt(self, visible_data: pd.DataFrame, has_position: bool) -> PromptPackage:
        features = self._compute_features(visible_data)
        recent_rows = []
        for _, row in visible_data.tail(5).iterrows():
            recent_rows.append(
                {
                    "date": pd.to_datetime(row["date"]).strftime("%Y-%m-%d"),
                    "price_per_gram": round(float(row["price_per_gram"]), 2),
                    "xau_close": round(float(row["xau_close"]), 2),
                    "usdthb": round(float(row["usdthb"]), 4),
                }
            )

        position_state = "LONG" if has_position else "FLAT"
        allowed_signals = ["SELL", "HOLD"] if has_position else ["BUY", "HOLD"]

        system = (
            "You are a disciplined gold trading analyst running a backtest. "
            "You can only use information provided in the prompt. "
            "Return exactly one JSON object with keys: signal, confidence, rationale. "
            "Signal must be one of BUY, SELL, HOLD."
        )
        user = (
            f"As-of date: {features['as_of_date']}\n"
            f"Portfolio state: {position_state}\n"
            f"Allowed signals today: {', '.join(allowed_signals)}\n"
            "Instrument: Gold priced in THB per gram.\n"
            "Make one trading decision for today only.\n"
            "Prefer HOLD when signals are mixed.\n\n"
            "Latest computed features:\n"
            f"{json.dumps(features, ensure_ascii=False, indent=2)}\n\n"
            "Recent visible bars:\n"
            f"{json.dumps(recent_rows, ensure_ascii=False, indent=2)}\n\n"
            "Return JSON only. Example:\n"
            '{"signal":"HOLD","confidence":0.55,"rationale":"short reason"}'
        )
        return PromptPackage(system=system, user=user, step_label="BACKTEST_SIGNAL")

    def _compute_features(self, visible_data: pd.DataFrame) -> dict:
        frame = visible_data.copy().reset_index(drop=True)
        frame["return_pct"] = frame["price_per_gram"].pct_change() * 100
        frame["sma_5"] = frame["price_per_gram"].rolling(5).mean()
        frame["sma_10"] = frame["price_per_gram"].rolling(10).mean()

        latest = frame.iloc[-1]
        prev_price = float(frame["price_per_gram"].iloc[-2]) if len(frame) > 1 else float(latest["price_per_gram"])
        momentum_base = float(frame["price_per_gram"].iloc[-6]) if len(frame) > 5 else prev_price
        volatility_window = frame["return_pct"].tail(5).dropna()

        return {
            "as_of_date": pd.to_datetime(latest["date"]).strftime("%Y-%m-%d"),
            "price_per_gram": round(float(latest["price_per_gram"]), 2),
            "xau_close": round(float(latest["xau_close"]), 2),
            "usdthb": round(float(latest["usdthb"]), 4),
            "daily_return_pct": round(
                ((float(latest["price_per_gram"]) / prev_price) - 1) * 100 if prev_price else 0.0,
                3,
            ),
            "momentum_5d_pct": round(
                ((float(latest["price_per_gram"]) / momentum_base) - 1) * 100 if momentum_base else 0.0,
                3,
            ),
            "sma_5": round(float(latest["sma_5"]), 2) if pd.notna(latest["sma_5"]) else None,
            "sma_10": round(float(latest["sma_10"]), 2) if pd.notna(latest["sma_10"]) else None,
            "volatility_5d_pct": round(float(volatility_window.std()), 3)
            if not volatility_window.empty
            else 0.0,
        }

    @staticmethod
    def _extract_json(raw_text: str) -> dict:
        try:
            return json.loads(raw_text.strip())
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        if fenced:
            try:
                return json.loads(fenced.group(1).strip())
            except json.JSONDecodeError:
                pass

        brace = re.search(r"\{[\s\S]*\}", raw_text)
        if brace:
            try:
                return json.loads(brace.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Unable to parse JSON from LLM response: {raw_text[:200]}")

    @staticmethod
    def _normalise_decision(parsed: dict, has_position: bool) -> tuple[str, float, str]:
        signal = str(parsed.get("signal", "HOLD")).upper().strip()
        confidence = parsed.get("confidence", 0.0)
        rationale = str(parsed.get("rationale", "")).strip()

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        if signal not in {"BUY", "SELL", "HOLD"}:
            signal = "HOLD"

        if not has_position and signal == "SELL":
            signal = "HOLD"
            rationale = rationale or "SELL blocked because portfolio is flat"
        elif has_position and signal == "BUY":
            signal = "HOLD"
            rationale = rationale or "BUY blocked because portfolio is already long"

        if not rationale:
            rationale = "No rationale provided"

        return signal, confidence, rationale
