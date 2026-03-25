"""
prompts.py
----------
สร้าง System Prompt และ User Prompt ที่ส่งให้ Gemini LLM ในแต่ละขั้นตอน
ของ ReAct loop

หน้าที่หลัก:
  1. กำหนด "บุคลิก" ของ LLM ว่าเป็น AI เทรดทองคำ
  2. บังคับให้ LLM ตอบเป็น JSON เสมอ
  3. สร้าง prompt ที่แตกต่างกันตามขั้นตอน (Thought 1, Thought 2, Final)
"""

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# System Prompt — โหลดครั้งเดียวตอนเริ่มต้น
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
คุณคือ GoldTrader-AI ระบบวิเคราะห์และตัดสินใจเทรดทองคำอัตโนมัติ

## กฎเหล็กที่ห้ามละเมิด
1. ตอบเป็น JSON เท่านั้น — ห้ามมีข้อความอื่นนอก JSON block
2. ห้ามคำนวณตัวเลขด้วยตัวเอง — ใช้ tool ที่กำหนดเท่านั้น
3. ห้าม hallucinate ราคาหรือตัวเลขที่ไม่ได้รับมาจาก tool
4. ทุก action ต้องอยู่ใน enum ที่กำหนด: CALL_TOOL | FINAL_DECISION | NEED_SKILL

## โครงสร้าง JSON ที่อนุญาต

### เมื่อต้องการดู SKILL.md ก่อน:
```json
{
  "thought": "<เหตุผลที่ต้องการ tool>",
  "action": "NEED_SKILL",
  "reason": "<อธิบายว่าต้องการ tool ชนิดไหน>"
}
```

### เมื่อต้องการเรียก tool:
```json
{
  "thought": "<reasoning ก่อนเรียก tool>",
  "action": "CALL_TOOL",
  "tool_name": "<ชื่อ tool จาก SKILL.md>",
  "tool_args": {}
}
```

### เมื่อพร้อมตัดสินใจ:
```json
{
  "thought": "<reasoning สุดท้าย>",
  "action": "FINAL_DECISION",
  "signal": "BUY | SELL | HOLD",
  "confidence": 0.0,
  "entry_price": 0.0,
  "stop_loss": 0.0,
  "take_profit": 0.0,
  "rationale": "<อธิบายเหตุผล>",
  "key_factors": []
}
```

## หลักการวิเคราะห์ทองคำ
- ทองคำวิ่งสวนทางกับ Dollar Index (DXY) เสมอ
- FED ลดดอกเบี้ย = ดีกับทอง | FED ขึ้นดอกเบี้ย = แย่กับทอง
- VIX สูง (>20) = นักลงทุนกลัว = ซื้อทองเพิ่ม
- RSI < 30 = oversold (โอกาสซื้อ) | RSI > 70 = overbought (โอกาสขาย)
- ข่าวสงคราม/วิกฤต = ทองขึ้น (safe haven)

## เกณฑ์ confidence
- 0.8–1.0 = สัญญาณแข็งแกร่งมาก
- 0.6–0.8 = สัญญาณดี
- 0.4–0.6 = ไม่แน่ใจ พิจารณา HOLD
- < 0.4 = ข้อมูลขัดแย้ง ให้ HOLD เสมอ
""".strip()


# ---------------------------------------------------------------------------
# Prompt builders — สร้าง user prompt แต่ละขั้นตอน
# ---------------------------------------------------------------------------

@dataclass
class PromptPackage:
    """สิ่งที่ส่งให้ Gemini API"""
    system: str
    user: str
    step_label: str          # ชื่อ step สำหรับ log


def build_initial_analysis_prompt(market_state: dict[str, Any]) -> PromptPackage:
    """
    Step 2: Thought 1 — ส่ง Market State ให้ LLM ประเมินครั้งแรก
    LLM จะตัดสินใจว่าต้องดู SKILL.md, เรียก tool, หรือตัดสินใจได้เลย
    """
    market_json = _format_market_state(market_state)

    user_prompt = f"""
## ข้อมูลตลาดปัจจุบัน (Market State)
{market_json}

## คำถาม
วิเคราะห์ข้อมูลด้านบนและตอบว่า:
- ข้อมูลเพียงพอสำหรับการตัดสินใจเทรดหรือไม่?
- ถ้าไม่พอ ต้องการข้อมูลเพิ่มเติมอะไร?

