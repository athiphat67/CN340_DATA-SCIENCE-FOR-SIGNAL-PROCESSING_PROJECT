"""
test_discord_notifier.py — Tests สำหรับ Discord Notification System

ทดสอบทั้ง pure helper functions และ integration flow:
  Part A — Unit: Pure helper functions
    1. _confidence_bar()  — render confidence progress bar
    2. _fmt_price()       — format ราคาทอง THB
    3. _fmt_usd()         — format ราคา USD
    4. Signal constants   — emoji, color mappings
  Part B — Integration: Components ทำงานร่วมกัน
    5. Full Pipeline      — config → build_embed → notify → httpx.post
    6. Guard Chain        — enabled → webhook → hold_filter → min_conf → send
    7. Multi-Interval     — หลาย intervals → voting breakdown + per-interval
    8. Error Recovery     — HTTP error / network error → last_error + retry
    9. Runtime Toggle     — update_hold_toggle / update_enabled → ส่งผลต่อ flow
   10. Status             — status() สะท้อนสถานะล่าสุด
   11. Edge Cases         — minimal market_state, long rationale

Strategy:
  - Pure function tests สำหรับ helpers (ไม่มี mock)
  - Mock httpx.post สำหรับ webhook (ไม่ส่ง Discord จริง)
  - ทดสอบ interaction จริงระหว่าง build_embed ↔ DiscordNotifier.notify
  - ทดสอบ config loading จาก os.environ → class → method → webhook call
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from notification.discord_notifier import (
    _confidence_bar,
    _fmt_price,
    _fmt_usd,
    build_embed,
    DiscordNotifier,
    _SIGNAL_EMOJI,
    _SIGNAL_COLOR,
    _CONFIDENCE_BAR_LENGTH,
    _CONFIDENCE_BAR_FILLED,
    _CONFIDENCE_BAR_EMPTY,
)

pytestmark = pytest.mark.integration

# ══════════════════════════════════════════════════════════════════
# Part A — Unit: Pure Helper Functions
# ══════════════════════════════════════════════════════════════════


# ── 1. _confidence_bar ────────────────────────────────────────────


class TestConfidenceBar:
    """ทดสอบ _confidence_bar() — text progress bar"""

    def test_full_confidence(self):
        """1.0 → bar เต็ม"""
        bar = _confidence_bar(1.0)
        assert _CONFIDENCE_BAR_FILLED * _CONFIDENCE_BAR_LENGTH in bar
        assert "100%" in bar

    def test_zero_confidence(self):
        """0.0 → bar ว่าง"""
        bar = _confidence_bar(0.0)
        assert _CONFIDENCE_BAR_EMPTY * _CONFIDENCE_BAR_LENGTH in bar
        assert "0%" in bar

    def test_half_confidence(self):
        """0.5 → bar ครึ่ง"""
        bar = _confidence_bar(0.5)
        assert "50%" in bar
        filled = bar.count(_CONFIDENCE_BAR_FILLED)
        assert filled == 5

    def test_high_confidence(self):
        """0.85 → 85%"""
        bar = _confidence_bar(0.85)
        assert "85%" in bar

    def test_returns_string(self):
        """ต้องคืน string"""
        assert isinstance(_confidence_bar(0.7), str)

    def test_has_backtick_wrapper(self):
        """bar ต้องอยู่ใน backtick (markdown code)"""
        bar = _confidence_bar(0.5)
        assert "`" in bar


# ── 2. _fmt_price ─────────────────────────────────────────────────


class TestFmtPrice:
    """ทดสอบ _fmt_price() — format THB price"""

    def test_normal_price(self):
        """ราคาปกติ → ฿45,000"""
        result = _fmt_price(45000)
        assert "฿" in result
        assert "45,000" in result

    def test_float_price(self):
        """float → format ถูก"""
        result = _fmt_price(45123.456)
        assert "฿" in result
        assert "45,123" in result

    def test_none_returns_fallback(self):
        """None → N/A"""
        assert _fmt_price(None) == "N/A"

    def test_custom_fallback(self):
        """None + custom fallback"""
        assert _fmt_price(None, fallback="-") == "-"

    def test_string_number(self):
        """string ที่เป็นตัวเลข → format ได้"""
        result = _fmt_price("45000")
        assert "฿" in result

    def test_invalid_string(self):
        """string ที่ไม่ใช่ตัวเลข → fallback"""
        result = _fmt_price("not_a_number")
        assert result == "N/A"

    def test_zero_price(self):
        """0 → ฿0"""
        result = _fmt_price(0)
        assert "฿" in result
        assert "0" in result


# ── 3. _fmt_usd ──────────────────────────────────────────────────


class TestFmtUsd:
    """ทดสอบ _fmt_usd() — format USD price"""

    def test_normal_price(self):
        """ราคาปกติ → $2,350.50"""
        result = _fmt_usd(2350.50)
        assert "$" in result
        assert "2,350.50" in result

    def test_none_returns_fallback(self):
        """None → N/A"""
        assert _fmt_usd(None) == "N/A"

    def test_custom_fallback(self):
        """None + custom fallback"""
        assert _fmt_usd(None, fallback="-") == "-"

    def test_string_number(self):
        """string ที่เป็นตัวเลข → format ได้"""
        result = _fmt_usd("2350.5")
        assert "$" in result

    def test_invalid_string(self):
        """string ที่ไม่ใช่ตัวเลข → fallback"""
        assert _fmt_usd("bad") == "N/A"

    def test_two_decimal_places(self):
        """ต้องมี 2 decimal places"""
        result = _fmt_usd(2350)
        assert "2,350.00" in result


# ── 4. Signal Config Constants ────────────────────────────────────


class TestSignalConfig:
    """ทดสอบ signal config constants"""

    def test_signal_emoji_buy(self):
        assert _SIGNAL_EMOJI["BUY"] == "🟢"

    def test_signal_emoji_sell(self):
        assert _SIGNAL_EMOJI["SELL"] == "🔴"

    def test_signal_emoji_hold(self):
        assert _SIGNAL_EMOJI["HOLD"] == "🟡"

    def test_signal_color_buy_is_int(self):
        assert isinstance(_SIGNAL_COLOR["BUY"], int)

    def test_signal_color_sell_is_int(self):
        assert isinstance(_SIGNAL_COLOR["SELL"], int)

    def test_signal_color_hold_is_int(self):
        assert isinstance(_SIGNAL_COLOR["HOLD"], int)

    def test_all_signals_have_emoji(self):
        for sig in ["BUY", "SELL", "HOLD"]:
            assert sig in _SIGNAL_EMOJI

    def test_all_signals_have_color(self):
        for sig in ["BUY", "SELL", "HOLD"]:
            assert sig in _SIGNAL_COLOR


# ══════════════════════════════════════════════════════════════════
# Part B — Integration: Components ทำงานร่วมกัน
# ══════════════════════════════════════════════════════════════════


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def env_full():
    """Environment variables ครบสำหรับ DiscordNotifier"""
    return {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/abc",
        "DISCORD_NOTIFY_ENABLED": "true",
        "DISCORD_NOTIFY_HOLD": "true",
        "DISCORD_NOTIFY_MIN_CONF": "0.0",
    }


@pytest.fixture
def voting_buy():
    return {
        "final_signal": "BUY",
        "weighted_confidence": 0.85,
        "voting_breakdown": {
            "BUY": {"count": 2, "weighted_score": 0.7},
            "HOLD": {"count": 1, "weighted_score": 0.15},
        },
    }


@pytest.fixture
def voting_sell():
    return {
        "final_signal": "SELL",
        "weighted_confidence": 0.75,
    }


@pytest.fixture
def voting_hold():
    return {
        "final_signal": "HOLD",
        "weighted_confidence": 0.5,
    }


@pytest.fixture
def interval_multi():
    """หลาย timeframes"""
    return {
        "1h": {
            "signal": "BUY",
            "confidence": 0.9,
            "entry_price": 45000,
            "stop_loss": 44500,
            "take_profit": 46000,
            "rationale": "RSI oversold + MACD bullish crossover",
        },
        "4h": {
            "signal": "BUY",
            "confidence": 0.7,
            "entry_price": 45100,
            "stop_loss": 44600,
            "take_profit": 46200,
            "rationale": "Uptrend confirmed by EMA",
        },
    }


@pytest.fixture
def interval_single():
    return {
        "1h": {
            "signal": "BUY",
            "confidence": 0.85,
            "entry_price": 45000,
            "stop_loss": 44500,
            "take_profit": 46000,
            "rationale": "Strong buy signal",
        },
    }


@pytest.fixture
def mock_httpx_ok():
    """Mock httpx.post ที่ return 204 (success)"""
    with patch("notification.discord_notifier.httpx.post") as mock_post:
        resp = MagicMock(status_code=204)
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp
        yield mock_post


# ── 5. Full Pipeline — config → build_embed → notify → webhook ───


class TestFullPipeline:
    """Integration: ทดสอบ flow ทั้งหมดตั้งแต่สร้าง notifier จนถึงส่ง webhook"""

    def test_buy_signal_full_flow(
        self, env_full, voting_buy, interval_multi, market_state, mock_httpx_ok
    ):
        """BUY signal → build_embed → httpx.post ถูกเรียก 1 ครั้ง"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_multi,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        assert result is True
        mock_httpx_ok.assert_called_once()

    def test_sell_signal_full_flow(
        self, env_full, voting_sell, interval_single, market_state, mock_httpx_ok
    ):
        """SELL signal → embed สร้างถูก + ส่งได้"""
        interval_single["1h"]["signal"] = "SELL"
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            result = notifier.notify(
                voting_result=voting_sell,
                interval_results=interval_single,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        assert result is True

    def test_payload_structure(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """Payload ที่ส่งไป Discord ต้องมี username + embeds"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        payload = mock_httpx_ok.call_args[1]["json"]
        assert "username" in payload
        assert "GoldTrader" in payload["username"]
        assert "embeds" in payload
        assert isinstance(payload["embeds"], list)
        assert len(payload["embeds"]) == 1

    def test_embed_contains_signal_and_confidence(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """Embed ที่ส่งไป Discord ต้องมี signal + confidence ครบ"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        assert "BUY" in embed["title"]
        assert _SIGNAL_EMOJI["BUY"] in embed["title"]
        assert embed["color"] == _SIGNAL_COLOR["BUY"]
        assert "85" in embed["description"]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Signal" in field_names
        assert "Confidence" in field_names
        assert "Entry" in field_names
        assert "Stop Loss" in field_names
        assert "Take Profit" in field_names

    def test_market_prices_in_embed(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """ราคาทองไทย + spot USD ต้องอยู่ใน embed"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        field_values = " ".join(f["value"] for f in embed["fields"])
        assert "45,200" in field_values  # sell_price_thb
        assert "45,000" in field_values  # entry / buy
        assert "2,350.50" in field_values  # spot USD

    def test_run_id_in_embed(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """run_id ต้องปรากฏใน Meta field"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="gemini",
                period="daily",
                run_id=42,
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        meta_fields = [f for f in embed["fields"] if "Meta" in f["name"]]
        assert len(meta_fields) >= 1
        assert "#42" in meta_fields[0]["value"]


# ── 6. Guard Chain — enabled → webhook → hold → min_conf → send ──


class TestGuardChain:
    """Integration: ทดสอบ guard ทั้ง chain ทำงานร่วมกัน"""

    def _notify(self, env, voting, interval, market_state):
        """Helper: สร้าง notifier + เรียก notify"""
        with patch.dict(os.environ, env, clear=False):
            notifier = DiscordNotifier()
        with patch("notification.discord_notifier.httpx.post") as mock_post:
            resp = MagicMock(status_code=204)
            resp.raise_for_status = MagicMock()
            mock_post.return_value = resp
            result = notifier.notify(
                voting_result=voting,
                interval_results=interval,
                market_state=market_state,
                provider="test",
                period="test",
            )
        return result, notifier

    def test_all_guards_pass(self, env_full, voting_buy, interval_single, market_state):
        """ทุก guard ผ่าน → True"""
        result, _ = self._notify(env_full, voting_buy, interval_single, market_state)
        assert result is True

    def test_disabled_blocks(self, env_full, voting_buy, interval_single, market_state):
        """enabled=false → blocked ที่ guard แรก"""
        env_full["DISCORD_NOTIFY_ENABLED"] = "false"
        result, _ = self._notify(env_full, voting_buy, interval_single, market_state)
        assert result is False

    def test_no_webhook_blocks(
        self, env_full, voting_buy, interval_single, market_state
    ):
        """webhook ว่าง → blocked + last_error"""
        env_full["DISCORD_WEBHOOK_URL"] = ""
        result, notifier = self._notify(
            env_full, voting_buy, interval_single, market_state
        )
        assert result is False
        assert "not set" in notifier.last_error

    def test_hold_filter_blocks(
        self, env_full, voting_hold, interval_single, market_state
    ):
        """HOLD + notify_hold=false → blocked"""
        env_full["DISCORD_NOTIFY_HOLD"] = "false"
        interval_single["1h"]["signal"] = "HOLD"
        result, _ = self._notify(env_full, voting_hold, interval_single, market_state)
        assert result is False

    def test_hold_filter_passes_when_enabled(
        self, env_full, voting_hold, interval_single, market_state
    ):
        """HOLD + notify_hold=true → passes"""
        env_full["DISCORD_NOTIFY_HOLD"] = "true"
        interval_single["1h"]["signal"] = "HOLD"
        result, _ = self._notify(env_full, voting_hold, interval_single, market_state)
        assert result is True

    def test_min_conf_blocks(self, env_full, voting_buy, interval_single, market_state):
        """confidence < min_conf → blocked"""
        env_full["DISCORD_NOTIFY_MIN_CONF"] = "0.9"
        voting_buy["weighted_confidence"] = 0.5
        result, _ = self._notify(env_full, voting_buy, interval_single, market_state)
        assert result is False

    def test_min_conf_passes(self, env_full, voting_buy, interval_single, market_state):
        """confidence >= min_conf → passes"""
        env_full["DISCORD_NOTIFY_MIN_CONF"] = "0.7"
        voting_buy["weighted_confidence"] = 0.85
        result, _ = self._notify(env_full, voting_buy, interval_single, market_state)
        assert result is True


# ── 7. Multi-Interval Flow ────────────────────────────────────────


class TestMultiIntervalFlow:
    """Integration: หลาย intervals → voting breakdown + per-interval"""

    def test_multi_interval_has_breakdown(
        self, env_full, voting_buy, interval_multi, market_state, mock_httpx_ok
    ):
        """หลาย intervals → Per-Interval Breakdown field"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_multi,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        names = [f["name"] for f in embed["fields"]]
        assert any("Breakdown" in n for n in names)

    def test_single_interval_no_breakdown(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """interval เดียว → ไม่มี breakdown"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        names = [f["name"] for f in embed["fields"]]
        assert not any("Breakdown" in n for n in names)

    def test_voting_summary_in_embed(
        self, env_full, voting_buy, interval_multi, market_state, mock_httpx_ok
    ):
        """voting_breakdown → Voting Summary field ใน embed"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_multi,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        names = [f["name"] for f in embed["fields"]]
        assert any("Voting" in n for n in names)

    def test_best_interval_used_for_prices(
        self, env_full, voting_buy, interval_multi, market_state, mock_httpx_ok
    ):
        """ราคา Entry/SL/TP ใช้จาก interval ที่ confidence สูงสุด"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_multi,
                market_state=market_state,
                provider="gemini",
                period="daily",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        entry_field = next(f for f in embed["fields"] if f["name"] == "Entry")
        # best interval = 1h (conf=0.9) → entry=45000
        assert "45,000" in entry_field["value"]


# ── 8. Error Recovery ─────────────────────────────────────────────


class TestErrorRecovery:
    """Integration: error → last_error set → retry → last_error cleared"""

    def test_http_error_sets_last_error(
        self, env_full, voting_buy, interval_single, market_state
    ):
        """HTTP 429 → last_error มีข้อมูล status code"""
        import httpx

        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
        with patch("notification.discord_notifier.httpx.post") as mock_post:
            mock_resp = MagicMock(status_code=429, text="Rate limited")
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429", request=MagicMock(), response=mock_resp
            )
            mock_post.return_value = mock_resp
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert result is False
        assert "429" in notifier.last_error

    def test_network_error_sets_last_error(
        self, env_full, voting_buy, interval_single, market_state
    ):
        """Connection refused → last_error set"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
        with patch("notification.discord_notifier.httpx.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert result is False
        assert "Connection refused" in notifier.last_error

    def test_success_after_error_clears_last_error(
        self, env_full, voting_buy, interval_single, market_state
    ):
        """error → success → last_error = None"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()

        # ครั้งที่ 1: fail
        with patch("notification.discord_notifier.httpx.post") as mock_post:
            mock_post.side_effect = Exception("timeout")
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert notifier.last_error is not None

        # ครั้งที่ 2: success → clear error
        with patch("notification.discord_notifier.httpx.post") as mock_post:
            resp = MagicMock(status_code=204)
            resp.raise_for_status = MagicMock()
            mock_post.return_value = resp
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert result is True
        assert notifier.last_error is None


# ── 9. Runtime Toggle → Flow ─────────────────────────────────────


class TestRuntimeToggleFlow:
    """Integration: runtime toggle → เปลี่ยน behavior ของ notify"""

    def test_disable_then_notify_fails(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """update_enabled(False) → notify returns False"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.update_enabled(False)
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert result is False
        mock_httpx_ok.assert_not_called()

    def test_reenable_then_notify_succeeds(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """disable → re-enable → notify returns True"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.update_enabled(False)
            notifier.update_enabled(True)
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert result is True

    def test_toggle_hold_off_blocks_hold(
        self, env_full, voting_hold, interval_single, market_state, mock_httpx_ok
    ):
        """update_hold_toggle(False) → HOLD ถูก block"""
        interval_single["1h"]["signal"] = "HOLD"
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.update_hold_toggle(False)
            result = notifier.notify(
                voting_result=voting_hold,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert result is False

    def test_toggle_hold_off_allows_buy(
        self, env_full, voting_buy, interval_single, market_state, mock_httpx_ok
    ):
        """update_hold_toggle(False) → BUY ยังส่งได้"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.update_hold_toggle(False)
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        assert result is True

    def test_toggle_updates_env(self, env_full):
        """toggle → os.environ อัพเดทด้วย"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.update_hold_toggle(False)
            assert os.environ.get("DISCORD_NOTIFY_HOLD") == "false"
            notifier.update_enabled(False)
            assert os.environ.get("DISCORD_NOTIFY_ENABLED") == "false"


# ── 10. Status → reflects runtime state ──────────────────────────


class TestStatusReflectsState:
    """Integration: status() สะท้อนสถานะล่าสุดจริง"""

    def test_initial_status(self, env_full):
        """สร้างใหม่ → status ตรงกับ env"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
        s = notifier.status()
        assert s["enabled"] is True
        assert s["notify_hold"] is True
        assert s["min_conf"] == 0.0
        assert s["webhook_set"] is True
        assert s["last_error"] is None

    def test_status_after_toggle(self, env_full):
        """toggle → status เปลี่ยนตาม"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.update_enabled(False)
            notifier.update_hold_toggle(False)
        s = notifier.status()
        assert s["enabled"] is False
        assert s["notify_hold"] is False

    def test_status_after_error(
        self, env_full, voting_buy, interval_single, market_state
    ):
        """error → status['last_error'] มีค่า"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
        with patch("notification.discord_notifier.httpx.post") as mock_post:
            mock_post.side_effect = Exception("boom")
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state,
                provider="test",
                period="test",
            )
        s = notifier.status()
        assert s["last_error"] is not None
        assert "boom" in s["last_error"]

    def test_status_no_webhook(self, env_full):
        """ไม่มี webhook → webhook_set = False"""
        env_full["DISCORD_WEBHOOK_URL"] = ""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
        assert notifier.status()["webhook_set"] is False


# ── 11. Edge Cases — minimal market_state, long rationale ────────


class TestEdgeCases:
    """Integration: edge cases ที่อาจเกิดในการใช้งานจริง"""

    def test_minimal_market_state(
        self, env_full, voting_buy, interval_single, market_state_minimal, mock_httpx_ok
    ):
        """market_state ไม่มี optional fields → ยังส่งได้"""
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            result = notifier.notify(
                voting_result=voting_buy,
                interval_results=interval_single,
                market_state=market_state_minimal,
                provider="test",
                period="test",
            )
        assert result is True

    def test_long_rationale_truncated(
        self, env_full, voting_buy, market_state, mock_httpx_ok
    ):
        """rationale > 900 chars → ถูก truncate ใน embed"""
        interval = {
            "1h": {
                "signal": "BUY",
                "confidence": 0.9,
                "rationale": "x" * 1500,
            },
        }
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval,
                market_state=market_state,
                provider="test",
                period="test",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        rationale_fields = [f for f in embed["fields"] if "Rationale" in f["name"]]
        assert len(rationale_fields) == 1
        assert len(rationale_fields[0]["value"]) <= 901

    def test_missing_entry_stop_tp(
        self, env_full, voting_buy, market_state, mock_httpx_ok
    ):
        """ไม่มี entry/stop/tp → ใช้ fallback N/A"""
        interval = {
            "1h": {
                "signal": "BUY",
                "confidence": 0.85,
            },
        }
        with patch.dict(os.environ, env_full, clear=False):
            notifier = DiscordNotifier()
            notifier.notify(
                voting_result=voting_buy,
                interval_results=interval,
                market_state=market_state,
                provider="test",
                period="test",
            )

        embed = mock_httpx_ok.call_args[1]["json"]["embeds"][0]
        entry_field = next(f for f in embed["fields"] if f["name"] == "Entry")
        assert entry_field["value"] == "N/A"
