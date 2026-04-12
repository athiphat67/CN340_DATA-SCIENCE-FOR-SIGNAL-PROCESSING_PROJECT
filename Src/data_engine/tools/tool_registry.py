"""
tools/tool_registry.py — Registry สำหรับ LLM Agent
รวม tools ทั้งหมดไว้ที่เดียว พร้อม schema ที่ LLM ใช้ตัดสินใจว่าจะเรียก tool ไหน

Usage:
    from data_engine.tools.tool_registry import call_tool, list_tools, AVAILABLE_TOOLS_INFO

    result = call_tool("fetch_price", interval="5m", history_days=30)
    result = call_tool("detect_swing_low", interval="15m", history_days=3)
"""

import logging
from typing import Any

from tools.fetch_price      import fetch_price,       TOOL_NAME as PRICE_NAME, TOOL_DESCRIPTION as PRICE_DESC
from tools.fetch_indicators import fetch_indicators,   TOOL_NAME as IND_NAME,   TOOL_DESCRIPTION as IND_DESC
from tools.fetch_news       import fetch_news,         TOOL_NAME as NEWS_NAME,  TOOL_DESCRIPTION as NEWS_DESC
from tools.schema_validator import validate_market_state

# 1. Import จากโฟลเดอร์ analysis_tools ที่เราเพิ่งสร้าง
from data_engine.analysis_tools import TOOL_REGISTRY as ANALYSIS_TOOL_REGISTRY
from data_engine.analysis_tools import AVAILABLE_TOOLS_INFO as ANALYSIS_TOOLS_INFO

logger = logging.getLogger(__name__)

# 2. Registry ของฝั่งดึงข้อมูล (ฟอร์แมตเดิมของเพื่อน)
TOOL_REGISTRY: dict[str, Any] = {
    PRICE_NAME: {
        "fn":          fetch_price,
        "description": PRICE_DESC,
        "parameters": {
            "history_days": {"type": "int", "default": 90,    "description": "จำนวนวันย้อนหลัง OHLCV"},
            "interval":     {"type": "str", "default": "5m",  "description": "Timeframe: 1m|5m|15m|1h|1d"},
        },
    },
    IND_NAME: {
        "fn":          fetch_indicators,
        "description": IND_DESC,
        "parameters": {
            "ohlcv_df": {"type": "DataFrame", "required": True, "description": "OHLCV DataFrame จาก fetch_price"},
            "interval": {"type": "str",       "default":  "5m", "description": "Timeframe ที่ใช้ดึงข้อมูล"},
        },
    },
    NEWS_NAME: {
        "fn":          fetch_news,
        "description": NEWS_DESC,
        "parameters": {
            "max_per_category": {"type": "int", "default": 5, "description": "จำนวนข่าวสูงสุดต่อ category"},
        },
    },
}

# 3. รวม Registry ฝั่งวิเคราะห์ (ฟอร์แมตของเรา) เข้าไป
TOOL_REGISTRY.update(ANALYSIS_TOOL_REGISTRY)

# 4. จัดทำคู่มือแบบ Text (สำหรับส่งไปให้ LLM อ่านใน System Prompt)
AVAILABLE_TOOLS_INFO = """
### DATA FETCHING TOOLS (กลุ่มดึงข้อมูลดิบ) ###
1. "fetch_price": ดึงข้อมูลราคาทองคำปัจจุบันและ OHLCV
   - Arguments: {"history_days": 90, "interval": "5m"}
2. "fetch_indicators": คำนวณ Technical Indicators พื้นฐาน
   - Arguments: {"ohlcv_df": "<DataFrame>", "interval": "5m"}
3. "fetch_news": ดึงข่าวล่าสุด
   - Arguments: {"max_per_category": 5}
""" + "\n\n" + ANALYSIS_TOOLS_INFO


def call_tool(tool_name: str, **kwargs: Any) -> dict:
    """
    เรียก tool จาก registry

    Args:
        tool_name: ชื่อ tool ใน TOOL_REGISTRY
        **kwargs:  พารามิเตอร์ของ tool นั้นๆ

    Returns:
        ผลลัพธ์จาก tool function (dict เสมอ)
    """
    if tool_name not in TOOL_REGISTRY:
        available = list(TOOL_REGISTRY.keys())
        raise KeyError(f"Tool '{tool_name}' not found. Available: {available}")

    logger.info(f"[ToolRegistry] Calling '{tool_name}' with params={list(kwargs.keys())}")
    
    tool_target = TOOL_REGISTRY[tool_name]
    
    # 🎯 Smart Check: เช็คว่า Tool เป็นฟอร์แมตของเพื่อน (มีคีย์ "fn") หรือเป็นฟังก์ชันตรงๆ ของเรา
    if isinstance(tool_target, dict) and "fn" in tool_target:
        return tool_target["fn"](**kwargs)
    else:
        return tool_target(**kwargs)


def list_tools() -> list[dict]:
    """
    คืน list ของ tools ทั้งหมดพร้อม description และ parameter schema
    ใช้สำหรับบอก LLM ว่ามี tools อะไรให้เรียกใช้บ้างแบบ Array Object
    """
    tools_list = []
    for name, meta in TOOL_REGISTRY.items():
        if isinstance(meta, dict) and "description" in meta:
            tools_list.append({
                "name": name, 
                "description": meta["description"], 
                "parameters": meta.get("parameters", {})
            })
        else:
            # 🛡️ Fallback: ป้องกัน list_tools() พังเวลามันดึงข้อมูล Analysis Tools ของเรา
            tools_list.append({
                "name": name, 
                "description": f"Advanced Analysis Tool: {name}", 
                "parameters": {}
            })
    return tools_list