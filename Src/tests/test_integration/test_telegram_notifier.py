"""
test_telegram_notifier.py — Tests สำหรับ TelegramNotifier

ครอบคลุม:
  Part A — Unit: Pure helper functions
    1. _confidence_bar()  — render bar, clamp 0..1, HTML <code> wrapper
    2. _fmt_price()       — format THB, None/invalid fallback, float/string/zero
    3. _fmt_usd()         — format USD 2 decimal, None/invalid fallback
    4. Signal constants   — emoji mapping ครบ BUY/SELL/HOLD

  Part B — Integration: Components ทำงานร่วมกัน
    5. Constructor        — env vars → instance attrs, api_url, defaults
    6. Guard Chain        — disabled → missing token/chat_id → HOLD filter → min_conf
    7. Full Pipeline      — BUY/SELL/HOLD → build message → httpx.post → return True
    8. Message Building   — signal, emoji, provider, period, confidence bar,
                            target levels, market data, breakdown, voting,
                            rationale truncation, HTML escape, run_id, chat_id
    9. Error Recovery     — HTTP 4xx/5xx → last_error, network error, retry clears
   10. Runtime Toggle     — update_enabled, update_hold_toggle → flow + env sync
   11. Status             — status() สะท้อนสถานะปัจจุบัน
   12. Edge Cases         — empty market, empty interval, no voting, kwargs passthrough

Strategy: mock httpx.post — ไม่ใช้ Telegram API จริง
"""

import os
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.integration

from notification.telegram_notifier import (
    TelegramNotifier,
    _confidence_bar,
    _fmt_price,
    _fmt_usd,
    _SIGNAL_EMOJI,
    _CONFIDENCE_BAR_FILLED,
    _CONFIDENCE_BAR_EMPTY,
    _CONFIDENCE_BAR_LENGTH,
)


# ══════════════════════════════════════════════════════════════════
# Test Helpers & Fixtures
# ══════════════════════════════════════════════════════════════════


def _voting(signal="BUY", confidence=0.85, breakdown=True):
    """สร้าง voting_result dict"""
    vr = {
        "final_signal": signal,
        "weighted_confidence": confidence,
    }
    if breakdown:
        vr["voting_breakdown"] = {
            "BUY": {"count": 3, "weighted_score": 0.75},
            "HOLD": {"count": 1, "weighted_score": 0.10},
            "SELL": {"count": 0, "weighted_score": 0.00},
        }
    return vr


def _market(quality="good", spot_conf=0.98):
    """สร้าง market_state dict"""
    return {
        "market_data": {
            "thai_gold_thb": {"sell_price_thb": 45200, "buy_price_thb": 45000},
            "forex": {"usd_thb": 34.5},
            "spot_price_usd": {"price_usd_per_oz": 2350.0, "confidence": spot_conf},
        },
        "data_quality": {"quality_score": quality},
    }


def _intervals_multi():
    """หลาย timeframes — ใช้ทดสอบ breakdown + best interval"""
    return {
        "1h": {
            "signal": "BUY",
            "confidence": 0.88,
            "entry_price": 45200,
            "stop_loss": 44900,
            "take_profit": 45700,
            "rationale": "RSI oversold",
        },
        "4h": {
            "signal": "BUY",
            "confidence": 0.82,
            "entry_price": 45100,
            "stop_loss": 44800,
            "take_profit": 45800,
            "rationale": "EMA uptrend",
        },
        "15m": {
            "signal": "HOLD",
            "confidence": 0.55,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "rationale": "",
        },
    }


def _intervals_single():
    """Interval เดียว — ไม่ควรมี breakdown"""
    return {
        "1h": {
            "signal": "BUY",
            "confidence": 0.85,
            "entry_price": 45000,
            "stop_loss": 44500,
            "take_profit": 46000,
            "rationale": "Strong buy",
        },
    }


