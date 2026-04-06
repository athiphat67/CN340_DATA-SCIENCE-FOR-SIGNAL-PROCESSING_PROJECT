from __future__ import annotations

import os
import re
import json
import requests
from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from agent_core.core.prompt import PromptPackage
import time
from functools import wraps
from logs.logger_setup import llm_logger, sys_logger, log_method

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
 
# Regex สำหรับ strip Qwen3 thinking blocks
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────
# LLMResponse — structured response จาก LLM (replaces bare str)
# ─────────────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    """
    Structured response จาก LLM ทุก provider

    Fields:
        text         — raw text response (JSON string expected)
        prompt_text  — full prompt ที่ส่งไป (system + user concatenated)
        token_input  — จำนวน input tokens (0 ถ้า provider ไม่รองรับ)
        token_output — จำนวน output tokens
        token_total  — รวม input + output
        model        — model name ที่ใช้จริง
        provider     — provider name ("gemini", "openai", "claude", ...)
    """
    text:         str
    prompt_text:  str
    token_input:  int = 0
    token_output: int = 0
    token_total:  int = 0
    model:        str = ""
    provider:     str = ""


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
# Retry Utility
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
                    time.sleep(delay * (attempt + 1))  # Exponential-ish backoff
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
    - call()         → รับ PromptPackage, คืน LLMResponse (text + tokens + meta)
    - is_available() → ตรวจสอบว่า client พร้อมใช้งาน
    """

    PROVIDER_NAME: str = "unknown"

    @abstractmethod
    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        """
        ส่ง prompt ไปยัง LLM และรับ LLMResponse กลับมา

        Args:
            prompt_package: PromptPackage ที่มี system, user, step_label

        Returns:
            LLMResponse: text + prompt_text + token counts + model/provider info

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

    @staticmethod
    def _build_prompt_text(prompt_package: PromptPackage) -> str:
        """Helper: สร้าง full prompt string สำหรับ logging"""
        return f"SYSTEM:\n{prompt_package.system}\n\nUSER:\n{prompt_package.user}"

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

    PROVIDER_NAME = "mock"

    def __init__(self, response_map: Optional[dict[str, str]] = None):
        self.response_map = (
            response_map if response_map is not None else DEFAULT_MOCK_RESPONSES
        )

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        text = self.response_map.get(
            prompt_package.step_label,
            '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.5, "rationale": "Mock fallback"}',
        )
        return LLMResponse(
            text=text,
            prompt_text=self._build_prompt_text(prompt_package),
            token_input=0,
            token_output=0,
            token_total=0,
            model="mock",
            provider=self.PROVIDER_NAME,
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

    PROVIDER_NAME = "gemini"
    # DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
    DEFAULT_MODEL = "gemini-2.5-flash-lite"

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
    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        if self.use_mock:
            return self._mock_response(prompt_package)

        if not self._client:
            raise LLMUnavailableError("GeminiClient is not initialized.")

        full_prompt = self._build_prompt_text(prompt_package)

        try:
            llm_logger.info(f"--- LLM REQUEST [{prompt_package.step_label}] ---")
            llm_logger.debug(f"PROMPT:\n{full_prompt}")

            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt_package.user,
                config={"system_instruction": prompt_package.system},
            )

            text = response.text or ""

            # Extract token usage from Gemini response
            usage = getattr(response, "usage_metadata", None)
            token_input  = getattr(usage, "prompt_token_count",     0) if usage else 0
            token_output = getattr(usage, "candidates_token_count", 0) if usage else 0
            token_total  = getattr(usage, "total_token_count", token_input + token_output) if usage else token_input + token_output

            llm_logger.info(f"--- LLM RESPONSE [{prompt_package.step_label}] ---")
            llm_logger.info(f"🪙 Gemini Token Usage → Input: {token_input} | Output: {token_output} | Total: {token_total}")
            llm_logger.debug(f"OUTPUT:\n{text}")

            return LLMResponse(
                text=text,
                prompt_text=full_prompt,
                token_input=token_input,
                token_output=token_output,
                token_total=token_total,
                model=self.model,
                provider=self.PROVIDER_NAME,
            )

        except Exception as e:
            raise LLMProviderError(
                f"Gemini API error at {prompt_package.step_label}: {e}"
            ) from e

    def is_available(self) -> bool:
        if self.use_mock:
            return True
        return self._client is not None

    def _mock_response(self, prompt_package: PromptPackage) -> LLMResponse:
        text = DEFAULT_MOCK_RESPONSES.get(
            prompt_package.step_label,
            '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.5, "rationale": "Mock fallback"}',
        )
        return LLMResponse(
            text=text,
            prompt_text=self._build_prompt_text(prompt_package),
            token_input=0, token_output=0, token_total=0,
            model=self.model, provider=self.PROVIDER_NAME,
        )


class OpenAIClient(LLMClient):
    """LLM Client สำหรับ OpenAI API (GPT series)"""

    PROVIDER_NAME = "openai"
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

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        full_prompt = self._build_prompt_text(prompt_package)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user",   "content": prompt_package.user},
                ],
            )
            text = response.choices[0].message.content or ""

            usage = response.usage
            token_input  = getattr(usage, "prompt_tokens",     0) if usage else 0
            token_output = getattr(usage, "completion_tokens", 0) if usage else 0
            token_total  = getattr(usage, "total_tokens", token_input + token_output) if usage else token_input + token_output

            llm_logger.info(f"🪙 OpenAI Token Usage → Input: {token_input} | Output: {token_output} | Total: {token_total}")

            return LLMResponse(
                text=text,
                prompt_text=full_prompt,
                token_input=token_input,
                token_output=token_output,
                token_total=token_total,
                model=self.model,
                provider=self.PROVIDER_NAME,
            )
        except Exception as e:
            raise LLMProviderError(
                f"OpenAI API error at {prompt_package.step_label}: {e}"
            ) from e

    def is_available(self) -> bool:
        return self._client is not None


class ClaudeClient(LLMClient):
    """LLM Client สำหรับ Anthropic Claude API"""

    PROVIDER_NAME = "claude"
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

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        full_prompt = self._build_prompt_text(prompt_package)
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=prompt_package.system,
                messages=[
                    {"role": "user", "content": prompt_package.user},
                ],
            )
            text = response.content[0].text if response.content else ""

            usage = getattr(response, "usage", None)
            token_input  = getattr(usage, "input_tokens",  0) if usage else 0
            token_output = getattr(usage, "output_tokens", 0) if usage else 0
            token_total  = token_input + token_output

            llm_logger.info(f"🪙 Claude Token Usage → Input: {token_input} | Output: {token_output} | Total: {token_total}")

            return LLMResponse(
                text=text,
                prompt_text=full_prompt,
                token_input=token_input,
                token_output=token_output,
                token_total=token_total,
                model=self.model,
                provider=self.PROVIDER_NAME,
            )
        except Exception as e:
            raise LLMProviderError(
                f"Claude API error at {prompt_package.step_label}: {e}"
            ) from e

    def is_available(self) -> bool:
        return self._client is not None


class GroqClient(LLMClient):
    """LLM Client สำหรับ Groq (LPU Inference Engine) - เน้นความเร็วสูง"""

    PROVIDER_NAME = "groq"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.1,
        **kwargs,
    ):
        self.model = model
        self.temperature = temperature
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")

        try:
            from groq import Groq
            if not self.api_key:
                raise LLMUnavailableError("GROQ_API_KEY not found. Please set it in your .env file.")
            self._client = Groq(api_key=self.api_key)
        except ImportError:
            raise LLMUnavailableError("groq package not installed. Run: pip install groq")

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        full_prompt = self._build_prompt_text(prompt_package)
        try:
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user",   "content": prompt_package.user},
                ],
                model=self.model,
                temperature=self.temperature,
            )

            usage = chat_completion.usage
            token_input  = getattr(usage, "prompt_tokens",     0) if usage else 0
            token_output = getattr(usage, "completion_tokens", 0) if usage else 0
            token_total  = getattr(usage, "total_tokens", token_input + token_output) if usage else token_input + token_output

            llm_logger.info(f"🪙 Groq Token Usage → Input: {token_input} | Output: {token_output} | Total: {token_total}")

            raw  = chat_completion.choices[0].message.content or ""
            text = _extract_json_block(_strip_think(raw))

            return LLMResponse(
                text=text,
                prompt_text=full_prompt,
                token_input=token_input,
                token_output=token_output,
                token_total=token_total,
                model=self.model,
                provider=self.PROVIDER_NAME,
            )

        except Exception as e:
            raise LLMProviderError(f"Groq API error: {e}") from e

    def is_available(self) -> bool:
        return self._client is not None


class DeepSeekClient(LLMClient):
    """LLM Client สำหรับ DeepSeek API - รองรับ OpenAI compatible format"""

    PROVIDER_NAME = "deepseek"
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

            self._client = OpenAI(
                api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
                base_url="https://api.deepseek.com",
            )
        except KeyError:
            raise LLMUnavailableError("DEEPSEEK_API_KEY not found in env.")
        except ImportError:
            raise LLMUnavailableError("openai package missing.")

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        full_prompt = self._build_prompt_text(prompt_package)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user",   "content": prompt_package.user},
                ],
                temperature=self.temperature,
                stream=False,
            )
            text = response.choices[0].message.content or ""

            usage = getattr(response, "usage", None)
            token_input  = getattr(usage, "prompt_tokens",     0) if usage else 0
            token_output = getattr(usage, "completion_tokens", 0) if usage else 0
            token_total  = getattr(usage, "total_tokens", token_input + token_output) if usage else token_input + token_output

            llm_logger.info(f"🪙 DeepSeek Token Usage → Input: {token_input} | Output: {token_output} | Total: {token_total}")

            return LLMResponse(
                text=text,
                prompt_text=full_prompt,
                token_input=token_input,
                token_output=token_output,
                token_total=token_total,
                model=self.model,
                provider=self.PROVIDER_NAME,
            )
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

    Environment Variables (optional):
        OLLAMA_BASE_URL  : default http://localhost:11434
        OLLAMA_MODEL     : default qwen3.5:9b
    """

    PROVIDER_NAME = "ollama"

    def __init__(
        self,
        model: str = OLLAMA_DEFAULT_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        temperature: float = 0.1,
        num_ctx: int = 4096,
        timeout: int = 120,
        strip_thinking: bool = True,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.strip_thinking = strip_thinking

        self._chat_url = f"{self.base_url}/api/chat"
        self._tags_url = f"{self.base_url}/api/tags"

        if not self._ping():
            raise LLMUnavailableError(
                f"Ollama server ไม่ตอบสนองที่ {self.base_url}\n"
                f"  → รัน: ollama serve\n"
                f"  → pull model: ollama pull {self.model}"
            )

    # ── Public API ────────────────────────────────────────────────

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        """
        ส่ง prompt ไปยัง Ollama และรับ LLMResponse กลับ

        Returns:
            LLMResponse: text (cleaned JSON) + prompt_text + token counts

        Raises:
            LLMProviderError: Ollama ตอบ error หรือ request ล้มเหลว
            LLMUnavailableError: server ไม่พร้อม
        """
        full_prompt = self._build_prompt_text(prompt_package)

        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
            "messages": [
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

        raw = data.get("message", {}).get("content", "")
        if not raw:
            raise LLMProviderError("Ollama returned empty content")

        # Ollama token usage fields
        token_input  = data.get("prompt_eval_count", 0)
        token_output = data.get("eval_count", 0)
        token_total  = token_input + token_output

        llm_logger.info(f"🪙 Ollama Token Usage → Input: {token_input} | Output: {token_output} | Total: {token_total}")

        cleaned = _strip_think(raw) if self.strip_thinking else raw
        text = _extract_json_block(cleaned)

        return LLMResponse(
            text=text,
            prompt_text=full_prompt,
            token_input=token_input,
            token_output=token_output,
            token_total=token_total,
            model=self.model,
            provider=self.PROVIDER_NAME,
        )

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
        """คืนรายชื่อ model ที่ pull ลงมาแล้วใน Ollama"""
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

class OpenRouterClient(LLMClient):
    """LLM Client สำหรับ OpenRouter API - รองรับ OpenAI compatible format"""

    PROVIDER_NAME = "openrouter"
    DEFAULT_MODEL = "meta-llama/llama-3-8b-instruct" # เปลี่ยน default model ได้ตามต้องการ

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

            # หัวใจสำคัญคือการเปลี่ยน base_url ชี้ไปที่ OpenRouter
            self._client = OpenAI(
                api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
            )
        except KeyError:
            raise LLMUnavailableError("OPENROUTER_API_KEY not found in env.")
        except ImportError:
            raise LLMUnavailableError("openai package missing.")

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        full_prompt = self._build_prompt_text(prompt_package)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt_package.system},
                    {"role": "user",   "content": prompt_package.user},
                ],
                temperature=self.temperature,
                stream=False,
                extra_headers={
                    "HTTP-Referer": "https://github.com/your-repo", # ใส่ URL ของคุณ (Optional)
                    "X-Title": "My Agent Framework", # ใส่ชื่อโปรเจกต์คุณ (Optional)
                }
            )
            text = response.choices[0].message.content or ""

            usage = getattr(response, "usage", None)
            token_input  = getattr(usage, "prompt_tokens",     0) if usage else 0
            token_output = getattr(usage, "completion_tokens", 0) if usage else 0
            token_total  = getattr(usage, "total_tokens", token_input + token_output) if usage else token_input + token_output

            llm_logger.info(f"🪙 OpenRouter Token Usage → Input: {token_input} | Output: {token_output} | Total: {token_total}")

            return LLMResponse(
                text=text,
                prompt_text=full_prompt,
                token_input=token_input,
                token_output=token_output,
                token_total=token_total,
                model=self.model,
                provider=self.PROVIDER_NAME,
            )
        except Exception as e:
            raise LLMProviderError(f"OpenRouter API error: {e}") from e

    def is_available(self) -> bool:
        return self._client is not None


