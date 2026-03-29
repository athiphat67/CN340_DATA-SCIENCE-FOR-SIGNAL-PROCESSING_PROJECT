from __future__ import annotations

import os
import re
import json
import requests
from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from agent_core.core.prompt import PromptPackage
import time
from functools import wraps
from logger_setup import llm_logger, sys_logger, log_method

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
 
# Regex สำหรับ strip Qwen3 thinking blocks
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────
 
def _strip_think(text: str) -> str:
    """
    ลบ <think>...</think> ออกจาก response Qwen3.5
    และ clean whitespace ที่เหลือ
    """
    cleaned = _THINK_RE.sub("", text)
    return cleaned.strip()
 
 
def _extract_json_block(text: str) -> str:
    """
    พยายาม extract JSON จาก response ที่อาจมี markdown fence
    ลำดับ: json block → bare { } → return as-is
    """
    # ```json ... ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
 
    # bare { ... } (first occurrence)
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return brace.group(0)
 
    return text  # ส่งคืนตามเดิม ให้ caller จัดการ


# ---------------------------------------------------------------------------
# Rery Utility
# ---------------------------------------------------------------------------

def with_retry(max_attempts=3, delay=2.0):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except LLMProviderError as e:
                    if attempt == max_attempts - 1:
                        raise
                    print(f"⚠️ API call failed (attempt {attempt + 1}/{max_attempts}). Retrying in {delay}s...")
                    time.sleep(delay * (attempt + 1)) # Exponential-ish backoff
        return wrapper
    return decorator

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
    - call()         → รับ PromptPackage, คืน str (JSON expected)
    - is_available() → ตรวจสอบว่า client พร้อมใช้งาน
    """

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

    @with_retry(max_attempts=3)
    @log_method(sys_logger)
    def call(self, prompt_package: PromptPackage) -> str:
        if self.use_mock:
            return self._mock_response(prompt_package)

        if not self._client:
            raise LLMUnavailableError("GeminiClient is not initialized.")

        try:
            full_prompt = (
                f"SYSTEM:\n{prompt_package.system}\n\n" f"USER:\n{prompt_package.user}"
            )
            
            llm_logger.info(f"--- LLM REQUEST [{prompt_package.step_label}] ---")
            llm_logger.debug(f"PROMPT:\n{full_prompt}")
            
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt_package.user,
                config={"system_instruction": prompt_package.system},
            )
            
            llm_logger.info(f"--- LLM RESPONSE [{prompt_package.step_label}] ---")
            llm_logger.debug(f"OUTPUT:\n{response.text}")
            
            return response.text
        
        except Exception as e:
            raise LLMProviderError(
                f"Gemini API error at {prompt_package.step_label}: {e}"
            ) from e

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
            return response.choices[0].message.content
        except Exception as e:
            raise LLMProviderError(
                f"OpenAI API error at {prompt_package.step_label}: {e}"
            ) from e

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
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=prompt_package.system,
                messages=[
                    {"role": "user", "content": prompt_package.user},
                ],
            )
            return response.content[0].text
        except Exception as e:
            raise LLMProviderError(
                f"Claude API error at {prompt_package.step_label}: {e}"
            ) from e

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
        try:
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user", "content": prompt_package.user},
                ],
                model=self.model,
                temperature=self.temperature,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            raise LLMProviderError(f"Groq API error: {e}") from e

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
                base_url="https://api.deepseek.com",
            )
        except KeyError:
            raise LLMUnavailableError("DEEPSEEK_API_KEY not found in env.")
        except ImportError:
            raise LLMUnavailableError("openai package missing.")

    def call(self, prompt_package: PromptPackage) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user", "content": prompt_package.user},
                ],
                temperature=self.temperature,
                stream=False,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMProviderError(f"DeepSeek API error: {e}") from e

    def is_available(self) -> bool:
        return self._client is not None
    
class OllamaClient(LLMClient):
    """
    LLM Client สำหรับ Ollama local inference server
 
    รองรับ model ทุกตัวที่ pull ลงใน Ollama แล้ว เช่น
      - qwen3.5:9b    (ถ้า available — มี thinking mode, strip ให้อัตโนมัติ)
      - llama3.1:8b
 
    การใช้งาน:
        client = LLMClientFactory.create("ollama")
        client = LLMClientFactory.create("ollama", model="qwen3.5:9b")
        client = LLMClientFactory.create("ollama", base_url="http://192.168.1.10:11434")
 
    Environment Variables (optional):
        OLLAMA_BASE_URL  : default http://localhost:11434
        OLLAMA_MODEL     : default qwen3.5:9b
    """
 
    def __init__(
        self,
        model: str = OLLAMA_DEFAULT_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        temperature: float = 0.1,      # ต่ำ = deterministic สำหรับ JSON
        num_ctx: int = 4096,           # context window
        timeout: int = 120,            # วินาที (local inference ช้ากว่า API)
        strip_thinking: bool = True,   # strip <think> Qwen3.5
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.strip_thinking = strip_thinking
 
        self._chat_url = f"{self.base_url}/api/chat"
        self._tags_url = f"{self.base_url}/api/tags"    # ใช้ตรวจสอบ health
 
        # ตรวจ connection ตั้งแต่ init
        if not self._ping():
            raise LLMUnavailableError(
                f"Ollama server ไม่ตอบสนองที่ {self.base_url}\n"
                f"  → รัน: ollama serve\n"
                f"  → pull model: ollama pull {self.model}"
            )
 
    # ── Public API ────────────────────────────────────────────────
 
    def call(self, prompt_package: PromptPackage) -> str:
        """
        ส่ง prompt ไปยัง Ollama และรับ response กลับ
 
        Returns:
            str: cleaned JSON string (think blocks stripped ถ้าเปิด)
 
        Raises:
            LLMProviderError: Ollama ตอบ error หรือ request ล้มเหลว
            LLMUnavailableError: server ไม่พร้อม
        """
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
            "messages": [
                # /no_think อยู่ใน system prompt → บอก Qwen3.5 ไม่ต้อง think
                {"role": "system", "content": self._inject_no_think(prompt_package.system)},
                {"role": "user",   "content": prompt_package.user},
            ],
        }
 
        try:
            resp = requests.post(
                self._chat_url,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise LLMUnavailableError(
                f"เชื่อมต่อ Ollama ไม่ได้ที่ {self.base_url} — ตรวจสอบว่า ollama serve รันอยู่"
            )
        except requests.exceptions.Timeout:
            raise LLMProviderError(
                f"Ollama timeout ({self.timeout}s) สำหรับ model={self.model}"
            )
        except requests.exceptions.HTTPError as e:
            raise LLMProviderError(f"Ollama HTTP error: {e}") from e
 
        data = resp.json()
 
        # Ollama response structure: data["message"]["content"]
        raw = data.get("message", {}).get("content", "")
        if not raw:
            raise LLMProviderError("Ollama returned empty content")
 
        # Strip think blocks + extract JSON
        cleaned = _strip_think(raw) if self.strip_thinking else raw
        return _extract_json_block(cleaned)
 
    def is_available(self) -> bool:
        return self._ping()
 
    # ── Private Helpers ───────────────────────────────────────────
 
    def _ping(self) -> bool:
        """ตรวจสอบว่า Ollama daemon รันอยู่"""
        try:
            r = requests.get(self._tags_url, timeout=3)
            return r.status_code == 200
        except Exception:
            return False
 
    @staticmethod
    def _inject_no_think(system_prompt: str) -> str:
        """
        เพิ่ม /no_think ถ้ายังไม่มีใน system prompt
        บอก Qwen3.5 ให้ข้ามขั้นตอน thinking และ output JSON ตรงๆ
        """
        if "/no_think" not in system_prompt:
            return "/no_think\n" + system_prompt
        return system_prompt
 
    def list_local_models(self) -> list[str]:
        """
        คืนรายชื่อ model ที่ pull ลงมาแล้วใน Ollama (utility method)
 
        Returns:
            ['qwen3.5:9b', 'llama3.1:8b', ...]
        """
        try:
            r = requests.get(self._tags_url, timeout=5)
            r.raise_for_status()
            models = r.json().get("models", [])
            return [m["name"] for m in models]
        except Exception:
            return []
 
    def __repr__(self) -> str:
        return (
            f"<OllamaClient model={self.model} "
            f"url={self.base_url} "
            f"available={self.is_available()}>"
        )


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
        "ollama":   OllamaClient,
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
        
    