def _make_notifier(
    enabled="true",
    token="fake-token",
    chat_id="123456",
    notify_hold="true",
    min_conf="0.0",
):
    """สร้าง TelegramNotifier ด้วย mock env"""
    env = {
        "TELEGRAM_NOTIFY_ENABLED": enabled,
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHAT_ID": chat_id,
        "TELEGRAM_NOTIFY_HOLD": notify_hold,
        "TELEGRAM_NOTIFY_MIN_CONF": min_conf,
    }
    with patch.dict(os.environ, env, clear=False):
        return TelegramNotifier()


def _mock_httpx_success():
    """Mock httpx response ที่ raise_for_status ไม่ throw"""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    return resp


def _capture_post(notifier, **notify_kwargs):
    """เรียก notify + capture payload ที่ส่งไป httpx.post"""
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        return _mock_httpx_success()

    with patch("httpx.post", side_effect=fake_post):
        result = notifier.notify(**notify_kwargs)
    return result, captured


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
        assert filled == _CONFIDENCE_BAR_LENGTH // 2

    def test_high_confidence(self):
        """0.85 → 85%"""
        bar = _confidence_bar(0.85)
        assert "85%" in bar

    def test_clamps_above_1(self):
        """confidence > 1.0 → filled = 10 (ไม่เกิน bar length)"""
        bar = _confidence_bar(1.5)
        assert bar.count(_CONFIDENCE_BAR_FILLED) == _CONFIDENCE_BAR_LENGTH

    def test_clamps_below_0(self):
        """confidence < 0.0 → filled = 0"""
        bar = _confidence_bar(-0.5)
        assert bar.count(_CONFIDENCE_BAR_FILLED) == 0

    def test_returns_string(self):
        assert isinstance(_confidence_bar(0.7), str)

    def test_has_html_code_tag(self):
        """bar อยู่ใน <code> tag (Telegram HTML mode)"""
        bar = _confidence_bar(0.5)
        assert "<code>" in bar and "</code>" in bar


# ── 2. _fmt_price ─────────────────────────────────────────────────


class TestFmtPrice:
    """ทดสอบ _fmt_price() — format THB price"""

    def test_normal_price(self):
        assert _fmt_price(45000) == "฿45,000"

    def test_float_price(self):
        result = _fmt_price(45123.456)
        assert "฿" in result
        assert "45,123" in result

    def test_none_returns_default_fallback(self):
        assert _fmt_price(None) == "N/A"

    def test_none_returns_custom_fallback(self):
        assert _fmt_price(None, fallback="—") == "—"

    def test_string_number(self):
        result = _fmt_price("45000")
        assert "฿" in result and "45,000" in result

    def test_invalid_string(self):
        assert _fmt_price("abc") == "N/A"

    def test_zero_price(self):
        result = _fmt_price(0)
        assert "฿" in result and "0" in result


# ── 3. _fmt_usd ──────────────────────────────────────────────────


class TestFmtUsd:
    """ทดสอบ _fmt_usd() — format USD price"""

    def test_normal_price(self):
        assert "$2,350.50" in _fmt_usd(2350.5)

    def test_none_returns_fallback(self):
        assert _fmt_usd(None) == "N/A"

    def test_custom_fallback(self):
        assert _fmt_usd(None, fallback="—") == "—"

    def test_string_number(self):
        assert "$" in _fmt_usd("2350.5")

    def test_invalid_string(self):
        assert _fmt_usd("bad") == "N/A"

    def test_two_decimal_places(self):
        assert "2,350.00" in _fmt_usd(2350)

    def test_zero(self):
        result = _fmt_usd(0)
        assert "$0.00" in result


# ── 4. Signal constants ──────────────────────────────────────────


class TestSignalConstants:
    """ทดสอบ _SIGNAL_EMOJI mapping"""

    def test_buy_emoji(self):
        assert _SIGNAL_EMOJI["BUY"] == "🟢"

    def test_sell_emoji(self):
        assert _SIGNAL_EMOJI["SELL"] == "🔴"

    def test_hold_emoji(self):
        assert _SIGNAL_EMOJI["HOLD"] == "🟡"

    def test_all_signals_mapped(self):
        for sig in ("BUY", "SELL", "HOLD"):
            assert sig in _SIGNAL_EMOJI


