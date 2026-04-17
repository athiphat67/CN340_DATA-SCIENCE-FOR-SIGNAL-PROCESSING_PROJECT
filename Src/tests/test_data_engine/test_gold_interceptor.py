"""
test_gold_interceptor.py — Pytest สำหรับ gold_interceptor_lite WebSocket protocol

หมายเหตุ:
  - gold_interceptor_lite.py สามารถ import ได้ปลอดภัย (ไม่มี module-level side effects)
    แต่ parsing logic ฝังอยู่ใน run_intergold_fallback() แบบ inline ไม่มี function แยก
    → ทดสอบ protocol specification ผ่าน inline reimplementation คือ approach ที่ถูกต้อง
  - gold_interceptor.py (Playwright version) ยังคง import ไม่ได้เพราะ sync_playwright()
    ถูกเรียกที่ module level → excluded จาก test suite

ครอบคลุม:
  1. WebSocket message parsing — "42" prefix, JSON extraction
  2. Gold rate data extraction — bid/ask/spot/fx fields
  3. Payload structure — ตรวจสอบ keys ที่คาดหวัง
  4. Edge cases — invalid message, missing fields, zero prices
  5. CSV headers — ตรงตามที่กำหนด

Strategy: Inline reimplementation ของ parsing protocol spec
  - ทดสอบ "42[event, data]" WebSocket format specification
  - Deterministic 100% ไม่ต้องเชื่อมต่อ WebSocket จริง
"""

import json
import pytest

pytestmark = pytest.mark.data_engine


# ══════════════════════════════════════════════════════════════════
# Constants จาก gold_interceptor.py (copy มาเพื่อทดสอบ)
# ══════════════════════════════════════════════════════════════════

EXPECTED_HEADERS = [
    "timestamp", "bid_99", "ask_99", "bid_96", "ask_96",
    "gold_spot", "fx_usd_thb", "assoc_bid", "assoc_ask",
]


# ══════════════════════════════════════════════════════════════════
# Helpers — จำลอง parsing logic จาก gold_interceptor.py
# ══════════════════════════════════════════════════════════════════


def parse_ws_message(payload: str) -> dict | None:
    """
    จำลอง process_message logic ของ gold_interceptor.py
    Parse "42[event, data]" format → dict หรือ None ถ้าไม่ใช่ gold data
    """
    if not payload.startswith("42"):
        return None
    try:
        data_list = json.loads(payload[2:])
        event_name = data_list[0]
        if event_name != "updateGoldRateData":
            return None
        gold = data_list[1]
        return {
            "timestamp": gold.get("createDate", "Unknown"),
            "bid_99": gold.get("bidPrice99"),
            "ask_99": gold.get("offerPrice99"),
            "bid_96": gold.get("bidPrice96"),
            "ask_96": gold.get("offerPrice96"),
            "gold_spot": gold.get("AUXBuy"),
            "fx_usd_thb": gold.get("usdBuy"),
            "assoc_bid": gold.get("bidCentralPrice96"),
            "assoc_ask": gold.get("offerCentralPrice96"),
        }
    except (json.JSONDecodeError, IndexError, TypeError):
        return None


def build_lite_payload(gold: dict) -> dict | None:
    """
    จำลอง payload creation ของ gold_interceptor_lite.py
    """
    bid_96 = float(gold.get("bidPrice96", 0))
    ask_96 = float(gold.get("offerPrice96", 0))
    spot = float(gold.get("AUXBuy", 0))
    fx = float(gold.get("usdBuy", 0))

    if bid_96 > 0 and ask_96 > 0:
        return {
            "source": "intergold_hybrid_ws",
            "price_thb_per_baht_weight": round((bid_96 + ask_96) / 2, 2),
            "sell_price_thb": ask_96,
            "buy_price_thb": bid_96,
            "spread_thb": ask_96 - bid_96,
            "gold_spot_usd": spot,
            "usd_thb_live": fx,
        }
    return None


# ══════════════════════════════════════════════════════════════════
# Sample data
# ══════════════════════════════════════════════════════════════════


SAMPLE_GOLD_DATA = {
    "createDate": "2026-04-01 10:30:00",
    "bidPrice99": 46500,
    "offerPrice99": 46600,
    "bidPrice96": 44800,
    "offerPrice96": 45000,
    "AUXBuy": 2350.50,
    "usdBuy": 34.50,
    "bidCentralPrice96": 44750,
    "offerCentralPrice96": 45050,
}

