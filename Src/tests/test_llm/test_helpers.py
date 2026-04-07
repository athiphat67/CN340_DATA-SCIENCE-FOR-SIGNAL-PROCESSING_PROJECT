"""
test_helpers.py — LLM Regression Tests สำหรับ helper functions

ทดสอบ pure functions ที่ประมวลผล LLM output:
  1. _strip_think()        — ลบ <think>...</think> จาก Qwen3 response
  2. _extract_json_block() — ดึง JSON จาก markdown fence / bare {} / as-is
  3. extract_json()        — parse JSON จาก LLM response อย่างปลอดภัย (react.py)
  4. _make_llm_log()       — สร้าง trace entry ที่มี LLM metadata ครบ
  5. LLMResponse            — dataclass fields + defaults

Strategy: Pure function tests — ไม่ใช้ API, ไม่ใช้ mock client
  - Deterministic 100%
  - รันได้ทุก commit, ไม่เสียเงิน
"""

import pytest

from agent_core.llm.client import (
    _strip_think,
    _extract_json_block,
    LLMResponse,
)
from agent_core.core.react import extract_json, _make_llm_log


# ══════════════════════════════════════════════════════════════════
# 1. _strip_think — ลบ <think>...</think> blocks
# ══════════════════════════════════════════════════════════════════


class TestStripThink:
    """ทดสอบ _strip_think() — ลบ Qwen3 thinking blocks"""

    def test_removes_think_block(self):
        """ลบ <think>...</think> ออกจาก response"""
        raw = '<think>I need to analyze the gold market...</think>{"signal": "BUY"}'
        assert _strip_think(raw) == '{"signal": "BUY"}'

    def test_no_think_block_unchanged(self):
        """ถ้าไม่มี <think> → คืนค่าเดิม (stripped)"""
        raw = '{"signal": "HOLD"}'
        assert _strip_think(raw) == '{"signal": "HOLD"}'

    def test_multiline_think(self):
        """<think> block หลายบรรทัด"""
        raw = (
            "<think>\n"
            "Step 1: Check RSI\n"
            "Step 2: Check MACD\n"
            "Step 3: Make decision\n"
            "</think>\n"
            '{"signal": "SELL", "confidence": 0.8}'
        )
        assert _strip_think(raw) == '{"signal": "SELL", "confidence": 0.8}'

    def test_multiple_think_blocks(self):
        """มี <think> หลาย blocks → ลบทั้งหมด"""
        raw = "<think>first</think>middle<think>second</think>end"
        assert _strip_think(raw) == "middleend"

    def test_case_insensitive(self):
        """<THINK>, <Think> ต้องลบได้เหมือนกัน"""
        raw = '<THINK>uppercase</THINK>{"signal": "BUY"}'
        assert _strip_think(raw) == '{"signal": "BUY"}'

    def test_empty_think_block(self):
        """<think></think> ว่าง → ลบได้"""
        raw = '<think></think>{"signal": "HOLD"}'
        assert _strip_think(raw) == '{"signal": "HOLD"}'

    def test_empty_string(self):
        """string ว่าง → คืน string ว่าง"""
        assert _strip_think("") == ""

    def test_whitespace_cleanup(self):
        """ลบ whitespace ที่เหลือหลัง strip"""
        raw = "  <think>thinking...</think>  result  "
        assert _strip_think(raw) == "result"

    def test_think_with_json_inside(self):
        """<think> block มี JSON ข้างใน → ลบ JSON ข้างใน think ด้วย"""
        raw = '<think>{"internal": true}</think>{"signal": "BUY"}'
        assert _strip_think(raw) == '{"signal": "BUY"}'


# ══════════════════════════════════════════════════════════════════
# 2. _extract_json_block — ดึง JSON จาก response
# ══════════════════════════════════════════════════════════════════


