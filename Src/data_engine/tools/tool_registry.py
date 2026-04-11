"""
tools/tool_registry.py — Registry สำหรับ LLM Agent
รวม tools ทั้งหมดไว้ที่เดียว พร้อม schema ที่ LLM ใช้ตัดสินใจว่าจะเรียก tool ไหน

Usage:
    from tools.tool_registry import call_tool, list_tools

    result = call_tool("fetch_price", interval="5m", history_days=30)
    result = call_tool("fetch_indicators", ohlcv_df=df, interval="5m")
    result = call_tool("fetch_news", max_per_category=5)
"""

import logging
from typing import Any

from tools.fetch_price      import fetch_price,       TOOL_NAME as PRICE_NAME, TOOL_DESCRIPTION as PRICE_DESC
from tools.fetch_indicators import fetch_indicators,   TOOL_NAME as IND_NAME,   TOOL_DESCRIPTION as IND_DESC
from tools.fetch_news       import fetch_news,         TOOL_NAME as NEWS_NAME,  TOOL_DESCRIPTION as NEWS_DESC
from tools.schema_validator import validate_market_state

logger = logging.getLogger(__name__)

TOOL_REGISTRY: dict[str, dict] = {
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


def call_tool(tool_name: str, **kwargs: Any) -> dict:
    """
    เรียก tool จาก registry

    Args:
        tool_name: ชื่อ tool ใน TOOL_REGISTRY
        **kwargs:  พารามิเตอร์ของ tool นั้นๆ

    Returns:
        ผลลัพธ์จาก tool function (dict เสมอ)

    Raises:
        KeyError: ถ้า tool_name ไม่อยู่ใน registry
    """
    if tool_name not in TOOL_REGISTRY:
        available = list(TOOL_REGISTRY.keys())
        raise KeyError(f"Tool '{tool_name}' not found. Available: {available}")

    logger.info(f"[ToolRegistry] Calling '{tool_name}' with params={list(kwargs.keys())}")
    return TOOL_REGISTRY[tool_name]["fn"](**kwargs)


def list_tools() -> list[dict]:
    """
    คืน list ของ tools ทั้งหมดพร้อม description และ parameter schema
    ใช้สำหรับบอก LLM ว่ามี tools อะไรให้เรียกใช้บ้าง
    """
    return [
        {"name": name, "description": meta["description"], "parameters": meta["parameters"]}
        for name, meta in TOOL_REGISTRY.items()
    ]
