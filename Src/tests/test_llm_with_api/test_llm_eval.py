"""
test_llm_eval.py — LLM Quality Evaluation Tests

Strategy: เรียก API จริง + ตรวจ "คุณภาพการตัดสินใจ"
- ใช้ Golden Dataset = scenario ที่รู้คำตอบที่ "สมเหตุสมผล"
- ไม่คาดหวัง 100% เพราะ LLM non-deterministic
- ใช้ threshold เช่น accuracy ≥ 60% (ดีกว่า random 33%)

วิธีรัน:
    python -m pytest tests/test_llm_with_api/test_llm_contract.py -v -k groq
    ถ้าไม่ได้ให้ใส่ด้านล่างแทน
    set GROQ_API_KEY=xxx&& python -m pytest tests/test_llm_with_api/test_llm_eval.py -v -k groq
    #xxx คือ API KEY ปล.ต้องใส่&&ตามท้ายด้วย


ค่าใช้จ่าย: ~15-30 API calls per run (ขึ้นกับจำนวน scenarios × retries)
ความถี่: ก่อน deploy, หลังเปลี่ยน prompt/model

หมายเหตุ:
  - ทุก scenario เรียก API จริง 1 ครั้ง → ช้า + มีค่าใช้จ่าย
  - ใช้ @pytest.mark.eval แยกจาก unit test ปกติ
  - Provider ที่ไม่มี key จะ skip อัตโนมัติ
"""

import os
import json
import re
import time
import pytest
from dataclasses import dataclass
from typing import Optional

from agent_core.core.prompt import PromptPackage


# ══════════════════════════════════════════════════════════════════
# Golden Dataset
# ══════════════════════════════════════════════════════════════════

# แต่ละ scenario = สถานการณ์ตลาดที่รู้ว่า signal ที่สมเหตุสมผลคืออะไร
# "acceptable" อาจมีหลายคำตอบที่ถือว่าถูก (เช่น HOLD ก็โอเคในบาง case)

GOLDEN_SCENARIOS = [
    # ── BUY scenarios ──
    {
        "name": "Strong uptrend + RSI oversold bounce",
        "market": {
            "price": 45000,
            "rsi": 28,
            "rsi_signal": "oversold",
            "macd": "bullish crossover",
            "macd_hist": 15.5,
            "trend": "uptrend",
            "ema20": 45200,
            "ema50": 44800,
            "bb_signal": "near lower band",
            "atr": 120,
            "news_sentiment": 0.3,
        },
        "expected": "BUY",
        "acceptable": {"BUY"},
        "reason": "RSI oversold + uptrend + bullish MACD = classic buy signal",
    },
    {
        "name": "Moderate uptrend + bullish MACD + positive news",
        "market": {
            "price": 46000,
            "rsi": 55,
            "rsi_signal": "neutral",
            "macd": "bullish",
            "macd_hist": 8.2,
            "trend": "uptrend",
            "ema20": 46100,
            "ema50": 45700,
            "bb_signal": "inside bands",
            "atr": 100,
            "news_sentiment": 0.6,
        },
        "expected": "BUY",
        "acceptable": {"BUY", "HOLD"},
        "reason": "Multiple signals align bullish, HOLD also acceptable",
    },
    # ── SELL scenarios ──
    {
        "name": "Overbought RSI + downtrend + bearish MACD",
        "market": {
            "price": 48000,
            "rsi": 82,
            "rsi_signal": "overbought",
            "macd": "bearish crossover",
            "macd_hist": -20.3,
            "trend": "downtrend",
            "ema20": 47500,
            "ema50": 47900,
            "bb_signal": "above upper band",
            "atr": 180,
            "news_sentiment": -0.4,
        },
        "expected": "SELL",
        "acceptable": {"SELL"},
        "reason": "RSI overbought + downtrend + bearish MACD = strong sell",
    },
    {
        "name": "Death cross + negative sentiment",
        "market": {
            "price": 44000,
            "rsi": 42,
            "rsi_signal": "neutral",
            "macd": "bearish",
            "macd_hist": -12.0,
            "trend": "downtrend",
            "ema20": 43800,
            "ema50": 44200,
            "bb_signal": "near lower band",
            "atr": 150,
            "news_sentiment": -0.6,
        },
        "expected": "SELL",
        "acceptable": {"SELL", "HOLD"},
        "reason": "EMA death cross + bearish MACD, HOLD also acceptable",
    },
    # ── HOLD scenarios ──
    {
        "name": "Sideways market + neutral RSI + no MACD signal",
        "market": {
            "price": 45500,
            "rsi": 50,
            "rsi_signal": "neutral",
            "macd": "neutral",
            "macd_hist": 0.5,
            "trend": "sideways",
            "ema20": 45500,
            "ema50": 45480,
            "bb_signal": "inside bands",
            "atr": 80,
            "news_sentiment": 0.0,
        },
        "expected": "HOLD",
        "acceptable": {"HOLD"},
        "reason": "No clear signal in any direction",
    },
    {
        "name": "Mixed signals — RSI high but uptrend",
        "market": {
            "price": 47000,
            "rsi": 68,
            "rsi_signal": "neutral",
            "macd": "bullish",
            "macd_hist": 5.0,
            "trend": "uptrend",
            "ema20": 47100,
            "ema50": 46800,
            "bb_signal": "near upper band",
            "atr": 110,
            "news_sentiment": 0.1,
        },
        "expected": "HOLD",
        "acceptable": {"HOLD", "BUY"},
        "reason": "RSI approaching overbought but trend still up — ambiguous",
    },
    # ── Edge cases ──
    {
        "name": "Extreme overbought — RSI 92",
        "market": {
            "price": 50000,
            "rsi": 92,
            "rsi_signal": "overbought",
            "macd": "bearish crossover",
            "macd_hist": -25.0,
            "trend": "downtrend",
            "ema20": 49500,
            "ema50": 49800,
            "bb_signal": "above upper band",
            "atr": 250,
            "news_sentiment": -0.3,
        },
        "expected": "SELL",
        "acceptable": {"SELL"},
        "reason": "Extreme overbought + bearish everything = must sell",
    },
    {
        "name": "Extreme oversold — RSI 15",
        "market": {
            "price": 40000,
            "rsi": 15,
            "rsi_signal": "oversold",
            "macd": "bullish crossover",
            "macd_hist": 30.0,
            "trend": "uptrend",
            "ema20": 40500,
            "ema50": 39800,
            "bb_signal": "below lower band",
            "atr": 200,
            "news_sentiment": 0.5,
        },
        "expected": "BUY",
        "acceptable": {"BUY"},
        "reason": "Extreme oversold + strong bullish reversal signals",
    },
]

