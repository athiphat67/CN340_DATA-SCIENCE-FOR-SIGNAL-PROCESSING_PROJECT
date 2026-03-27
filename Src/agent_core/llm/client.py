from __future__ import annotations

import math
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class PromptPackage:
    """ข้อมูล prompt ที่ใช้ร่วมกันทุก provider"""

    system: str
    user: str
    step_label: str


@dataclass
class LLMCallResult:
    """ผลลัพธ์การเรียก LLM พร้อม usage metadata"""

    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    step_label: str = ""
    raw_usage: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMException(Exception):
    """Base exception สำหรับ LLM errors ทุกชนิด"""

    pass


class LLMProviderError(LLMException):
    """เกิดจาก API error ของ provider"""

    pass


class LLMUnavailableError(LLMException):
    """Provider ไม่พร้อมใช้งาน (missing key, no connection)"""

    pass


# ---------------------------------------------------------------------------
# Abstract Base Class
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """
    Abstract base class สำหรับ LLM provider ทุกตัว

    Contract:
    - call()               → รับ PromptPackage, คืน str (JSON expected)
    - call_with_metadata() → คืนข้อความพร้อม usage metadata
    - is_available()       → ตรวจสอบว่า client พร้อมใช้งาน
    """

    PROVIDER_NAME = "unknown"

    @abstractmethod
    def call(self, prompt_package: PromptPackage) -> str:
        """
        ส่ง prompt ไปยัง LLM และรับ response กลับมา

        Args:
            prompt_package: PromptPackage ที่มี system, user, step_label

        Returns:
            str: raw text response จาก LLM

        Raises:
            LLMProviderError: เมื่อ API call ล้มเหลว
            LLMUnavailableError: เมื่อ client ไม่พร้อม
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        ตรวจสอบว่า LLM client พร้อมใช้งานหรือไม่

        Returns:
            bool: True ถ้าพร้อม, False ถ้าไม่พร้อม
        """
        ...

    def call_with_metadata(self, prompt_package: PromptPackage) -> LLMCallResult:
        """
        Default implementation สำหรับ provider ที่ยังไม่มี usage จาก SDK
        จะ fallback เป็นการ estimate token จากความยาวข้อความ
        """
        started_at = time.perf_counter()
        text = self.call(prompt_package)
        latency_ms = (time.perf_counter() - started_at) * 1000

        prompt_tokens = self._estimate_tokens(
            f"{prompt_package.system}\n\n{prompt_package.user}"
        )
        completion_tokens = self._estimate_tokens(text)

        return LLMCallResult(
            text=text,
            provider=self.provider_name,
            model=self.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=round(latency_ms, 2),
            step_label=prompt_package.step_label,
            raw_usage={"source": "estimated"},
        )

    @property
    def provider_name(self) -> str:
        return getattr(self, "PROVIDER_NAME", self.__class__.__name__.lower())

    @property
    def model_name(self) -> str:
        return str(getattr(self, "model", self.__class__.__name__))

    def _build_result(
        self,
        prompt_package: PromptPackage,
        text: str,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        raw_usage: Optional[dict[str, Any]] = None,
    ) -> LLMCallResult:
        if total_tokens <= 0:
            total_tokens = prompt_tokens + completion_tokens

        return LLMCallResult(
            text=text,
            provider=self.provider_name,
            model=self.model_name,
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            total_tokens=max(0, total_tokens),
            latency_ms=round(latency_ms, 2),
            step_label=prompt_package.step_label,
            raw_usage=raw_usage or {},
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4))

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _safe_usage_dict(cls, usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if isinstance(usage, dict):
            return dict(usage)
        if hasattr(usage, "model_dump"):
            return usage.model_dump()
        if hasattr(usage, "to_dict"):
            return usage.to_dict()

        data: dict[str, Any] = {}
        for name in dir(usage):
            if name.startswith("_"):
                continue
            value = getattr(usage, name, None)
            if callable(value):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                data[name] = value
        return data

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} available={self.is_available()}>"


# ---------------------------------------------------------------------------
# Default mock responses
# ---------------------------------------------------------------------------


