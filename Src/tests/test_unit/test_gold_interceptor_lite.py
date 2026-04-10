"""
test_gold_interceptor_lite.py — Tests สำหรับ gold_interceptor_lite

ครอบคลุม:
  1. Payload building     — updateGoldRateData → payload ถูกต้อง
  2. Invalid prices       — bid/ask ≤ 0 → ไม่เขียน file
  3. Malformed JSON       — json.JSONDecodeError → ข้ามไปเงียบๆ (pass)
  4. Cookie fetch failure — requests.Session.get() fail → Exception caught, print error
  5. WebSocket connect fail — websocket.connect() fail → Exception caught
  6. Message routing      — msg "0" → send "40", msg "2" → send "3", msg "42..." → parse
  7. File writing         — payload บันทึกเป็น JSON ไฟล์ถูกต้อง

Strategy: mock curl_cffi, websocket, json.dump — ไม่ใช้ network จริง
"""

import json
import sys
import pytest
from unittest.mock import patch, MagicMock, mock_open, call

# ── pre-mock dependencies ────────────────────────────────────────
# curl_cffi อาจไม่ได้ install ใน test env
if "curl_cffi" not in sys.modules:
    sys.modules["curl_cffi"] = MagicMock()
    sys.modules["curl_cffi.requests"] = MagicMock()

if "websocket" not in sys.modules:
    sys.modules["websocket"] = MagicMock()


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _gold_event(bid=72000.0, ask=72200.0, spot=2350.0, fx=34.5) -> str:
    """สร้าง WebSocket message สำหรับ updateGoldRateData event"""
    data = {
        "bidPrice96": bid,
        "offerPrice96": ask,
        "AUXBuy": spot,
        "usdBuy": fx,
    }
    return "42" + json.dumps(["updateGoldRateData", data])


def _run_interceptor_with_messages(messages: list[str]) -> list[dict]:
    """
    รัน start_interceptor() โดย mock WebSocket ให้รับ messages ตามลำดับ
    แล้วตัดลูปหลังรับครบ (ใช้ StopIteration)

    Returns:
        list ของ payloads ที่ถูกเขียนลง JSON file
    """
    # หลังรับ messages ครบ → raise StopIteration เพื่อออกจาก while True
    messages_with_stop = messages + [None]  # None → break จาก loop

    mock_ws = MagicMock()
    mock_ws.recv.side_effect = messages_with_stop
    mock_ws.send = MagicMock()

    mock_session = MagicMock()
    mock_session.get.return_value = MagicMock(status_code=200)
    mock_session.cookies.get_dict.return_value = {"cf_clearance": "test123"}

    written_payloads = []

    def fake_open(path, mode, **kwargs):
        """capture json.dump calls"""
        m = mock_open()()
        return m

    with (
        patch("data_engine.gold_interceptor_lite.requests") as mock_req,
        patch("data_engine.gold_interceptor_lite.websocket") as mock_websocket_mod,
        patch("data_engine.gold_interceptor_lite.time.sleep"),
        patch("builtins.open", mock_open()),
        patch("json.dump") as mock_json_dump,
    ):
        mock_req.Session.return_value = mock_session
        mock_websocket_mod.WebSocket.return_value = mock_ws

        from data_engine.gold_interceptor_lite import start_interceptor

        start_interceptor()

        # เก็บ payload ที่ถูกเขียน
        for c in mock_json_dump.call_args_list:
            written_payloads.append(c.args[0])

    return written_payloads, mock_ws


# ══════════════════════════════════════════════════════════════════
# 1. Payload building
# ══════════════════════════════════════════════════════════════════


class TestPayloadBuilding:
    """updateGoldRateData → payload fields ถูกต้อง"""

    def test_payload_has_required_fields(self):
        """payload ต้องมี key มาตรฐาน"""
        payloads, _ = _run_interceptor_with_messages([_gold_event()])
        assert len(payloads) == 1
        p = payloads[0]
        assert "buy_price_thb" in p
        assert "sell_price_thb" in p
        assert "spread_thb" in p
        assert "source" in p
        assert "timestamp" in p

    def test_payload_buy_price_equals_bid(self):
        """buy_price_thb ต้องเท่ากับ bidPrice96"""
        payloads, _ = _run_interceptor_with_messages([_gold_event(bid=71500.0)])
        assert payloads[0]["buy_price_thb"] == 71500.0

    def test_payload_sell_price_equals_ask(self):
        """sell_price_thb ต้องเท่ากับ offerPrice96"""
        payloads, _ = _run_interceptor_with_messages([_gold_event(ask=71800.0)])
        assert payloads[0]["sell_price_thb"] == 71800.0

    def test_payload_spread_is_ask_minus_bid(self):
        """spread_thb = ask - bid"""
        payloads, _ = _run_interceptor_with_messages([_gold_event(bid=71500.0, ask=71800.0)])
        assert payloads[0]["spread_thb"] == pytest.approx(300.0)

    def test_payload_source_is_correct(self):
        """source ต้องเป็น 'intergold_hybrid_ws'"""
        payloads, _ = _run_interceptor_with_messages([_gold_event()])
        assert payloads[0]["source"] == "intergold_hybrid_ws"

    def test_payload_mid_price_is_average(self):
        """price_thb_per_baht_weight = round((bid + ask) / 2, 2)"""
        payloads, _ = _run_interceptor_with_messages([_gold_event(bid=71500.0, ask=71800.0)])
        expected = round((71500.0 + 71800.0) / 2, 2)
        assert payloads[0]["price_thb_per_baht_weight"] == expected