class TestExtractJsonBlock:
    """ทดสอบ _extract_json_block() — extract JSON จาก LLM text"""

    def test_json_fence(self):
        """```json ... ``` → ดึง JSON ออกมา"""
        raw = '```json\n{"signal": "BUY", "confidence": 0.9}\n```'
        result = _extract_json_block(raw)
        assert result == '{"signal": "BUY", "confidence": 0.9}'

    def test_generic_fence(self):
        """``` ... ``` (ไม่มี json label) → ดึง JSON ออกมา"""
        raw = '```\n{"signal": "SELL"}\n```'
        result = _extract_json_block(raw)
        assert result == '{"signal": "SELL"}'

    def test_bare_braces(self):
        """JSON ไม่มี fence → ดึงจาก { ... }"""
        raw = 'Here is my analysis: {"signal": "HOLD", "confidence": 0.5} end.'
        result = _extract_json_block(raw)
        assert '{"signal": "HOLD"' in result

    def test_no_json_returns_as_is(self):
        """ไม่มี JSON เลย → คืน text เดิม"""
        raw = "I think we should hold for now."
        result = _extract_json_block(raw)
        assert result == raw

    def test_json_fence_with_whitespace(self):
        """```json ... ``` มี whitespace → ยังดึงได้"""
        raw = '```json\n  {"signal": "BUY"}  \n```'
        result = _extract_json_block(raw)
        assert '"signal": "BUY"' in result

    def test_nested_braces(self):
        """JSON มี nested objects"""
        raw = '{"action": "CALL_TOOL", "params": {"expression": "close / open"}}'
        result = _extract_json_block(raw)
        assert '"params"' in result

    def test_text_before_and_after_json(self):
        """มี text ก่อนและหลัง JSON"""
        raw = 'Based on analysis: {"signal": "SELL"} That is my decision.'
        result = _extract_json_block(raw)
        assert '"signal": "SELL"' in result

    def test_empty_string(self):
        """string ว่าง → คืน string ว่าง"""
        result = _extract_json_block("")
        assert result == ""


# ══════════════════════════════════════════════════════════════════
# 3. extract_json (react.py) — parse JSON อย่างปลอดภัย
# ══════════════════════════════════════════════════════════════════


class TestExtractJson:
    """ทดสอบ extract_json() จาก react.py — safe JSON parsing"""

    def test_valid_json(self):
        """JSON ปกติ → parse สำเร็จ"""
        raw = '{"signal": "BUY", "confidence": 0.9}'
        result = extract_json(raw)
        assert result["signal"] == "BUY"
        assert result["confidence"] == 0.9

    def test_json_in_markdown_fence(self):
        """```json ... ``` → parse สำเร็จ"""
        raw = '```json\n{"signal": "SELL", "confidence": 0.8}\n```'
        result = extract_json(raw)
        assert result["signal"] == "SELL"

    def test_json_in_generic_fence(self):
        """``` ... ``` → parse สำเร็จ"""
        raw = '```\n{"signal": "HOLD"}\n```'
        result = extract_json(raw)
        assert result["signal"] == "HOLD"

    def test_empty_string_returns_empty_dict(self):
        """string ว่าง → {}"""
        assert extract_json("") == {}

    def test_none_like_empty(self):
        """whitespace เท่านั้น → {}"""
        assert extract_json("   ") == {}

    def test_invalid_json_returns_parse_error(self):
        """JSON ผิด format → มี _parse_error key"""
        result = extract_json("not json at all")
        assert result.get("_parse_error") is True
        assert "_raw" in result

    def test_partial_json_with_text(self):
        """มี text ก่อน JSON → parse ส่วน JSON ได้"""
        raw = 'Here is my decision: {"signal": "BUY", "confidence": 0.7}'
        result = extract_json(raw)
        assert result["signal"] == "BUY"

    def test_nested_json(self):
        """JSON ซ้อน → parse ได้ทั้งหมด"""
        raw = '{"action": "CALL_TOOL", "tool": "calc", "params": {"expr": "1+1"}}'
        result = extract_json(raw)
        assert result["action"] == "CALL_TOOL"
        assert result["params"]["expr"] == "1+1"

    def test_json_with_array(self):
        """JSON มี array"""
        raw = '{"signals": ["BUY", "HOLD"], "count": 2}'
        result = extract_json(raw)
        assert result["signals"] == ["BUY", "HOLD"]

    def test_raw_truncated_to_500(self):
        """_raw ต้องถูก truncate ไม่เกิน 500 chars"""
        long_text = "x" * 1000
        result = extract_json(long_text)
        assert result.get("_parse_error") is True
        assert len(result["_raw"]) == 500

    def test_json_with_unicode(self):
        """JSON มี unicode (ภาษาไทย)"""
        raw = '{"rationale": "ราคาทองสูงเกินไป", "signal": "SELL"}'
        result = extract_json(raw)
        assert result["signal"] == "SELL"
        assert "ราคาทอง" in result["rationale"]


# ══════════════════════════════════════════════════════════════════
# 4. _make_llm_log — สร้าง trace entry
# ══════════════════════════════════════════════════════════════════