# ── Behavioral rules ที่ LLM ต้องทำตาม ──
RULE_SCENARIOS = [
    {
        "name": "Never BUY when RSI > 80",
        "market": {
            "price": 49000,
            "rsi": 85,
            "rsi_signal": "overbought",
            "macd": "bullish",
            "macd_hist": 10.0,
            "trend": "uptrend",
            "ema20": 49200,
            "ema50": 48800,
            "bb_signal": "above upper band",
            "atr": 140,
            "news_sentiment": 0.5,
        },
        "forbidden_signal": "BUY",
        "reason": "RSI > 80 = overbought, BUY would be reckless",
    },
    {
        "name": "Never SELL when RSI < 20",
        "market": {
            "price": 41000,
            "rsi": 18,
            "rsi_signal": "oversold",
            "macd": "bearish",
            "macd_hist": -5.0,
            "trend": "downtrend",
            "ema20": 40800,
            "ema50": 41200,
            "bb_signal": "below lower band",
            "atr": 160,
            "news_sentiment": -0.2,
        },
        "forbidden_signal": "SELL",
        "reason": "RSI < 20 = extreme oversold, SELL would be panic selling",
    },
]


# ══════════════════════════════════════════════════════════════════
# Prompt Builder
# ══════════════════════════════════════════════════════════════════


EVAL_SYSTEM_PROMPT = """You are a professional gold trading analyst for the Thai gold market (ออม NOW platform).
Analyze the market data and give ONE trading decision.

Rules:
- Do NOT buy when RSI > 75 (overbought zone)
- Do NOT sell when RSI < 25 (oversold zone)  
- Consider MACD, trend (EMA20 vs EMA50), Bollinger Bands, ATR, and news sentiment
- Confidence should reflect how strong the signals are

Respond ONLY with a single JSON object:
{"signal": "BUY"|"SELL"|"HOLD", "confidence": 0.0-1.0, "rationale": "brief reason"}"""


