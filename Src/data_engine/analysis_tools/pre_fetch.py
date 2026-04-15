# data_engine/tools/pre_fetch.py

import asyncio
import logging
from typing import Any

# นำเข้า Tools ที่เป็นแกนหลักสำหรับการเทรด (แก้ไข path ให้ตรงกับโปรเจกต์ของคุณ)
from data_engine.analysis_tools.technical_tools import (
    get_htf_trend,
    get_support_resistance_zones,
)

from data_engine.analysis_tools.fundamental_tools import (
    check_upcoming_economic_calendar,
    get_deep_news_by_category
)

logger = logging.getLogger(__name__)

def _safe_tool_result(result: Any, tool_name: str) -> dict:
    """Helper สำหรับจัดการ Error จาก asyncio.gather"""
    if isinstance(result, Exception):
        logger.error(f"[PRE-FETCH] ❌ Tool '{tool_name}' failed: {str(result)}")
        return {"status": "error", "message": str(result)}
    
    # ถ้าฟังก์ชันของ tool คืนค่ามาเป็น dict อยู่แล้วให้ใช้เลย
    if isinstance(result, dict):
        return result
        
    # ถ้าคืนค่ามาเป็นอย่างอื่น ให้ห่อด้วย dict
    return {"status": "success", "data": result}

async def pre_fetch_market_data(session_context: dict = None) -> dict:
    """
    ดึงข้อมูล Core Tools 4 ตัวพร้อมกันก่อนเริ่ม AI ReAct Loop
    ใช้เวลาประมาณ 2-3 วินาที แทนที่จะเสียเวลา 1 Iteration ของ LLM
    """
    logger.info("🚀 [PRE-FETCH] Start fetching core tools concurrently...")

    # 1. ห่อ Tool เก่า (Synchronous) ด้วย to_thread เพื่อให้รันขนานกันได้
    task_trend = asyncio.to_thread(
        get_htf_trend, timeframe="1h", history_days=1
    )
    
    task_sr = asyncio.to_thread(
        get_support_resistance_zones, interval="15m", history_days=1
    )
    
    task_calendar = asyncio.to_thread(
        check_upcoming_economic_calendar, hours_ahead=4
    )
    
    # ดึงข่าวโดยใช้ Wrapper ของคุณ (ดึงข่าวภาพรวม/Fed)
    task_news = asyncio.to_thread(
        get_deep_news_by_category, category="fed_policy" 
    )

    # 2. ยิงคำสั่งดึงข้อมูลทั้งหมด 'พร้อมกัน'
    # return_exceptions=True สำคัญมาก! เพื่อไม่ให้บอทพังทั้งระบบถ้ามี 1 API ล่ม
    results = await asyncio.gather(
        task_trend, 
        task_sr, 
        task_calendar, 
        task_news, 
        return_exceptions=True
    )

    # 3. ประกอบร่าง Dictionary (จัด Format และเช็ค Error)
    pre_fetched_tools = {
        "get_htf_trend": _safe_tool_result(results[0], "get_htf_trend"),
        "get_support_resistance_zones": _safe_tool_result(results[1], "get_support_resistance_zones"),
        "check_upcoming_economic_calendar": _safe_tool_result(results[2], "check_upcoming_economic_calendar"),
        "get_deep_news_by_category": _safe_tool_result(results[3], "get_deep_news_by_category")
    }

    logger.info("✅ [PRE-FETCH] Done!")
    return pre_fetched_tools