DEFAULT_MOCK_RESPONSES: dict[str, str] = {
    "THOUGHT_1": '{"action": "CALL_TOOL", "tool": "get_news", "params": {}}',
    "THOUGHT_2": '{"action": "CALL_TOOL", "tool": "run_calculator", "params": {"expression": "close / open"}}',
    "THOUGHT_3": '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.6, "rationale": "Insufficient signal"}',
    "THOUGHT_FINAL": '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.5, "rationale": "Mock final decision"}',
}


# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------


class MockClient(LLMClient):
    """
    LLM Client สำหรับ testing — ไม่เรียก API จริง

    ใช้ response_map เพื่อ map step_label → mock JSON response
    ถ้าไม่มี key ที่ตรง จะ fallback เป็น HOLD decision
    """

    def __init__(self, response_map: Optional[dict[str, str]] = None):
        """
        Args:
            response_map: dict[step_label, json_string]
                          ถ้า None ใช้ DEFAULT_MOCK_RESPONSES
        """
        self.response_map = (
            response_map if response_map is not None else DEFAULT_MOCK_RESPONSES
        )

    def call(self, prompt_package: PromptPackage) -> str:
        return self.response_map.get(
            prompt_package.step_label,
            '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.5, "rationale": "Mock fallback"}',
        )

    def call_with_metadata(self, prompt_package: PromptPackage) -> LLMCallResult:
        text = self.call(prompt_package)
        prompt_tokens = self._estimate_tokens(
            f"{prompt_package.system}\n\n{prompt_package.user}"
        )
        completion_tokens = self._estimate_tokens(text)
        return self._build_result(
            prompt_package=prompt_package,
            text=text,
            latency_ms=0.0,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw_usage={"source": "mock-estimated"},
        )

    def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Concrete Implementations
# ---------------------------------------------------------------------------


class GeminiClient(LLMClient):
    """
    LLM Client สำหรับ Google Gemini API
    รองรับ mock mode สำหรับ testing
    """

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        use_mock: bool = False,
    ):
        self.model = model
        self.use_mock = use_mock
        self._client = None

        if not use_mock:
            try:
                from google import genai  # type: ignore

                self._client = genai.Client(
                    api_key=api_key or os.environ["GEMINI_API_KEY"]
                )
            except KeyError:
                raise LLMUnavailableError(
                    "GEMINI_API_KEY not found. Set env var or pass api_key."
                )
            except ImportError:
                raise LLMUnavailableError(
                    "google-genai package not installed. Run: pip install google-genai"
                )

    def call(self, prompt_package: PromptPackage) -> str:
        return self.call_with_metadata(prompt_package).text

    def call_with_metadata(self, prompt_package: PromptPackage) -> LLMCallResult:
        if self.use_mock:
            text = DEFAULT_MOCK_RESPONSES.get(
                prompt_package.step_label,
                '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.5, "rationale": "Mock fallback"}',
            )
            return self._build_result(
                prompt_package=prompt_package,
                text=text,
                latency_ms=0.0,
                prompt_tokens=self._estimate_tokens(
                    f"{prompt_package.system}\n\n{prompt_package.user}"
                ),
                completion_tokens=self._estimate_tokens(text),
                raw_usage={"source": "gemini-mock-estimated"},
            )

        if not self._client:
            raise LLMUnavailableError("GeminiClient is not initialized.")

        full_prompt = (
            f"SYSTEM:\n{prompt_package.system}\n\n"
            f"USER:\n{prompt_package.user}"
        )

        started_at = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=full_prompt,
            )
            return response.text
        except Exception as e:
            raise LLMProviderError(
                f"Gemini API error at {prompt_package.step_label}: {exc}"
            ) from exc

        latency_ms = (time.perf_counter() - started_at) * 1000
        text = getattr(response, "text", "") or ""
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = self._safe_int(getattr(usage, "prompt_token_count", 0))
        completion_tokens = self._safe_int(
            getattr(usage, "candidates_token_count", 0)
        )
        total_tokens = self._safe_int(getattr(usage, "total_token_count", 0))

        return self._build_result(
            prompt_package=prompt_package,
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_usage=self._safe_usage_dict(usage),
        )

    def is_available(self) -> bool:
        if self.use_mock:
            return True
        return self._client is not None

    def _mock_response(self, prompt_package: PromptPackage) -> str:
        """คืน mock response ตาม step_label"""
        return DEFAULT_MOCK_RESPONSES.get(
            prompt_package.step_label,
            '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.5, "rationale": "Mock fallback"}',
        )
        