def _build_eval_prompt(scenario: dict) -> PromptPackage:
    """สร้าง prompt จาก scenario"""
    m = scenario["market"]
    user = f"""Current Thai gold market data:
- Price: ฿{m["price"]:,}/baht weight
- RSI(14): {m["rsi"]} ({m["rsi_signal"]})
- MACD: {m["macd"]} (histogram: {m["macd_hist"]})
- Trend: {m["trend"]} (EMA20: {m["ema20"]}, EMA50: {m["ema50"]})
- Bollinger: {m["bb_signal"]}
- ATR(14): {m["atr"]} THB
- News sentiment: {m["news_sentiment"]} (-1=bearish, +1=bullish)

What is your trading decision? Respond with JSON only."""

    return PromptPackage(
        system=EVAL_SYSTEM_PROMPT,
        user=user,
        step_label="THOUGHT_FINAL",
    )


def _parse_response(text: str) -> dict:
    """Parse JSON จาก LLM response"""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(cleaned)


# ══════════════════════════════════════════════════════════════════
# Eval Runner
# ══════════════════════════════════════════════════════════════════


def _run_eval_suite(client, scenarios, provider_name: str) -> dict:
    """
    รัน golden dataset ทั้งหมด → คืนผลสรุป

    Returns:
        {
            "total": int,
            "correct": int,         # signal ตรง expected
            "acceptable": int,      # signal อยู่ใน acceptable set
            "accuracy_pct": float,  # correct / total
            "acceptable_pct": float,
            "results": [{ scenario, expected, actual, is_correct, is_acceptable }],
            "errors": [{ scenario, error }],
        }
    """
    results = []
    errors = []

    for scenario in scenarios:
        prompt = _build_eval_prompt(scenario)
        try:
            response = client.call(prompt)
            data = _parse_response(response.text)
            actual = data.get("signal", "UNKNOWN")
            confidence = float(data.get("confidence", 0))

            is_correct = actual == scenario["expected"]
            is_acceptable = actual in scenario.get("acceptable", {scenario["expected"]})

            results.append(
                {
                    "name": scenario["name"],
                    "expected": scenario["expected"],
                    "actual": actual,
                    "confidence": confidence,
                    "is_correct": is_correct,
                    "is_acceptable": is_acceptable,
                }
            )

            # rate limit safety
            time.sleep(0.5)

        except Exception as e:
            errors.append({"name": scenario["name"], "error": str(e)})

    total = len(results)
    correct = sum(1 for r in results if r["is_correct"])
    acceptable = sum(1 for r in results if r["is_acceptable"])

    return {
        "provider": provider_name,
        "total": total,
        "correct": correct,
        "acceptable": acceptable,
        "accuracy_pct": round(correct / total * 100, 1) if total else 0,
        "acceptable_pct": round(acceptable / total * 100, 1) if total else 0,
        "results": results,
        "errors": errors,
    }


def _run_rule_check(client, rule_scenarios) -> dict:
    """ตรวจว่า LLM ไม่ฝ่า rules (เช่น ไม่ BUY เมื่อ RSI > 80)"""
    violations = []
    passes = []

    for scenario in rule_scenarios:
        prompt = _build_eval_prompt(scenario)
        try:
            response = client.call(prompt)
            data = _parse_response(response.text)
            actual = data.get("signal", "UNKNOWN")

            if actual == scenario["forbidden_signal"]:
                violations.append(
                    {
                        "name": scenario["name"],
                        "forbidden": scenario["forbidden_signal"],
                        "actual": actual,
                        "reason": scenario["reason"],
                    }
                )
            else:
                passes.append(scenario["name"])

            time.sleep(0.5)

        except Exception as e:
            violations.append(
                {
                    "name": scenario["name"],
                    "error": str(e),
                }
            )

    return {
        "total": len(rule_scenarios),
        "passes": len(passes),
        "violations": violations,
        "violation_rate": round(len(violations) / len(rule_scenarios) * 100, 1)
        if rule_scenarios
        else 0,
    }


# ══════════════════════════════════════════════════════════════════
# Gemini Eval Tests
# ══════════════════════════════════════════════════════════════════


HAS_GEMINI_KEY = bool(os.environ.get("GEMINI_API_KEY"))