# ══════════════════════════════════════════════════════════════════
# Part B — Integration: Components ทำงานร่วมกัน
# ══════════════════════════════════════════════════════════════════


# ── 5. Constructor ────────────────────────────────────────────────


class TestConstructor:
    """ทดสอบ TelegramNotifier.__init__()"""

    def test_enabled_true(self):
        n = _make_notifier(enabled="true")
        assert n.enabled is True

    def test_enabled_false(self):
        n = _make_notifier(enabled="false")
        assert n.enabled is False

    def test_token_loaded(self):
        n = _make_notifier(token="my-secret")
        assert n.token == "my-secret"

    def test_chat_id_loaded(self):
        n = _make_notifier(chat_id="987654")
        assert n.chat_id == "987654"

    def test_api_url_contains_token(self):
        n = _make_notifier(token="test-123")
        assert "test-123" in n.api_url
        assert "api.telegram.org" in n.api_url
        assert "/sendMessage" in n.api_url

    def test_notify_hold_loaded(self):
        n = _make_notifier(notify_hold="false")
        assert n.notify_hold is False

    def test_min_conf_loaded(self):
        n = _make_notifier(min_conf="0.7")
        assert n.min_conf == pytest.approx(0.7)

    def test_min_conf_default_zero(self):
        n = _make_notifier()
        assert n.min_conf == pytest.approx(0.0)

    def test_last_error_initially_none(self):
        n = _make_notifier()
        assert n.last_error is None


# ── 6. Guard Chain ────────────────────────────────────────────────


class TestGuardChain:
    """ทดสอบ guard chain: disabled → token → chat_id → HOLD → min_conf"""

    def test_disabled_blocks(self):
        n = _make_notifier(enabled="false")
        assert n.notify(_voting(), provider="mock", period="1h") is False

    def test_disabled_sets_last_error(self):
        n = _make_notifier(enabled="false")
        n.notify(_voting(), provider="mock", period="1h")
        assert n.last_error is not None

    def test_missing_token_blocks(self):
        n = _make_notifier(token="")
        assert n.notify(_voting(), provider="mock", period="1h") is False

    def test_missing_chat_id_blocks(self):
        n = _make_notifier(chat_id="")
        assert n.notify(_voting(), provider="mock", period="1h") is False

    def test_hold_signal_blocked_when_notify_hold_false(self):
        n = _make_notifier(notify_hold="false")
        assert n.notify(_voting(signal="HOLD"), provider="mock", period="1h") is False

    def test_hold_signal_passes_when_notify_hold_true(self):
        n = _make_notifier(notify_hold="true")
        with patch("httpx.post", return_value=_mock_httpx_success()):
            assert (
                n.notify(_voting(signal="HOLD"), provider="mock", period="1h") is True
            )

    def test_buy_always_passes_hold_filter(self):
        n = _make_notifier(notify_hold="false")
        with patch("httpx.post", return_value=_mock_httpx_success()):
            assert n.notify(_voting(signal="BUY"), provider="mock", period="1h") is True

    def test_sell_always_passes_hold_filter(self):
        n = _make_notifier(notify_hold="false")
        with patch("httpx.post", return_value=_mock_httpx_success()):
            assert (
                n.notify(_voting(signal="SELL"), provider="mock", period="1h") is True
            )

    def test_low_confidence_blocked(self):
        n = _make_notifier(min_conf="0.9")
        assert n.notify(_voting(confidence=0.7), provider="mock", period="1h") is False

    def test_exact_min_conf_passes(self):
        """confidence == min_conf → ไม่ถูก block (ไม่ strict less than)"""
        n = _make_notifier(min_conf="0.85")
        with patch("httpx.post", return_value=_mock_httpx_success()):
            assert (
                n.notify(_voting(confidence=0.85), provider="mock", period="1h") is True
            )

    def test_all_guards_pass_sends(self):
        """ทุก guard ผ่าน → httpx.post ถูกเรียก"""
        n = _make_notifier()
        with patch("httpx.post", return_value=_mock_httpx_success()) as mock_post:
            n.notify(_voting(), provider="mock", period="1h")
        mock_post.assert_called_once()