class OpenAIClient(LLMClient):
    """LLM Client สำหรับ OpenAI API (GPT series)"""

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
    ):
        self.model = model
        self.temperature = temperature

        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        except KeyError:
            raise LLMUnavailableError(
                "OPENAI_API_KEY not found. Set env var or pass api_key."
            )
        except ImportError:
            raise LLMUnavailableError(
                "openai package not installed. Run: pip install openai"
            )

    def call(self, prompt_package: PromptPackage) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user", "content": prompt_package.user},
                ],
            )
        except Exception as exc:
            raise LLMProviderError(
                f"OpenAI API error at {prompt_package.step_label}: {exc}"
            ) from exc

        latency_ms = (time.perf_counter() - started_at) * 1000
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)

        return self._build_result(
            prompt_package=prompt_package,
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=self._safe_int(getattr(usage, "prompt_tokens", 0)),
            completion_tokens=self._safe_int(
                getattr(usage, "completion_tokens", 0)
            ),
            total_tokens=self._safe_int(getattr(usage, "total_tokens", 0)),
            raw_usage=self._safe_usage_dict(usage),
        )

    def is_available(self) -> bool:
        return self._client is not None


class ClaudeClient(LLMClient):
    """LLM Client สำหรับ Anthropic Claude API"""

    DEFAULT_MODEL = "claude-opus-4-1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
    ):
        self.model = model
        self.max_tokens = max_tokens

        try:
            from anthropic import Anthropic  # type: ignore

            self._client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        except KeyError:
            raise LLMUnavailableError(
                "ANTHROPIC_API_KEY not found. Set env var or pass api_key."
            )
        except ImportError:
            raise LLMUnavailableError(
                "anthropic package not installed. Run: pip install anthropic"
            )

    def call(self, prompt_package: PromptPackage) -> str:
        return self.call_with_metadata(prompt_package).text

    def call_with_metadata(self, prompt_package: PromptPackage) -> LLMCallResult:
        started_at = time.perf_counter()
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=prompt_package.system,
                messages=[{"role": "user", "content": prompt_package.user}],
            )
        except Exception as exc:
            raise LLMProviderError(
                f"Claude API error at {prompt_package.step_label}: {exc}"
            ) from exc

        latency_ms = (time.perf_counter() - started_at) * 1000
        text = response.content[0].text if response.content else ""
        usage = getattr(response, "usage", None)
        prompt_tokens = self._safe_int(getattr(usage, "input_tokens", 0))
        completion_tokens = self._safe_int(getattr(usage, "output_tokens", 0))

        return self._build_result(
            prompt_package=prompt_package,
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            raw_usage=self._safe_usage_dict(usage),
        )

    def is_available(self) -> bool:
        return self._client is not None


class GroqClient(LLMClient):
    """LLM Client สำหรับ Groq (LPU Inference Engine) - เน้นความเร็วสูง"""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.5,
        **kwargs,
    ):
        self.model = model
        self.temperature = temperature

        try:
            from groq import Groq  # type: ignore

            self._client = Groq(api_key=api_key or os.environ["GROQ_API_KEY"])
        except KeyError:
            raise LLMUnavailableError("GROQ_API_KEY not found in env.")
        except ImportError:
            raise LLMUnavailableError(
                "groq package not installed. Run: pip install groq"
            )

    def call(self, prompt_package: PromptPackage) -> str:
        return self.call_with_metadata(prompt_package).text

    def call_with_metadata(self, prompt_package: PromptPackage) -> LLMCallResult:
        started_at = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user", "content": prompt_package.user},
                ],
                model=self.model,
                temperature=self.temperature,
            )
        except Exception as exc:
            raise LLMProviderError(f"Groq API error: {exc}") from exc

        latency_ms = (time.perf_counter() - started_at) * 1000
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)

        return self._build_result(
            prompt_package=prompt_package,
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=self._safe_int(getattr(usage, "prompt_tokens", 0)),
            completion_tokens=self._safe_int(
                getattr(usage, "completion_tokens", 0)
            ),
            total_tokens=self._safe_int(getattr(usage, "total_tokens", 0)),
            raw_usage=self._safe_usage_dict(usage),
        )

    def is_available(self) -> bool:
        return self._client is not None