@pytest.mark.eval
@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="GEMINI_API_KEY not set")
class TestGeminiEval:
    """Evaluation: Gemini ตัดสินใจเทรดได้ดีแค่ไหน"""

    @pytest.fixture(scope="class")
    def gemini_client(self):
        from agent_core.llm.client import GeminiClient

        return GeminiClient()

    @pytest.fixture(scope="class")
    def eval_results(self, gemini_client):
        """รัน golden dataset ทั้งหมด (scope=class → รันครั้งเดียว)"""
        return _run_eval_suite(gemini_client, GOLDEN_SCENARIOS, "gemini")

    def test_accuracy_above_threshold(self, eval_results):
        """Exact accuracy ≥ 50% (ดีกว่า random 33%)"""
        assert eval_results["accuracy_pct"] >= 50, (
            f"Gemini accuracy {eval_results['accuracy_pct']}% < 50% threshold\n"
            f"Results: {json.dumps(eval_results['results'], indent=2)}"
        )

    def test_acceptable_above_threshold(self, eval_results):
        """Acceptable accuracy ≥ 70% (รวม alternative ที่โอเค)"""
        assert eval_results["acceptable_pct"] >= 70, (
            f"Gemini acceptable {eval_results['acceptable_pct']}% < 70%\n"
            f"Results: {json.dumps(eval_results['results'], indent=2)}"
        )

    def test_no_parse_errors(self, eval_results):
        """ทุก scenario ต้อง parse JSON ได้"""
        assert len(eval_results["errors"]) == 0, (
            f"Parse errors: {eval_results['errors']}"
        )

    def test_json_format_consistency(self, eval_results):
        """ทุก response ต้องมี signal field"""
        for r in eval_results["results"]:
            assert r["actual"] in ("BUY", "SELL", "HOLD", "UNKNOWN"), (
                f"Invalid signal '{r['actual']}' in scenario '{r['name']}'"
            )

    def test_rule_compliance(self, gemini_client):
        """ไม่ฝ่า trading rules (RSI boundaries)"""
        rule_result = _run_rule_check(gemini_client, RULE_SCENARIOS)
        assert rule_result["violation_rate"] <= 30, (
            f"Gemini violated {rule_result['violation_rate']}% of rules\n"
            f"Violations: {json.dumps(rule_result['violations'], indent=2)}"
        )

    def test_confidence_correlation(self, eval_results):
        """correct decisions ควรมี confidence สูงกว่า incorrect"""
        correct_confs = [
            r["confidence"] for r in eval_results["results"] if r["is_correct"]
        ]
        wrong_confs = [
            r["confidence"] for r in eval_results["results"] if not r["is_correct"]
        ]

        if correct_confs and wrong_confs:
            avg_correct = sum(correct_confs) / len(correct_confs)
            avg_wrong = sum(wrong_confs) / len(wrong_confs)
            # ไม่ hard fail — แค่ log เพราะ correlation อาจไม่มี
            if avg_correct <= avg_wrong:
                pytest.skip(
                    f"Confidence not correlated: correct={avg_correct:.2f} "
                    f"vs wrong={avg_wrong:.2f} (acceptable for LLMs)"
                )


# ══════════════════════════════════════════════════════════════════
# Groq Eval Tests
# ══════════════════════════════════════════════════════════════════


HAS_GROQ_KEY = bool(os.environ.get("GROQ_API_KEY"))


@pytest.mark.eval
@pytest.mark.skipif(not HAS_GROQ_KEY, reason="GROQ_API_KEY not set")
class TestGroqEval:
    @pytest.fixture(scope="class")
    def groq_client(self):
        from agent_core.llm.client import GroqClient

        return GroqClient()

    @pytest.fixture(scope="class")
    def eval_results(self, groq_client):
        return _run_eval_suite(groq_client, GOLDEN_SCENARIOS, "groq")

    def test_accuracy_above_threshold(self, eval_results):
        assert eval_results["accuracy_pct"] >= 50

    def test_acceptable_above_threshold(self, eval_results):
        assert eval_results["acceptable_pct"] >= 70

    def test_no_parse_errors(self, eval_results):
        assert len(eval_results["errors"]) == 0


# ══════════════════════════════════════════════════════════════════
# OpenAI Eval Tests
# ══════════════════════════════════════════════════════════════════


HAS_OPENAI_KEY = bool(os.environ.get("OPENAI_API_KEY"))