# ── 7. Full Pipeline ─────────────────────────────────────────────


class TestFullPipeline:
    """Integration: config → build message → httpx.post → return True"""

    def test_buy_full_flow(self):
        n = _make_notifier()
        ok, cap = _capture_post(
            n,
            voting_result=_voting(signal="BUY"),
            provider="gemini",
            period="daily",
            interval_results=_intervals_multi(),
            market_state=_market(),
        )
        assert ok is True
        assert "BUY" in cap["payload"]["text"]
        assert "gemini" in cap["payload"]["text"]

    def test_sell_full_flow(self):
        n = _make_notifier()
        ok, cap = _capture_post(
            n,
            voting_result=_voting(signal="SELL", confidence=0.75),
            provider="ollama",
            period="4h",
            interval_results=_intervals_single(),
            market_state=_market(),
        )
        assert ok is True
        assert "SELL" in cap["payload"]["text"]

    def test_hold_full_flow(self):
        n = _make_notifier(notify_hold="true")
        ok, cap = _capture_post(
            n,
            voting_result=_voting(signal="HOLD", confidence=0.5),
            provider="mock",
            period="1h",
        )
        assert ok is True
        assert "HOLD" in cap["payload"]["text"]

    def test_payload_has_chat_id(self):
        n = _make_notifier(chat_id="99999")
        _, cap = _capture_post(
            n,
            voting_result=_voting(),
            provider="mock",
            period="1h",
        )
        assert cap["payload"]["chat_id"] == "99999"

    def test_payload_disables_web_preview(self):
        n = _make_notifier()
        _, cap = _capture_post(
            n,
            voting_result=_voting(),
            provider="mock",
            period="1h",
        )
        assert cap["payload"]["disable_web_page_preview"] is True

    def test_post_url_matches_api_url(self):
        n = _make_notifier(token="mytoken")
        _, cap = _capture_post(
            n,
            voting_result=_voting(),
            provider="mock",
            period="1h",
        )
        assert cap["url"] == n.api_url

    def test_timeout_is_set(self):
        n = _make_notifier()
        _, cap = _capture_post(
            n,
            voting_result=_voting(),
            provider="mock",
            period="1h",
        )
        assert cap["timeout"] == 10


# ── 8. Message Building ──────────────────────────────────────────