# ---------------------------------------------------------------------------
# Fallback Chain Client
# ---------------------------------------------------------------------------


class FallbackChainClient(LLMClient):
    """
    LLM Client ที่รวม provider หลายตัวเข้าด้วยกัน
    ลองตัวแรกก่อน — ถ้าล้มเหลว (LLMProviderError / LLMUnavailableError)
    จะสลับไปตัวถัดไปอัตโนมัติโดยไม่ crash

    Usage:
        chain = FallbackChainClient([
            ("gemini", GeminiClient()),
            ("groq",   GroqClient()),
            ("mock",   MockClient()),
        ])
        result = chain.call(prompt_package)
        print(chain.active_provider)   # ชื่อ provider ที่ใช้จริง

    Behaviour:
    - ลอง provider ตามลำดับใน `clients`
    - Skip provider ที่ is_available() == False ตั้งแต่ต้น
    - เก็บ error log ทุกตัวใน `errors` สำหรับ debug
    - ถ้าทุกตัว fail → raise LLMProviderError รวม error ทั้งหมด
    """

    PROVIDER_NAME = "fallback_chain"

    def __init__(self, clients: list[tuple[str, LLMClient]]):
        if not clients:
            raise ValueError("FallbackChainClient requires at least one client")
        self.clients = clients
        self.active_provider: str = clients[0][0]
        self.errors: list[dict] = []

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        """
        ลอง call ตามลำดับ — fallback อัตโนมัติเมื่อ error

        Returns:
            LLMResponse จาก provider แรกที่สำเร็จ

        Raises:
            LLMProviderError: เมื่อทุก provider ล้มเหลว
        """
        self.errors = []

        for name, client in self.clients:
            if not client.is_available():
                msg = f"{name}: is_available() = False — skipped"
                sys_logger.warning(f"[FallbackChain] {msg}")
                self.errors.append({"provider": name, "error": msg, "skipped": True})
                continue

            try:
                sys_logger.info(
                    f"[FallbackChain] Trying provider '{name}' "
                    f"(step={prompt_package.step_label})"
                )
                result = client.call(prompt_package)
                self.active_provider = name
                sys_logger.info(f"[FallbackChain] ✅ Success with '{name}'")
                return result

            except (LLMProviderError, LLMUnavailableError) as e:
                err_str = f"{type(e).__name__}: {e}"
                sys_logger.warning(
                    f"[FallbackChain] ❌ '{name}' failed — {err_str}. "
                    f"Trying next provider..."
                )
                self.errors.append({"provider": name, "error": err_str, "skipped": False})
                continue

            except Exception as e:
                err_str = f"Unexpected {type(e).__name__}: {e}"
                sys_logger.error(f"[FallbackChain] 💥 '{name}' unexpected error — {err_str}")
                self.errors.append({"provider": name, "error": err_str, "skipped": False})
                continue

        # ทุกตัว fail
        summary = " | ".join(
            f"{e['provider']}: {e['error']}" for e in self.errors
        )
        raise LLMProviderError(
            f"All providers in fallback chain failed.\n  → {summary}"
        )

    def is_available(self) -> bool:
        """True ถ้ามีอย่างน้อย 1 provider ที่พร้อม"""
        return any(client.is_available() for _, client in self.clients)

    def __repr__(self) -> str:
        names = [n for n, _ in self.clients]
        return (
            f"<FallbackChainClient providers={names} "
            f"active='{self.active_provider}' "
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
        "gemini":   GeminiClient,
        "openai":   OpenAIClient,
        "claude":   ClaudeClient,
        "mock":     MockClient,
        "groq":     GroqClient,
        "deepseek": DeepSeekClient,
        "ollama":   OllamaClient,
        "openrouter": OpenRouterClient,
    }

    @classmethod
    def create(cls, provider: str, **kwargs) -> LLMClient:
        """
        สร้าง LLMClient ตาม provider name

        Args:
            provider: "gemini" | "openai" | "claude" | "groq" | "deepseek" | "ollama" | "mock"
            **kwargs: ส่งต่อไปยัง constructor ของแต่ละ class

        Returns:
            LLMClient instance ที่พร้อมใช้งาน

        Raises:
            ValueError: ถ้า provider ไม่รู้จัก
            LLMUnavailableError: ถ้า client สร้างไม่ได้
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