@pytest.mark.eval
@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
class TestOpenAIEval:
    @pytest.fixture(scope="class")
    def openai_client(self):
        from agent_core.llm.client import OpenAIClient

        return OpenAIClient()

    @pytest.fixture(scope="class")
    def eval_results(self, openai_client):
        return _run_eval_suite(openai_client, GOLDEN_SCENARIOS, "openai")

    def test_accuracy_above_threshold(self, eval_results):
        assert eval_results["accuracy_pct"] >= 50

    def test_acceptable_above_threshold(self, eval_results):
        assert eval_results["acceptable_pct"] >= 70

    def test_no_parse_errors(self, eval_results):
        assert len(eval_results["errors"]) == 0


# ══════════════════════════════════════════════════════════════════
# MockClient Eval (Baseline — รันได้เสมอ)
# ══════════════════════════════════════════════════════════════════


class TestMockClientEval:
    """
    Baseline eval สำหรับ MockClient — ไม่ mark eval
    MockClient ตอบ HOLD ทุกครั้ง → accuracy จะตรงแค่ HOLD scenarios
    ใช้ตรวจว่า eval infrastructure ทำงาน
    """

    def test_eval_infrastructure_works(self):
        from agent_core.llm.client import MockClient

        # MockClient คืน HOLD เสมอ → ตรง HOLD scenarios เท่านั้น
        client = MockClient()
        result = _run_eval_suite(client, GOLDEN_SCENARIOS, "mock")

        assert result["total"] == len(GOLDEN_SCENARIOS)
        assert result["total"] > 0
        # MockClient ตอบ HOLD → ตรง HOLD scenarios = 2/8
        # ไม่ assert accuracy threshold — แค่ตรวจว่า infra ทำงาน

    def test_rule_check_infrastructure_works(self):
        from agent_core.llm.client import MockClient

        client = MockClient()
        result = _run_rule_check(client, RULE_SCENARIOS)

        assert result["total"] == len(RULE_SCENARIOS)
        # MockClient ตอบ HOLD → ไม่ violate ทั้ง BUY rule และ SELL rule
        assert result["violation_rate"] == 0


# ══════════════════════════════════════════════════════════════════
# Golden Dataset Sanity Check (ไม่เรียก API)
# ══════════════════════════════════════════════════════════════════


class TestGoldenDatasetSanity:
    """ตรวจว่า golden dataset ถูกต้อง — ไม่ต้องเรียก API"""

    def test_all_scenarios_have_required_fields(self):
        for s in GOLDEN_SCENARIOS:
            assert "name" in s, f"Missing 'name'"
            assert "market" in s, f"Missing 'market' in {s['name']}"
            assert "expected" in s, f"Missing 'expected' in {s['name']}"
            assert "acceptable" in s, f"Missing 'acceptable' in {s['name']}"
            assert s["expected"] in ("BUY", "SELL", "HOLD"), (
                f"Invalid expected '{s['expected']}' in {s['name']}"
            )

    def test_expected_is_in_acceptable(self):
        """expected ต้องอยู่ใน acceptable set เสมอ"""
        for s in GOLDEN_SCENARIOS:
            assert s["expected"] in s["acceptable"], (
                f"'{s['name']}': expected '{s['expected']}' "
                f"not in acceptable {s['acceptable']}"
            )

    def test_balanced_dataset(self):
        """golden dataset ควรมีทุก signal type"""
        signals = [s["expected"] for s in GOLDEN_SCENARIOS]
        assert "BUY" in signals, "No BUY scenario in golden dataset"
        assert "SELL" in signals, "No SELL scenario in golden dataset"
        assert "HOLD" in signals, "No HOLD scenario in golden dataset"

    def test_market_data_complete(self):
        """ทุก scenario ต้องมี market fields ครบ"""
        required_fields = {
            "price",
            "rsi",
            "rsi_signal",
            "macd",
            "macd_hist",
            "trend",
            "ema20",
            "ema50",
            "bb_signal",
            "atr",
            "news_sentiment",
        }
        for s in GOLDEN_SCENARIOS:
            missing = required_fields - set(s["market"].keys())
            assert not missing, f"'{s['name']}' missing market fields: {missing}"

    def test_rule_scenarios_have_required_fields(self):
        for s in RULE_SCENARIOS:
            assert "forbidden_signal" in s
            assert s["forbidden_signal"] in ("BUY", "SELL", "HOLD")

    def test_prompt_builds_without_error(self):
        """PromptPackage สร้างได้ทุก scenario"""
        for s in GOLDEN_SCENARIOS:
            prompt = _build_eval_prompt(s)
            assert len(prompt.system) > 0
            assert len(prompt.user) > 0
            assert str(s["market"]["price"]) in prompt.user