class TestMessageBuilding:
    """ทดสอบเนื้อหา message ที่สร้างขึ้น"""

    def _text(self, **kwargs):
        """Helper: capture text from notify()"""
        n = _make_notifier()
        _, cap = _capture_post(n, **kwargs)
        return cap["payload"]["text"]

    def test_parse_mode_html(self):
        n = _make_notifier()
        _, cap = _capture_post(
            n,
            voting_result=_voting(),
            provider="mock",
            period="1h",
        )
        assert cap["payload"]["parse_mode"] == "HTML"

    def test_signal_emoji_in_title(self):
        text = self._text(
            voting_result=_voting(signal="BUY"), provider="mock", period="1h"
        )
        assert _SIGNAL_EMOJI["BUY"] in text
        assert "BUY" in text

    def test_sell_emoji_in_title(self):
        text = self._text(
            voting_result=_voting(signal="SELL"), provider="mock", period="1h"
        )
        assert _SIGNAL_EMOJI["SELL"] in text

    def test_provider_in_meta(self):
        text = self._text(voting_result=_voting(), provider="gemini", period="1h")
        assert "gemini" in text

    def test_period_in_meta(self):
        text = self._text(voting_result=_voting(), provider="mock", period="Daily")
        assert "Daily" in text

    def test_confidence_percentage_shown(self):
        text = self._text(
            voting_result=_voting(confidence=0.85), provider="mock", period="1h"
        )
        assert "85" in text

    def test_run_id_shown(self):
        text = self._text(
            voting_result=_voting(), provider="mock", period="1h", run_id=42
        )
        assert "#42" in text

    def test_run_id_omitted_when_none(self):
        text = self._text(
            voting_result=_voting(), provider="mock", period="1h", run_id=None
        )
        assert "#None" not in text

    # ── Target Levels ──

    def test_entry_stop_tp_shown(self):
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=_intervals_single(),
        )
        assert "45,000" in text  # entry
        assert "44,500" in text  # stop loss
        assert "46,000" in text  # take profit

    def test_no_target_levels_when_all_none(self):
        """entry/sl/tp ทั้งหมดเป็น None → ไม่แสดง Target Levels"""
        intervals = {
            "1h": {
                "signal": "HOLD",
                "confidence": 0.5,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
            }
        }
        text = self._text(
            voting_result=_voting(signal="HOLD"),
            provider="mock",
            period="1h",
            interval_results=intervals,
        )
        assert "Target" not in text

    def test_best_interval_used_for_prices(self):
        """ราคา entry ใช้จาก interval ที่ confidence สูงสุด"""
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=_intervals_multi(),
        )
        # best = 1h (conf=0.88) → entry=45200
        assert "45,200" in text

    # ── Market Data ──

    def test_market_prices_shown(self):
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            market_state=_market(),
        )
        assert "45,200" in text  # sell_price_thb
        assert "45,000" in text  # buy_price_thb
        assert "2,350.00" in text  # spot USD

    def test_usd_thb_shown(self):
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            market_state=_market(),
        )
        assert "34.50" in text

    def test_degraded_quality_badge(self):
        """data quality degraded → warning badge"""
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            market_state=_market(quality="degraded"),
        )
        assert "Degraded" in text

    def test_good_quality_badge(self):
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            market_state=_market(quality="good"),
        )
        assert "Good" in text

    def test_low_spot_confidence_shown(self):
        """spot_conf < 0.95 → แสดง conf %"""
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            market_state=_market(spot_conf=0.80),
        )
        assert "conf" in text.lower()

    def test_high_spot_confidence_hidden(self):
        """spot_conf >= 0.95 → ไม่แสดง conf %"""
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            market_state=_market(spot_conf=0.99),
        )
        assert "(conf" not in text

    def test_empty_market_no_crash(self):
        """market_state ว่าง → ไม่ crash, ไม่มี Market Data section"""
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            market_state={},
        )
        assert "BUY" in text

    # ── Breakdown ──

    def test_multi_interval_shows_breakdown(self):
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=_intervals_multi(),
        )
        assert "Breakdown" in text
        assert "1h" in text
        assert "4h" in text
        assert "15m" in text

    def test_single_interval_no_breakdown(self):
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=_intervals_single(),
        )
        assert "Breakdown" not in text

    def test_best_interval_marked(self):
        """best interval ต้องมีเครื่องหมาย ◀"""
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=_intervals_multi(),
        )
        assert "◀" in text

    # ── Voting ──

    def test_voting_summary_shown(self):
        text = self._text(
            voting_result=_voting(breakdown=True),
            provider="mock",
            period="1h",
        )
        assert "Voting" in text
        assert "vote" in text.lower()

    def test_no_voting_breakdown_no_section(self):
        text = self._text(
            voting_result=_voting(breakdown=False),
            provider="mock",
            period="1h",
        )
        assert "Voting" not in text

    # ── Rationale ──

    def test_rationale_shown_in_message(self):
        intervals = {
            "1h": {
                "signal": "BUY",
                "confidence": 0.9,
                "rationale": "RSI oversold + uptrend",
            }
        }
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=intervals,
        )
        assert "Rationale" in text
        assert "RSI oversold" in text

    def test_rationale_truncated_at_800(self):
        """rationale > 800 chars → ถูก truncate"""
        long = "a" * 1000
        intervals = {"1h": {"signal": "BUY", "confidence": 0.9, "rationale": long}}
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=intervals,
        )
        assert "a" * 801 not in text
        assert "…" in text  # truncation marker

    def test_rationale_html_escaped(self):
        """rationale มี < > & → ถูก escape ป้องกัน HTML injection"""
        intervals = {
            "1h": {
                "signal": "BUY",
                "confidence": 0.9,
                "rationale": "price < 45000 & trend > neutral",
            }
        }
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=intervals,
        )
        assert "&lt;" in text  # < escaped
        assert "&amp;" in text  # & escaped

    def test_empty_rationale_no_section(self):
        intervals = {"1h": {"signal": "BUY", "confidence": 0.9, "rationale": ""}}
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=intervals,
        )
        assert "Rationale" not in text

    def test_reasoning_fallback_key(self):
        """ถ้าไม่มี rationale ให้ใช้ reasoning แทน"""
        intervals = {
            "1h": {
                "signal": "BUY",
                "confidence": 0.9,
                "reasoning": "fallback reasoning",
            }
        }
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=intervals,
        )
        assert "fallback reasoning" in text

    # ── Interval count ──

    def test_interval_count_shown(self):
        """หลาย intervals → แสดงจำนวน interval"""
        text = self._text(
            voting_result=_voting(),
            provider="mock",
            period="1h",
            interval_results=_intervals_multi(),
        )
        assert "3" in text  # 3 intervals