class TestMakeLlmLog:
    """ทดสอบ _make_llm_log() — สร้าง react trace entry"""

    @pytest.fixture
    def mock_llm_resp(self):
        """สร้าง LLMResponse สำหรับ test"""
        return LLMResponse(
            text='{"signal": "BUY"}',
            prompt_text="SYSTEM:\nYou are...\n\nUSER:\nAnalyze...",
            token_input=100,
            token_output=50,
            token_total=150,
            model="gemini-2.0-flash",
            provider="gemini",
        )

    def test_basic_entry(self, mock_llm_resp):
        """สร้าง entry พื้นฐาน — มี keys ครบ"""
        entry = _make_llm_log(
            step="THOUGHT",
            iteration=1,
            llm_resp=mock_llm_resp,
            parsed={"signal": "BUY"},
        )
        assert entry["step"] == "THOUGHT"
        assert entry["iteration"] == 1
        assert entry["response"] == {"signal": "BUY"}

    def test_llm_metadata(self, mock_llm_resp):
        """entry มี LLM metadata ครบ"""
        entry = _make_llm_log(
            step="THOUGHT",
            iteration=1,
            llm_resp=mock_llm_resp,
            parsed={},
        )
        assert entry["prompt_text"] == "SYSTEM:\nYou are...\n\nUSER:\nAnalyze..."
        assert entry["response_raw"] == '{"signal": "BUY"}'
        assert entry["token_input"] == 100
        assert entry["token_output"] == 50
        assert entry["token_total"] == 150
        assert entry["model"] == "gemini-2.0-flash"
        assert entry["provider"] == "gemini"

    def test_with_note(self, mock_llm_resp):
        """note ถ้ามีค่า → ต้องอยู่ใน entry"""
        entry = _make_llm_log(
            step="THOUGHT",
            iteration=1,
            llm_resp=mock_llm_resp,
            parsed={},
            note="Fallback to HOLD",
        )
        assert entry["note"] == "Fallback to HOLD"

    def test_without_note(self, mock_llm_resp):
        """ไม่มี note → ไม่มี key 'note' ใน entry"""
        entry = _make_llm_log(
            step="THOUGHT",
            iteration=1,
            llm_resp=mock_llm_resp,
            parsed={},
        )
        assert "note" not in entry

    def test_none_llm_resp(self):
        """llm_resp = None → metadata เป็น default values"""
        entry = _make_llm_log(
            step="FINAL_DECISION",
            iteration=3,
            llm_resp=None,
            parsed={"signal": "HOLD"},
        )
        assert entry["prompt_text"] == ""
        assert entry["response_raw"] == ""
        assert entry["token_input"] == 0
        assert entry["token_output"] == 0
        assert entry["token_total"] == 0
        assert entry["model"] == ""
        assert entry["provider"] == ""

    def test_all_required_keys(self, mock_llm_resp):
        """ตรวจว่ามี keys ที่จำเป็นทั้งหมด"""
        entry = _make_llm_log(
            step="THOUGHT",
            iteration=1,
            llm_resp=mock_llm_resp,
            parsed={},
        )
        required_keys = {
            "step",
            "iteration",
            "response",
            "prompt_text",
            "response_raw",
            "token_input",
            "token_output",
            "token_total",
            "model",
            "provider",
        }
        assert required_keys.issubset(entry.keys())


# ══════════════════════════════════════════════════════════════════
# 5. LLMResponse — dataclass
# ══════════════════════════════════════════════════════════════════


class TestLLMResponse:
    """ทดสอบ LLMResponse dataclass"""

    def test_required_fields(self):
        """text + prompt_text เป็น required"""
        resp = LLMResponse(text="hello", prompt_text="prompt")
        assert resp.text == "hello"
        assert resp.prompt_text == "prompt"

    def test_default_values(self):
        """fields ที่ไม่ระบุ → ใช้ default"""
        resp = LLMResponse(text="hello", prompt_text="prompt")
        assert resp.token_input == 0
        assert resp.token_output == 0
        assert resp.token_total == 0
        assert resp.model == ""
        assert resp.provider == ""

    def test_all_fields(self):
        """ระบุทุก field"""
        resp = LLMResponse(
            text='{"signal": "BUY"}',
            prompt_text="full prompt",
            token_input=100,
            token_output=50,
            token_total=150,
            model="gemini-2.0-flash",
            provider="gemini",
        )
        assert resp.text == '{"signal": "BUY"}'
        assert resp.prompt_text == "full prompt"
        assert resp.token_input == 100
        assert resp.token_output == 50
        assert resp.token_total == 150
        assert resp.model == "gemini-2.0-flash"
        assert resp.provider == "gemini"

    def test_token_total_independent(self):
        """token_total ไม่ได้คำนวณอัตโนมัติ — ต้องระบุเอง"""
        resp = LLMResponse(
            text="test",
            prompt_text="prompt",
            token_input=100,
            token_output=50,
            token_total=999,
        )
        assert resp.token_total == 999  # ไม่ใช่ 150

    def test_is_dataclass(self):
        """LLMResponse เป็น dataclass จริง"""
        from dataclasses import fields

        field_names = {f.name for f in fields(LLMResponse)}
        expected = {
            "text",
            "prompt_text",
            "token_input",
            "token_output",
            "token_total",
            "model",
            "provider",
        }
        assert expected == field_names
