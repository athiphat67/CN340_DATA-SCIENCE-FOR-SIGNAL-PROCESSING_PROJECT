"""
tools/tool_registry.py — Registry สำหรับ LLM Agent
รวม tools ไว้ที่เดียว แยกส่วน Internal (Orchestrator) และ Public (LLM) 

Usage:
    from data_engine.tools.tool_registry import call_tool, list_tools, AVAILABLE_TOOLS_INFO

    # Orchestrator เรียกได้ (Internal)
    result = call_tool("fetch_price", interval="5m", history_days=30)
    
    # LLM เรียกได้ (Public)
    result = call_tool("detect_swing_low", interval="15m", history_days=3)
"""

import logging
from typing import Any

from tools.fetch_price      import fetch_price
from tools.fetch_indicators import fetch_indicators
from tools.fetch_news       import fetch_news
from tools.schema_validator import validate_market_state

# 1. Import จากโฟลเดอร์ analysis_tools 
from data_engine.analysis_tools import TOOL_REGISTRY as ANALYSIS_TOOL_REGISTRY
from data_engine.analysis_tools import AVAILABLE_TOOLS_INFO as ANALYSIS_TOOLS_INFO

logger = logging.getLogger(__name__)

# 2. Internal Tools (ใช้โดย Orchestrator เพื่อสร้าง market_state ห้ามให้ LLM เห็น)
INTERNAL_TOOLS: dict[str, Any] = {
    "fetch_price": fetch_price,
    "fetch_indicators": fetch_indicators,
    "fetch_news": fetch_news,
}

# 3. LLM Tools (เครื่องมือวิเคราะห์จำเพาะ ที่อนุญาตให้ LLM ใช้ใน ReAct Loop)
LLM_TOOLS = ANALYSIS_TOOL_REGISTRY

# 4. TOOL_REGISTRY (รวมทั้งหมด เพื่อให้ call_tool หรือไฟล์เก่าดึงไปใช้ได้ ไม่พัง)
TOOL_REGISTRY = {**INTERNAL_TOOLS, **LLM_TOOLS}

# 5. คู่มือสำหรับ LLM (ดึงมาเฉพาะฝั่ง Analysis)
AVAILABLE_TOOLS_INFO = ANALYSIS_TOOLS_INFO


def call_tool(tool_name: str, **kwargs: Any) -> dict:
    """
    เรียก tool จาก TOOL_REGISTRY (Orchestrator และ LLM เรียกผ่านที่นี่)
    """
    if tool_name not in TOOL_REGISTRY:
        available = list(TOOL_REGISTRY.keys())
        raise KeyError(f"Tool '{tool_name}' not found. Available: {available}")

    logger.info(f"[ToolRegistry] Calling '{tool_name}' with params={list(kwargs.keys())}")
    
    tool_target = TOOL_REGISTRY[tool_name]
    
    # Smart Check: รองรับทั้ง Dictionary ที่มี "fn" และ Function ตรงๆ
    if isinstance(tool_target, dict) and "fn" in tool_target:
        return tool_target["fn"](**kwargs)
    else:
        return tool_target(**kwargs)


def list_tools() -> list[dict]:
    """
    คืน list ของ tools ไปประทับใน Prompt
    **คืนค่าเฉพาะ LLM_TOOLS เท่านั้น (ซ่อน Internal Tools)**
    """
    tools_list = []
    for name, meta in LLM_TOOLS.items():
        if isinstance(meta, dict) and "description" in meta:
            tools_list.append({
                "name": name, 
                "description": meta["description"], 
                "parameters": meta.get("parameters", {})
            })
        else:
            # Fallback ป้องกัน list_tools() พัง
            tools_list.append({
                "name": name, 
                "description": f"Advanced Analysis Tool: {name}", 
                "parameters": {}
            })
    return tools_list