# ── 9. Error Recovery ─────────────────────────────────────────────


class TestErrorRecovery:
    """ทดสอบ error handling + recovery flow"""

    def _http_error(self, status_code, text="Error"):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = text
        error = httpx.HTTPStatusError(
            str(status_code), request=MagicMock(), response=mock_resp
        )
        mock_resp.raise_for_status.side_effect = error
        return mock_resp

    def test_http_401_returns_false(self):
        n = _make_notifier()
        with patch("httpx.post", return_value=self._http_error(401, "Unauthorized")):
            assert n.notify(_voting(), provider="mock", period="1h") is False

    def test_http_403_sets_last_error(self):
        n = _make_notifier()
        with patch("httpx.post", return_value=self._http_error(403, "Forbidden")):
            n.notify(_voting(), provider="mock", period="1h")
        assert "403" in n.last_error

    def test_http_429_rate_limit(self):
        n = _make_notifier()
        with patch(
            "httpx.post", return_value=self._http_error(429, "Too Many Requests")
        ):
            result = n.notify(_voting(), provider="mock", period="1h")
        assert result is False
        assert "429" in n.last_error

    def test_http_500_server_error(self):
        n = _make_notifier()
        with patch(
            "httpx.post", return_value=self._http_error(500, "Internal Server Error")
        ):
            assert n.notify(_voting(), provider="mock", period="1h") is False

    def test_network_error_returns_false(self):
        n = _make_notifier()
        with patch("httpx.post", side_effect=Exception("Connection refused")):
            assert n.notify(_voting(), provider="mock", period="1h") is False

    def test_network_error_sets_last_error(self):
        n = _make_notifier()
        with patch("httpx.post", side_effect=Exception("timeout")):
            n.notify(_voting(), provider="mock", period="1h")
        assert "timeout" in n.last_error

    def test_timeout_error(self):
        n = _make_notifier()
        with patch("httpx.post", side_effect=Exception("ReadTimeout")):
            assert n.notify(_voting(), provider="mock", period="1h") is False

    def test_success_clears_last_error(self):
        """error → success → last_error = None"""
        n = _make_notifier()
        # ครั้งที่ 1: fail
        with patch("httpx.post", side_effect=Exception("boom")):
            n.notify(_voting(), provider="mock", period="1h")
        assert n.last_error is not None

        # ครั้งที่ 2: success → clear
        with patch("httpx.post", return_value=_mock_httpx_success()):
            result = n.notify(_voting(), provider="mock", period="1h")
        assert result is True
        assert n.last_error is None

    def test_last_error_format_includes_status_and_text(self):
        """last_error ต้องมี HTTP status code + response text"""
        n = _make_notifier()
        with patch("httpx.post", return_value=self._http_error(403, "Forbidden")):
            n.notify(_voting(), provider="mock", period="1h")
        assert "HTTP" in n.last_error
        assert "403" in n.last_error
        assert "Forbidden" in n.last_error


