"""
react.py — Part B: ReAct Orchestration Loop
Thought → Action → Observation → ... → FINAL_DECISION
"""

import json
import re
from typing import Callable, Any, Optional
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
# Config (ต้องอยู่ก่อน ReactState)
# ─────────────────────────────────────────────

@dataclass
class ReactConfig:
    """Config สำหรับ ReAct loop"""
    max_iterations: int   = 5
    max_tool_calls: int   = 0      # 0 = ไม่ใช้ tool (data pre-loaded)
    timeout_seconds: Optional[int] = None


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class ToolResult:
    """Result จากการ execute tool"""
    tool_name: str
    status:    str              # "success" | "error"
    data:      dict
    error:     Optional[str] = None


@dataclass
class ReactState:
    """Mutable state ตลอด loop"""
    market_state:    dict
    tool_results:    list        # list[ToolResult]
    iteration:       int = 0
    tool_call_count: int = 0
    react_trace:     list = field(default_factory=list)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def extract_json(raw: str) -> dict:
    """
    Parse JSON จาก LLM response อย่างปลอดภัย
    รองรับ: plain JSON, ```json ... ```, ``` ... ```
    """
    if not raw or not raw.strip():
        return {}

    # Strip markdown fences (Gemini / Claude อาจส่งมา)
    cleaned = re.sub(r"^
http://googleusercontent.com/immersive_entry_chip/0

ถ้าทดสอบรัน 2 ไฟล์นี้แล้วได้ผลลัพธ์ที่เร็วขึ้นจริงๆ (หรือถ้ายังติดตรงไหน) ทักมาบอกได้เลยนะครับ ผมรอช่วยอยู่!