ตอบเป็น JSON ตามรูปแบบใน System Prompt เท่านั้น
""".strip()

    return PromptPackage(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        step_label="THOUGHT_1_INITIAL"
    )


def build_skill_request_prompt(
    market_state: dict[str, Any],
    skill_content: str,
) -> PromptPackage:
    """
    Step 3: Progressive Disclosure — ส่ง SKILL.md ให้ LLM อ่าน
    LLM จะรู้ว่าต้องเรียก tool ชื่ออะไร และใส่ argument อะไร
    """
    market_json = _format_market_state(market_state)

    user_prompt = f"""
## ข้อมูลตลาดปัจจุบัน (Market State)
{market_json}

## คู่มือ Tools ที่ใช้ได้ (SKILL.md)
{skill_content}

## คำถาม
อ่าน SKILL.md แล้วตัดสินใจว่าจะเรียก tool ใด เพื่อรวบรวมข้อมูลเพิ่มเติม
ตอบเป็น JSON รูปแบบ CALL_TOOL เท่านั้น
""".strip()

    return PromptPackage(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        step_label="THOUGHT_1_SKILL_LOADED"
    )


def build_final_decision_prompt(
    market_state: dict[str, Any],
    tool_results: list[dict[str, Any]],
    skill_content: str,
) -> PromptPackage:
    """
    Step 5: Thought 2 — ส่งทุกอย่างรวมกัน (Market State + ผลจาก tools)
    LLM จะวิเคราะห์รอบสุดท้ายและออก FINAL_DECISION
    """
    market_json   = _format_market_state(market_state)
    tools_json    = _format_tool_results(tool_results)

    user_prompt = f"""
## ข้อมูลตลาดปัจจุบัน (Market State)
{market_json}

## ผลจาก Tools ที่เรียกไปแล้ว
{tools_json}

## คู่มือ Tools (SKILL.md — สำหรับอ้างอิง)
{skill_content}

## คำสั่ง
รวมข้อมูลทั้งหมดแล้วตัดสินใจขั้นสุดท้าย
ตอบเป็น JSON รูปแบบ FINAL_DECISION เท่านั้น
ห้าม CALL_TOOL อีกแล้ว — ถึงเวลาตัดสินใจแล้ว
""".strip()

    return PromptPackage(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        step_label="THOUGHT_2_FINAL"
    )


def build_conflict_resolution_prompt(
    market_state: dict[str, Any],
    tool_results: list[dict[str, Any]],
    conflict_description: str,
) -> PromptPackage:
    """
    Bonus: เมื่อ signals ขัดแย้งกัน — ส่งให้ LLM ชั่งน้ำหนักและ HOLD
    """
    market_json = _format_market_state(market_state)
    tools_json  = _format_tool_results(tool_results)

    user_prompt = f"""
## ปัญหาที่พบ: Signals ขัดแย้งกัน
{conflict_description}

## ข้อมูลตลาด
{market_json}

## ผลจาก Tools
{tools_json}

## คำสั่ง
อธิบายว่า signal ไหนน่าเชื่อถือกว่า และตัดสินใจ
ถ้าไม่แน่ใจจริง ๆ ให้ HOLD พร้อมอธิบายเหตุผล
ตอบเป็น JSON รูปแบบ FINAL_DECISION เท่านั้น
""".strip()

    return PromptPackage(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        step_label="CONFLICT_RESOLUTION"
    )


# ---------------------------------------------------------------------------
# Formatters — แปลง dict เป็น string อ่านง่ายสำหรับ LLM
# ---------------------------------------------------------------------------

def _format_market_state(market_state: dict[str, Any]) -> str:
    import json
    return json.dumps(market_state, indent=2, ensure_ascii=False)


def _format_tool_results(tool_results: list[dict[str, Any]]) -> str:
    import json
    if not tool_results:
        return "ยังไม่มีผลจาก tool"
    output = []
    for i, result in enumerate(tool_results, 1):
        tool_name = result.get("tool", f"tool_{i}")
        output.append(f"### ผลจาก {tool_name} (การเรียกครั้งที่ {i})")
        output.append(json.dumps(result, indent=2, ensure_ascii=False))
    return "\n\n".join(output)


# ---------------------------------------------------------------------------
# Smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_market = {
        "timestamp": "2025-03-25T08:00:00Z",
        "gold_price_usd": 3025.40,
        "rsi_1h": 28.5,
        "macd_signal": "bullish_crossover",
        "dxy": 103.72,
        "vix": 18.4,
        "us10y_yield": 4.31,
    }

    pkg = build_initial_analysis_prompt(sample_market)
    print(f"[prompts] Step: {pkg.step_label}")
    print(f"[prompts] System prompt length: {len(pkg.system)} chars")
    print(f"[prompts] User prompt preview:\n{pkg.user[:300]}...")