# ── 10. Runtime Toggle ────────────────────────────────────────────


class TestRuntimeToggle:
    """ทดสอบ update_enabled / update_hold_toggle → เปลี่ยน behavior"""

    def test_disable_then_notify_blocked(self):
        n = _make_notifier()
        n.update_enabled(False)
        with patch("httpx.post", return_value=_mock_httpx_success()) as mock_post:
            result = n.notify(_voting(), provider="mock", period="1h")
        assert result is False
        mock_post.assert_not_called()

    def test_reenable_then_notify_passes(self):
        n = _make_notifier()
        n.update_enabled(False)
        n.update_enabled(True)
        with patch("httpx.post", return_value=_mock_httpx_success()):
            assert n.notify(_voting(), provider="mock", period="1h") is True

    def test_hold_toggle_off_blocks_hold(self):
        n = _make_notifier()
        n.update_hold_toggle(False)
        result = n.notify(_voting(signal="HOLD"), provider="mock", period="1h")
        assert result is False

    def test_hold_toggle_off_allows_buy(self):
        n = _make_notifier()
        n.update_hold_toggle(False)
        with patch("httpx.post", return_value=_mock_httpx_success()):
            assert n.notify(_voting(signal="BUY"), provider="mock", period="1h") is True

    def test_update_enabled_syncs_env(self):
        """update_enabled → os.environ อัพเดทด้วย"""
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_NOTIFY_ENABLED": "true",
                "TELEGRAM_BOT_TOKEN": "tok",
                "TELEGRAM_CHAT_ID": "123",
            },
            clear=False,
        ):
            n = TelegramNotifier()
            n.update_enabled(False)
            assert os.environ["TELEGRAM_NOTIFY_ENABLED"] == "false"
            n.update_enabled(True)
            assert os.environ["TELEGRAM_NOTIFY_ENABLED"] == "true"

    def test_update_hold_toggle_syncs_env(self):
        """update_hold_toggle → os.environ อัพเดทด้วย"""
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_NOTIFY_ENABLED": "true",
                "TELEGRAM_BOT_TOKEN": "tok",
                "TELEGRAM_CHAT_ID": "123",
                "TELEGRAM_NOTIFY_HOLD": "true",
            },
            clear=False,
        ):
            n = TelegramNotifier()
            n.update_hold_toggle(False)
            assert os.environ["TELEGRAM_NOTIFY_HOLD"] == "false"


# ── 11. Status ────────────────────────────────────────────────────