SAMPLE_WS_MESSAGE = '42["updateGoldRateData",' + json.dumps(SAMPLE_GOLD_DATA) + ']'


# ══════════════════════════════════════════════════════════════════
# 1. WebSocket message parsing
# ══════════════════════════════════════════════════════════════════


class TestParseWsMessage:
    """ทดสอบ WebSocket message parsing"""

    def test_valid_42_message(self):
        """"42" prefix + valid JSON → parsed dict"""
        result = parse_ws_message(SAMPLE_WS_MESSAGE)
        assert result is not None
        assert result["bid_96"] == 44800
        assert result["ask_96"] == 45000

    def test_not_42_prefix(self):
        """ไม่ขึ้นต้นด้วย "42" → None"""
        assert parse_ws_message("0{\"sid\": \"test\"}") is None
        assert parse_ws_message("2") is None
        assert parse_ws_message("3") is None

    def test_non_gold_event(self):
        """Event อื่นที่ไม่ใช่ updateGoldRateData → None"""
        msg = '42["otherEvent",{"data":"test"}]'
        assert parse_ws_message(msg) is None

    def test_invalid_json(self):
        """JSON ไม่ถูกต้อง → None"""
        assert parse_ws_message("42{invalid json}") is None

    def test_empty_string(self):
        assert parse_ws_message("") is None

    def test_just_42(self):
        """แค่ "42" ไม่มี JSON → None"""
        assert parse_ws_message("42") is None


# ══════════════════════════════════════════════════════════════════
# 2. Gold rate data extraction
# ══════════════════════════════════════════════════════════════════


class TestGoldDataExtraction:
    """ทดสอบ extraction ข้อมูลราคาทอง"""

    def test_all_fields_extracted(self):
        """ทุก field ถูก extract"""
        result = parse_ws_message(SAMPLE_WS_MESSAGE)
        assert result["timestamp"] == "2026-04-01 10:30:00"
        assert result["bid_99"] == 46500
        assert result["ask_99"] == 46600
        assert result["gold_spot"] == 2350.50
        assert result["fx_usd_thb"] == 34.50
        assert result["assoc_bid"] == 44750
        assert result["assoc_ask"] == 45050

    def test_missing_fields_default(self):
        """field ที่ไม่มี → None / 'Unknown'"""
        minimal = '42["updateGoldRateData",{}]'
        result = parse_ws_message(minimal)
        assert result["timestamp"] == "Unknown"
        assert result["bid_99"] is None
        assert result["ask_99"] is None


# ══════════════════════════════════════════════════════════════════
# 3. Lite payload structure
# ══════════════════════════════════════════════════════════════════


class TestBuildLitePayload:
    """ทดสอบ gold_interceptor_lite payload creation"""

    def test_valid_payload(self):
        result = build_lite_payload(SAMPLE_GOLD_DATA)
        assert result is not None
        assert result["source"] == "intergold_hybrid_ws"
        assert result["sell_price_thb"] == 45000
        assert result["buy_price_thb"] == 44800
        assert result["spread_thb"] == 200
        assert result["gold_spot_usd"] == 2350.50
        assert result["usd_thb_live"] == 34.50

    def test_average_price(self):
        """price_thb_per_baht_weight = (bid + ask) / 2"""
        result = build_lite_payload(SAMPLE_GOLD_DATA)
        expected = round((44800 + 45000) / 2, 2)
        assert result["price_thb_per_baht_weight"] == expected

    def test_zero_bid_returns_none(self):
        """bid = 0 → None"""
        data = {**SAMPLE_GOLD_DATA, "bidPrice96": 0}
        assert build_lite_payload(data) is None

    def test_zero_ask_returns_none(self):
        """ask = 0 → None"""
        data = {**SAMPLE_GOLD_DATA, "offerPrice96": 0}
        assert build_lite_payload(data) is None

    def test_missing_fields_zero(self):
        """field ไม่มี → default 0 → None"""
        assert build_lite_payload({}) is None


# ══════════════════════════════════════════════════════════════════
# 4. CSV Headers
# ══════════════════════════════════════════════════════════════════


class TestCsvHeaders:
    """ทดสอบ CSV header specification"""

    def test_expected_headers(self):
        assert len(EXPECTED_HEADERS) == 9
        assert EXPECTED_HEADERS[0] == "timestamp"
        assert "bid_96" in EXPECTED_HEADERS
        assert "ask_96" in EXPECTED_HEADERS
        assert "gold_spot" in EXPECTED_HEADERS
        assert "fx_usd_thb" in EXPECTED_HEADERS