# ══════════════════════════════════════════════════════════════════
# 2. Invalid prices (bid/ask ≤ 0)
# ══════════════════════════════════════════════════════════════════


class TestInvalidPrices:
    """bid หรือ ask ≤ 0 → ไม่เขียน payload"""

    def test_zero_bid_skips_payload(self):
        """bid=0 → ไม่เขียน JSON file"""
        payloads, _ = _run_interceptor_with_messages([_gold_event(bid=0.0)])
        assert len(payloads) == 0

    def test_zero_ask_skips_payload(self):
        """ask=0 → ไม่เขียน JSON file"""
        payloads, _ = _run_interceptor_with_messages([_gold_event(ask=0.0)])
        assert len(payloads) == 0

    def test_negative_bid_skips_payload(self):
        """bid<0 → ไม่เขียน JSON file"""
        payloads, _ = _run_interceptor_with_messages([_gold_event(bid=-100.0)])
        assert len(payloads) == 0

    def test_valid_after_invalid_writes_payload(self):
        """invalid ก่อน → valid ทีหลัง → เขียน 1 payload"""
        messages = [
            _gold_event(bid=0.0),   # skip
            _gold_event(bid=71500.0, ask=71800.0),  # write
        ]
        payloads, _ = _run_interceptor_with_messages(messages)
        assert len(payloads) == 1


# ══════════════════════════════════════════════════════════════════
# 3. Malformed JSON
# ══════════════════════════════════════════════════════════════════


class TestMalformedJSON:
    """JSON เสียหาย → pass เงียบๆ ไม่ crash"""

    def test_malformed_42_message_does_not_crash(self):
        """42{broken json} → json.JSONDecodeError → pass"""
        payloads, _ = _run_interceptor_with_messages(["42{not valid json!!!}"])
        assert len(payloads) == 0  # ไม่เขียนอะไร ไม่ crash

    def test_valid_after_malformed_still_works(self):
        """malformed ก่อน → valid ทีหลัง → ยังทำงานได้"""
        messages = [
            "42{broken!}",
            _gold_event(bid=71500.0, ask=71800.0),
        ]
        payloads, _ = _run_interceptor_with_messages(messages)
        assert len(payloads) == 1


# ══════════════════════════════════════════════════════════════════
# 4. Message routing
# ══════════════════════════════════════════════════════════════════


class TestMessageRouting:
    """ทดสอบ routing ของ message ประเภทต่างๆ"""

    def test_welcome_message_0_sends_40(self):
        """msg startswith "0" → ส่ง "40" กลับไป"""
        _, mock_ws = _run_interceptor_with_messages(["0{handshake}"])
        mock_ws.send.assert_any_call("40")

    def test_ping_2_sends_pong_3(self):
        """msg == "2" → ส่ง "3" (pong) กลับ"""
        _, mock_ws = _run_interceptor_with_messages(["2"])
        mock_ws.send.assert_any_call("3")

    def test_non_42_message_does_nothing(self):
        """msg ที่ไม่ match pattern → ไม่ crash"""
        payloads, _ = _run_interceptor_with_messages(["3", "some_unknown_message"])
        assert len(payloads) == 0

    def test_multiple_gold_events_all_written(self):
        """หลาย updateGoldRateData → เขียนทุกตัว"""
        messages = [
            _gold_event(bid=71500.0, ask=71800.0),
            _gold_event(bid=71600.0, ask=71900.0),
            _gold_event(bid=71700.0, ask=72000.0),
        ]
        payloads, _ = _run_interceptor_with_messages(messages)
        assert len(payloads) == 3


# ══════════════════════════════════════════════════════════════════
# 5. Connection failures
# ══════════════════════════════════════════════════════════════════


class TestConnectionFailures:
    """Cookie/WebSocket failure → exception caught, print error message"""

    def test_cookie_fetch_failure_does_not_crash(self):
        """requests.Session.get() raise → start_interceptor() ไม่ crash"""
        with (
            patch("data_engine.gold_interceptor_lite.requests") as mock_req,
            patch("data_engine.gold_interceptor_lite.time.sleep"),
        ):
            mock_session = MagicMock()
            mock_session.get.side_effect = Exception("Connection refused")
            mock_req.Session.return_value = mock_session

            from data_engine.gold_interceptor_lite import start_interceptor

            # ต้องไม่ raise — Exception ถูก catch ใน outer try/except
            start_interceptor()  # ไม่ raise

    def test_websocket_connect_failure_does_not_crash(self):
        """websocket.WebSocket().connect() raise → ไม่ crash"""
        with (
            patch("data_engine.gold_interceptor_lite.requests") as mock_req,
            patch("data_engine.gold_interceptor_lite.websocket") as mock_ws_mod,
            patch("data_engine.gold_interceptor_lite.time.sleep"),
        ):
            mock_session = MagicMock()
            mock_session.get.return_value = MagicMock(status_code=200)
            mock_session.cookies.get_dict.return_value = {}
            mock_req.Session.return_value = mock_session

            mock_ws = MagicMock()
            mock_ws.connect.side_effect = Exception("WebSocket refused")
            mock_ws_mod.WebSocket.return_value = mock_ws

            from data_engine.gold_interceptor_lite import start_interceptor

            start_interceptor()  # ไม่ raise

    def test_server_disconnect_breaks_loop(self):
        """recv() คืน empty string → break ออกจาก loop"""
        payloads, mock_ws = _run_interceptor_with_messages([""])
        # empty string → break → ไม่ crash
        assert len(payloads) == 0
