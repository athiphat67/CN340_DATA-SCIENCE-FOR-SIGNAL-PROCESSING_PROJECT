"""
tools/tool_registry.py — Registry สำหรับ LLM Agent
รวม tools ไว้ที่เดียว แยกส่วน Internal (Orchestrator) และ Public (LLM)

Usage:
    from data_engine.tools.tool_registry import call_tool, list_tools, AVAILABLE_TOOLS_INFO

    # Orchestrator เรียกได้ (Internal) — ไม่ผ่าน scorer
    result = call_tool("fetch_price", interval="5m", history_days=30)

    # LLM เรียกได้ (Public) — ไม่ผ่าน scorer (single call เดิม)
    result = call_tool("detect_swing_low", interval="15m", history_days=3)

    # ─── NEW: เรียก tools พร้อม scoring ในครั้งเดียว ───────────────
    from data_engine.tools.tool_registry import execute_with_scoring

    report = execute_with_scoring([
        ("check_upcoming_economic_calendar", {"hours_ahead": 24}),
        ("detect_breakout_confirmation",     {"zone_top": 3250, "zone_bottom": 3200, "interval": "15m"}),
    ])

    if report.should_proceed:
        llm_context = [ts.tool_name for ts in report.tool_scores]  # ส่งต่อ LLM ได้เลย
    else:
        print(report.recommendations)   # ดูว่าต้อง call tool เพิ่มอะไร
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

# ─── NEW: Import ToolResultScorer ──────────────────────────────────────────────
from tools.tool_result_scorer import ToolResult, ToolResultScorer, ScoreReport

logger = logging.getLogger(__name__)

# ─── Scorer singleton (สร้างครั้งเดียว ใช้ร่วมกันทั้งไฟล์) ──────────────────────
_scorer = ToolResultScorer()

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


# ─────────────────────────────────────────────────────────────────────────────
# ฟังก์ชันเดิม — ไม่เปลี่ยนแปลง (Backward Compatible)
# ─────────────────────────────────────────────────────────────────────────────

def call_tool(tool_name: str, **kwargs: Any) -> dict:
    """
    เรียก tool จาก TOOL_REGISTRY (Orchestrator และ LLM เรียกผ่านที่นี่)
    คืน dict ตรงๆ ไม่ผ่าน scorer — เหมือนเดิมทุกอย่าง
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
                "parameters": meta.get("parameters", {}),
            })
        else:
            # Fallback ป้องกัน list_tools() พัง
            tools_list.append({
                "name": name,
                "description": f"Advanced Analysis Tool: {name}",
                "parameters": {},
            })
    return tools_list


# ─────────────────────────────────────────────────────────────────────────────
# NEW — ฟังก์ชันเสริม สำหรับ Scoring Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def call_tool_as_result(
    tool_name: str,
    weight: float = 1.0,
    **kwargs: Any,
) -> ToolResult:
    """
    เรียก tool เดียว แล้วห่อผลลัพธ์เป็น ToolResult ทันที

    ใช้เมื่อต้องการ call tool ทีละตัวแต่ยังอยากรวม score ทีหลัง
    Internal Tools (fetch_price ฯลฯ) ก็เรียกได้ แต่ scorer จะ skip ถ้าชื่อไม่รู้จัก

    Args:
        tool_name: ชื่อ tool ใน TOOL_REGISTRY
        weight:    ความสำคัญของ tool นี้ใน context ปัจจุบัน (default 1.0)
        **kwargs:  params ส่งต่อให้ tool ตรงๆ

    Returns:
        ToolResult พร้อม output และ params ที่ใช้ call
    """
    output = call_tool(tool_name, **kwargs)
    return ToolResult(
        tool_name=tool_name,
        output=output,
        params=dict(kwargs),
        weight=weight,
    )