class TestStatus:
    """ทดสอบ status() สะท้อนสถานะปัจจุบัน"""

    def test_returns_dict(self):
        assert isinstance(_make_notifier().status(), dict)

    def test_has_all_required_keys(self):
        s = _make_notifier().status()
        for key in (
            "enabled",
            "notify_hold",
            "min_conf",
            "chat_id_set",
            "token_set",
            "last_error",
        ):
            assert key in s

    def test_initial_values_correct(self):
        n = _make_notifier(enabled="true", token="tok", chat_id="123", min_conf="0.5")
        s = n.status()
        assert s["enabled"] is True
        assert s["token_set"] is True
        assert s["chat_id_set"] is True
        assert s["min_conf"] == pytest.approx(0.5)
        assert s["last_error"] is None

    def test_enabled_reflects_toggle(self):
        n = _make_notifier()
        n.update_enabled(False)
        assert n.status()["enabled"] is False

    def test_notify_hold_reflects_toggle(self):
        n = _make_notifier()
        n.update_hold_toggle(False)
        assert n.status()["notify_hold"] is False

    def test_token_set_false_when_empty(self):
        assert _make_notifier(token="").status()["token_set"] is False

    def test_chat_id_set_false_when_empty(self):
        assert _make_notifier(chat_id="").status()["chat_id_set"] is False

    def test_last_error_after_failure(self):
        n = _make_notifier()
        with patch("httpx.post", side_effect=Exception("boom")):
            n.notify(_voting(), provider="mock", period="1h")
        s = n.status()
        assert s["last_error"] is not None
        assert "boom" in s["last_error"]

    def test_last_error_cleared_after_success(self):
        n = _make_notifier()
        with patch("httpx.post", side_effect=Exception("fail")):
            n.notify(_voting(), provider="mock", period="1h")
        with patch("httpx.post", return_value=_mock_httpx_success()):
            n.notify(_voting(), provider="mock", period="1h")
        assert n.status()["last_error"] is None


# ── 12. Edge Cases ────────────────────────────────────────────────


class TestEdgeCases:
    """ทดสอบ edge cases ที่อาจเกิดในการใช้งานจริง"""

    def test_no_interval_results_no_crash(self):
        """interval_results=None → ไม่ crash"""
        n = _make_notifier()
        with patch("httpx.post", return_value=_mock_httpx_success()):
            result = n.notify(
                _voting(), provider="mock", period="1h", interval_results=None
            )
        assert result is True

    def test_empty_interval_results_no_crash(self):
        """interval_results={} → ไม่ crash"""
        n = _make_notifier()
        with patch("httpx.post", return_value=_mock_httpx_success()):
            result = n.notify(
                _voting(), provider="mock", period="1h", interval_results={}
            )
        assert result is True

    def test_no_market_state_no_crash(self):
        """market_state=None → ไม่ crash"""
        n = _make_notifier()
        with patch("httpx.post", return_value=_mock_httpx_success()):
            result = n.notify(
                _voting(), provider="mock", period="1h", market_state=None
            )
        assert result is True

    def test_empty_market_state_no_crash(self):
        n = _make_notifier()
        with patch("httpx.post", return_value=_mock_httpx_success()):
            result = n.notify(_voting(), provider="mock", period="1h", market_state={})
        assert result is True

    def test_voting_without_breakdown(self):
        """voting_result ไม่มี voting_breakdown → ไม่ crash"""
        n = _make_notifier()
        with patch("httpx.post", return_value=_mock_httpx_success()):
            result = n.notify(
                {"final_signal": "BUY", "weighted_confidence": 0.8},
                provider="mock",
                period="1h",
            )
        assert result is True

    def test_unknown_signal_uses_fallback_emoji(self):
        """signal ที่ไม่รู้จัก → ใช้ ⚪ แทน"""
        n = _make_notifier()
        _, cap = _capture_post(
            n,
            voting_result={"final_signal": "UNKNOWN", "weighted_confidence": 0.5},
            provider="mock",
            period="1h",
        )
        assert "⚪" in cap["payload"]["text"]

    def test_kwargs_passthrough_no_crash(self):
        """extra kwargs → ไม่ crash (notify มี **kwargs)"""
        n = _make_notifier()
        with patch("httpx.post", return_value=_mock_httpx_success()):
            result = n.notify(
                _voting(),
                provider="mock",
                period="1h",
                extra_param="ignored",
                another=123,
            )
        assert result is True

    def test_missing_voting_keys_uses_defaults(self):
        """voting_result ไม่มี key → ใช้ defaults (HOLD, 0.0)"""
        n = _make_notifier()
        _, cap = _capture_post(
            n,
            voting_result={},
            provider="mock",
            period="1h",
        )
        assert "HOLD" in cap["payload"]["text"]