class DeepSeekClient(LLMClient):
    """LLM Client สำหรับ DeepSeek API - รองรับ OpenAI compatible format"""

    DEFAULT_MODEL = "deepseek-chat"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
    ):
        self.model = model
        self.temperature = temperature

        try:
            from openai import OpenAI
            # DeepSeek ใช้ OpenAI SDK ได้เลย แค่เปลี่ยน base_url
            self._client = OpenAI(
                api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
                base_url="https://api.deepseek.com"
            )
        except KeyError:
            raise LLMUnavailableError("DEEPSEEK_API_KEY not found in env.")
        except ImportError:
            raise LLMUnavailableError("openai package missing.")

    def call(self, prompt_package: PromptPackage) -> str:
        return self.call_with_metadata(prompt_package).text

    def call_with_metadata(self, prompt_package: PromptPackage) -> LLMCallResult:
        started_at = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user", "content": prompt_package.user},
                ],
                temperature=self.temperature,
                stream=False
            )
        except Exception as exc:
            raise LLMProviderError(f"DeepSeek API error: {exc}") from exc

        latency_ms = (time.perf_counter() - started_at) * 1000
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)

        return self._build_result(
            prompt_package=prompt_package,
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=self._safe_int(getattr(usage, "prompt_tokens", 0)),
            completion_tokens=self._safe_int(
                getattr(usage, "completion_tokens", 0)
            ),
            total_tokens=self._safe_int(getattr(usage, "total_tokens", 0)),
            raw_usage=self._safe_usage_dict(usage),
        )

    def is_available(self) -> bool:
        return self._client is not None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class LLMClientFactory:
    """
    Factory สำหรับสร้าง LLMClient ตามชื่อ provider

    Usage:
        client = LLMClientFactory.create("gemini")
        client = LLMClientFactory.create("gemini", use_mock=True)
        client = LLMClientFactory.create("openai", model="gpt-4o")
        client = LLMClientFactory.create("claude")
        client = LLMClientFactory.create("mock", response_map={...})
    """

    _REGISTRY: dict[str, type[LLMClient]] = {
        "gemini": GeminiClient,
        "openai": OpenAIClient,
        "claude": ClaudeClient,
        "mock": MockClient,
        "groq": GroqClient,
        "deepseek": DeepSeekClient,
    }

    @classmethod
    def create(cls, provider: str, **kwargs) -> LLMClient:
        """
        สร้าง LLMClient ตาม provider name

        Args:
            provider: "gemini" | "mock"
            **kwargs: (**kwargs => use_mock=True) ส่งต่อไปยัง constructor ของแต่ละ class
                      เช่น api_key, model, use_mock, response_map

        Returns:
            LLMClient instance ที่พร้อมใช้งาน

        Raises:
            ValueError: ถ้า provider ไม่รู้จัก
            LLMUnavailableError: ถ้า client สร้างไม่ได้ (key missing, package missing)
        """
        provider_lower = provider.lower().strip()

        if provider_lower not in cls._REGISTRY:
            available = ", ".join(cls._REGISTRY.keys())
            raise ValueError(f"Unknown provider: '{provider}'. Available: {available}")

        client_class = cls._REGISTRY[provider_lower]
        return client_class(**kwargs)

    @classmethod
    def available_providers(cls) -> list[str]:
        """คืนรายชื่อ provider ที่รองรับทั้งหมด"""
        return list(cls._REGISTRY.keys())

    @classmethod
    def register(cls, name: str, client_class: type[LLMClient]) -> None:
        """
        Register provider ใหม่ (Extensibility hook)

        Args:
            name: ชื่อ provider (lowercase)
            client_class: class ที่ extends LLMClient
        """
        if not issubclass(client_class, LLMClient):
            raise TypeError(f"{client_class} must be a subclass of LLMClient")
        cls._REGISTRY[name.lower()] = client_class