def execute_with_scoring(
    tool_calls: list[tuple[str, dict]],
    weights: dict[str, float] | None = None,
    max_rounds: int = 3,
) -> ScoreReport:
    """
    เรียก tools หลายตัวพร้อมกัน → score → loop ถ้าคะแนนไม่ถึง 0.6

    Pipeline:
        1. Call tools ทุกตัวใน tool_calls
        2. ส่งผลทั้งหมดเข้า ToolResultScorer
        3. ถ้า avg score < 0.6 → call tools ที่ scorer แนะนำเพิ่ม
        4. วน loop ซ้ำจนกว่าจะผ่าน หรือครบ max_rounds
        5. คืน ScoreReport สุดท้าย (should_proceed + tool_scores + recommendations)

    Args:
        tool_calls:  list ของ (tool_name, params_dict) ที่จะ call รอบแรก
                     ตย. [("detect_breakout_confirmation", {"interval": "15m"})]
        weights:     dict ของ {tool_name: weight} สำหรับ tool ที่ต้องการให้น้ำหนักพิเศษ
                     ตย. {"check_upcoming_economic_calendar": 1.5}
                     tool ที่ไม่ระบุ weight จะได้ 1.0
        max_rounds:  จำนวนรอบ retry สูงสุด (default 3) ป้องกัน infinite loop

    Returns:
        ScoreReport ที่มี:
            - tool_scores:       คะแนนและเหตุผลของแต่ละ tool
            - avg_score:         weighted average ของทุก tool
            - should_proceed:    True ถ้าพร้อมส่งเข้า LLM
            - recommendations:   tool ที่ควร call เพิ่ม (ว่างถ้า should_proceed=True)
            - summary:           สรุปสั้นๆ สำหรับ log

    Example:
        report = execute_with_scoring(
            tool_calls=[
                ("check_upcoming_economic_calendar", {"hours_ahead": 24}),
                ("detect_breakout_confirmation",     {"zone_top": 3250, "zone_bottom": 3200, "interval": "15m"}),
                ("get_htf_trend",                   {"timeframe": "1h"}),
            ],
            weights={"check_upcoming_economic_calendar": 1.5},
            max_rounds=3,
        )

        if report.should_proceed:
            # รวม outputs ทั้งหมดเพื่อส่งเข้า LLM
            llm_context = {ts.tool_name: ... for ts in report.tool_scores}
        else:
            # ดู recommendations เพื่อตัดสินใจว่าจะ retry หรือ proceed ด้วย context ที่มี
            for rec in report.recommendations:
                print(f"แนะนำ call: {rec.recommended_tool} params={rec.suggested_params}")
    """
    weights = weights or {}

    # ── Round 1: Call tools ชุดแรก ─────────────────────────────────────────
    results: list[ToolResult] = []
    for tool_name, params in tool_calls:
        try:
            w = weights.get(tool_name, 1.0)
            result = call_tool_as_result(tool_name, weight=w, **params)
            results.append(result)
        except KeyError as e:
            logger.warning(f"[execute_with_scoring] Tool ไม่พบ: {e} — ข้ามไป")
        except Exception as e:
            # ถ้า tool crash → สร้าง ToolResult ที่ status=error เพื่อให้ scorer ให้ 0.0
            logger.error(f"[execute_with_scoring] '{tool_name}' error: {e}")
            results.append(ToolResult(
                tool_name=tool_name,
                output={"status": "error", "message": str(e)},
                params=params,
                weight=weights.get(tool_name, 1.0),
            ))

    report = _scorer.score(results)
    logger.info(f"[execute_with_scoring] Round 1 — {report.summary}")

    # ── Retry Loop: ตาม recommendations จนกว่าผ่านหรือหมด rounds ──────────
    for round_num in range(2, max_rounds + 1):
        if report.should_proceed:
            break

        if not report.recommendations:
            logger.info(f"[execute_with_scoring] ไม่มี recommendations เหลือ — หยุดที่ round {round_num - 1}")
            break

        logger.info(f"[execute_with_scoring] Round {round_num} — call {len(report.recommendations)} tools เพิ่ม")

        for rec in report.recommendations:
            try:
                w = weights.get(rec.recommended_tool, 1.0)
                new_result = call_tool_as_result(rec.recommended_tool, weight=w, **rec.suggested_params)
                results.append(new_result)
                logger.info(f"[execute_with_scoring] ✅ '{rec.recommended_tool}' called — reason: {rec.reason}")
            except KeyError as e:
                logger.warning(f"[execute_with_scoring] Recommended tool ไม่พบ: {e} — ข้ามไป")
            except Exception as e:
                logger.error(f"[execute_with_scoring] '{rec.recommended_tool}' error: {e}")
                results.append(ToolResult(
                    tool_name=rec.recommended_tool,
                    output={"status": "error", "message": str(e)},
                    params=rec.suggested_params,
                    weight=w,
                ))

        report = _scorer.score(results)
        logger.info(f"[execute_with_scoring] Round {round_num} — {report.summary}")

    # ── Log สรุปผลสุดท้าย ──────────────────────────────────────────────────
    if report.should_proceed:
        logger.info(
            f"[execute_with_scoring] ✅ PROCEED — avg={report.avg_score:.3f} "
            f"| {len(results)} tools called"
        )
    else:
        logger.warning(
            f"[execute_with_scoring] ⚠️ LOW SCORE หลัง {max_rounds} rounds — "
            f"avg={report.avg_score:.3f} | proceed ต่อด้วย context ที่มีอยู่"
        )

    return report