"""
test_session_gate.py — Pytest for agent_core/core/session_gate.py

Covers:
  1. Weekday session windows (night, morning, noon, evening)
  2. Dead-zone gap (02:00–06:14) outside all windows
  3. Weekend window (09:30–17:30)
  4. Edge mode vs Quota mode (urgent_threshold_minutes boundary)
  5. force_bypass parameter
  6. Return structure (apply_gate, session_id, llm_mode, suggested_min_confidence, etc.)
  7. to_market_dict() output
"""

import pytest
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    _BKK = ZoneInfo("Asia/Bangkok")
except ImportError:
    from datetime import timezone
    _BKK = timezone.utc  # type: ignore — fallback for environments without zoneinfo

from agent_core.core.session_gate import (
    resolve_session_gate,
    SessionGateResult,
    attach_session_gate_to_market_state,
    URGENT_MINUTES_DEFAULT,
)

pytestmark = [pytest.mark.unit]

# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def make_bkk_dt():
    """
    Factory: (weekday_int, hour, minute) -> tz-aware datetime in Asia/Bangkok.
    weekday 0=Monday … 5=Saturday, 6=Sunday.
    Anchored to Monday 2026-04-13 then shifted by delta_days.
    """
    ANCHOR = datetime(2026, 4, 13, tzinfo=_BKK)  # known Monday

    def _factory(weekday: int, hour: int, minute: int) -> datetime:
        delta_days = weekday - ANCHOR.weekday()
        return ANCHOR.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=delta_days)

    return _factory


# ─────────────────────────────────────────────────────────────────────
# TestWeekdayWindowsApplyGate
# ─────────────────────────────────────────────────────────────────────


class TestWeekdayWindowsApplyGate:
    """Verify apply_gate and session_id for each weekday trading window."""

    def test_night_window_00_30(self, make_bkk_dt):
        """Mon 00:30 is inside night window (00:00–01:59) → apply_gate=True, session='night'."""
        result = resolve_session_gate(now=make_bkk_dt(0, 0, 30))
        assert result.apply_gate is True
        assert result.session_id == "night"

    def test_night_window_end_boundary_01_59(self, make_bkk_dt):
        """Mon 01:59 is last minute of night window → apply_gate=True."""
        result = resolve_session_gate(now=make_bkk_dt(0, 1, 59))
        assert result.apply_gate is True
        assert result.session_id == "night"

    def test_dead_zone_start_02_00_is_outside_windows(self, make_bkk_dt):
        """Mon 02:00 falls in the dead zone gap (no window) → apply_gate=False."""
        result = resolve_session_gate(now=make_bkk_dt(0, 2, 0))
        assert result.apply_gate is False

    def test_dead_zone_end_06_14_is_outside_windows(self, make_bkk_dt):
        """Mon 06:14 is still in the dead zone gap → apply_gate=False."""
        result = resolve_session_gate(now=make_bkk_dt(0, 6, 14))
        assert result.apply_gate is False

    def test_morning_window_opens_06_15(self, make_bkk_dt):
        """Mon 06:15 is the first minute of morning window → apply_gate=True, session='morning'."""
        result = resolve_session_gate(now=make_bkk_dt(0, 6, 15))
        assert result.apply_gate is True
        assert result.session_id == "morning"

    def test_morning_window_mid_09_00(self, make_bkk_dt):
        """Mon 09:00 is mid morning window → apply_gate=True."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        assert result.apply_gate is True
        assert result.session_id == "morning"

    def test_noon_window_12_00(self, make_bkk_dt):
        """Mon 12:00 is start of noon window → apply_gate=True, session='noon'."""
        result = resolve_session_gate(now=make_bkk_dt(0, 12, 0))
        assert result.apply_gate is True
        assert result.session_id == "noon"

    def test_noon_window_14_00(self, make_bkk_dt):
        """Mon 14:00 is mid noon window → apply_gate=True."""
        result = resolve_session_gate(now=make_bkk_dt(0, 14, 0))
        assert result.apply_gate is True
        assert result.session_id == "noon"

    def test_evening_window_18_00(self, make_bkk_dt):
        """Mon 18:00 is start of evening window → apply_gate=True, session='evening'."""
        result = resolve_session_gate(now=make_bkk_dt(0, 18, 0))
        assert result.apply_gate is True
        assert result.session_id == "evening"

    def test_evening_window_20_00(self, make_bkk_dt):
        """Mon 20:00 is mid evening window → apply_gate=True."""
        result = resolve_session_gate(now=make_bkk_dt(0, 20, 0))
        assert result.apply_gate is True
        assert result.session_id == "evening"

    def test_evening_window_end_23_59(self, make_bkk_dt):
        """Mon 23:59 is last minute of evening window → apply_gate=True."""
        result = resolve_session_gate(now=make_bkk_dt(0, 23, 59))
        assert result.apply_gate is True
        assert result.session_id == "evening"

    def test_dead_zone_gap_03_00(self, make_bkk_dt):
        """Mon 03:00 is in the dead zone gap between night and morning → apply_gate=False."""
        result = resolve_session_gate(now=make_bkk_dt(0, 3, 0))
        assert result.apply_gate is False


# ─────────────────────────────────────────────────────────────────────
# TestWeekendWindow
# ─────────────────────────────────────────────────────────────────────


class TestWeekendWindow:
    """Verify weekend session window (09:30–17:30)."""

    def test_saturday_within_window_12_00(self, make_bkk_dt):
        """Sat 12:00 is inside weekend window → apply_gate=True, session='weekend'."""
        result = resolve_session_gate(now=make_bkk_dt(5, 12, 0))
        assert result.apply_gate is True
        assert result.session_id == "weekend"

    def test_saturday_start_boundary_09_30(self, make_bkk_dt):
        """Sat 09:30 is the first minute of weekend window → apply_gate=True."""
        result = resolve_session_gate(now=make_bkk_dt(5, 9, 30))
        assert result.apply_gate is True
        assert result.session_id == "weekend"

    def test_saturday_before_window_08_00(self, make_bkk_dt):
        """Sat 08:00 is before weekend window → apply_gate=False."""
        result = resolve_session_gate(now=make_bkk_dt(5, 8, 0))
        assert result.apply_gate is False

    def test_saturday_end_boundary_17_30(self, make_bkk_dt):
        """Sat 17:30 is the last minute of weekend window → apply_gate=True."""
        result = resolve_session_gate(now=make_bkk_dt(5, 17, 30))
        assert result.apply_gate is True

    def test_saturday_after_window_18_00(self, make_bkk_dt):
        """Sat 18:00 is after weekend window closes → apply_gate=False."""
        result = resolve_session_gate(now=make_bkk_dt(5, 18, 0))
        assert result.apply_gate is False

    def test_sunday_within_window_10_00(self, make_bkk_dt):
        """Sun 10:00 is inside weekend window → apply_gate=True, session='weekend'."""
        result = resolve_session_gate(now=make_bkk_dt(6, 10, 0))
        assert result.apply_gate is True
        assert result.session_id == "weekend"

    def test_sunday_before_window_09_00(self, make_bkk_dt):
        """Sun 09:00 is before weekend window → apply_gate=False."""
        result = resolve_session_gate(now=make_bkk_dt(6, 9, 0))
        assert result.apply_gate is False


# ─────────────────────────────────────────────────────────────────────
# TestEdgeVsQuotaMode
# ─────────────────────────────────────────────────────────────────────


class TestEdgeVsQuotaMode:
    """
    Edge mode vs Quota mode based on minutes_to_session_end vs urgent_threshold_minutes.

    Default URGENT_MINUTES_DEFAULT = 15:
      > 15 min left  → edge mode, suggested_min_confidence = 0.70
      ≤ 15 min left  → quota mode, suggested_min_confidence = 0.55
    """

    def test_edge_mode_when_far_from_end(self, make_bkk_dt):
        """Mon 09:00 (morning window ends 11:59 = 179 min away) → edge mode."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        assert result.apply_gate is True
        assert result.llm_mode == "edge"
        assert result.suggested_min_confidence == 0.70
        assert result.quota_urgent is False

    def test_quota_mode_when_near_end_within_15min(self, make_bkk_dt):
        """Mon 11:45 (morning window ends 11:59 = 14 min away) → quota mode."""
        result = resolve_session_gate(now=make_bkk_dt(0, 11, 45))
        assert result.apply_gate is True
        assert result.llm_mode == "quota"
        assert result.suggested_min_confidence == 0.55
        assert result.quota_urgent is True

    def test_quota_boundary_exactly_15min_left(self, make_bkk_dt):
        """Mon 11:44 (morning ends 11:59 = 15 min away) → quota mode (≤ threshold)."""
        result = resolve_session_gate(now=make_bkk_dt(0, 11, 44))
        mins_left = result.minutes_to_session_end
        assert mins_left == 15
        assert result.llm_mode == "quota"
        assert result.quota_urgent is True

    def test_edge_boundary_exactly_16min_left(self, make_bkk_dt):
        """Mon 11:43 (morning ends 11:59 = 16 min away) → edge mode (> threshold)."""
        result = resolve_session_gate(now=make_bkk_dt(0, 11, 43))
        mins_left = result.minutes_to_session_end
        assert mins_left == 16
        assert result.llm_mode == "edge"
        assert result.quota_urgent is False

    def test_custom_urgent_threshold_overrides_default(self, make_bkk_dt):
        """urgent_threshold_minutes=30: 20 min left → quota mode."""
        result = resolve_session_gate(now=make_bkk_dt(0, 11, 39), urgent_threshold_minutes=30)
        # 11:59 - 11:39 = 20 min → ≤ 30 → quota
        assert result.quota_urgent is True
        assert result.llm_mode == "quota"

    def test_minutes_to_session_end_non_negative(self, make_bkk_dt):
        """minutes_to_session_end must always be >= 0 when apply_gate is True."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        assert result.apply_gate is True
        assert result.minutes_to_session_end >= 0


# ─────────────────────────────────────────────────────────────────────
# TestForceBypass
# ─────────────────────────────────────────────────────────────────────


class TestForceBypass:
    """force_bypass=True returns apply_gate=False regardless of time."""

    def test_force_bypass_during_active_session(self, make_bkk_dt):
        """force_bypass=True during morning window → apply_gate=False."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0), force_bypass=True)
        assert result.apply_gate is False

    def test_force_bypass_notes_contain_bypass_message(self, make_bkk_dt):
        """force_bypass result notes must mention bypass."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0), force_bypass=True)
        assert any("bypass" in n.lower() or "force_bypass" in n.lower() for n in result.notes)

    def test_force_bypass_false_respects_window(self, make_bkk_dt):
        """force_bypass=False (default) → normal gate resolution."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0), force_bypass=False)
        assert result.apply_gate is True

    def test_force_bypass_during_dead_zone(self, make_bkk_dt):
        """force_bypass=True during dead zone → apply_gate=False (same as normal — dead zone also returns False)."""
        result_bypass = resolve_session_gate(now=make_bkk_dt(0, 3, 0), force_bypass=True)
        result_normal = resolve_session_gate(now=make_bkk_dt(0, 3, 0), force_bypass=False)
        assert result_bypass.apply_gate is False
        assert result_normal.apply_gate is False


# ─────────────────────────────────────────────────────────────────────
# TestReturnStructure
# ─────────────────────────────────────────────────────────────────────


class TestReturnStructure:
    """Verify that SessionGateResult has the expected fields and to_market_dict() output."""

    def test_return_type_is_session_gate_result(self, make_bkk_dt):
        """resolve_session_gate always returns a SessionGateResult."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        assert isinstance(result, SessionGateResult)

    def test_apply_gate_true_has_all_required_fields(self, make_bkk_dt):
        """When apply_gate=True, all gate fields must be set."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        assert result.apply_gate is True
        assert result.session_id is not None
        assert result.quota_group_id is not None
        assert result.llm_mode in ("edge", "quota")
        assert result.suggested_min_confidence is not None
        assert result.minutes_to_session_end is not None

    def test_apply_gate_false_outside_window_fields_are_none(self, make_bkk_dt):
        """When apply_gate=False (outside window), session-specific fields are None."""
        result = resolve_session_gate(now=make_bkk_dt(0, 3, 0))  # dead zone
        assert result.apply_gate is False
        assert result.session_id is None
        assert result.llm_mode is None

    def test_suggested_min_confidence_in_range(self, make_bkk_dt):
        """suggested_min_confidence must be between 0.0 and 1.0 inclusive."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        assert 0.0 <= result.suggested_min_confidence <= 1.0

    def test_notes_is_list(self, make_bkk_dt):
        """notes field must always be a list."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        assert isinstance(result.notes, list)

    def test_to_market_dict_keys(self, make_bkk_dt):
        """to_market_dict() must contain all required keys."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        d = result.to_market_dict()
        expected_keys = {
            "apply_gate", "session_id", "quota_group_id",
            "quota_urgent", "minutes_to_session_end",
            "llm_mode", "suggested_min_confidence", "notes",
        }
        assert expected_keys.issubset(d.keys())

    def test_to_market_dict_values_match_result(self, make_bkk_dt):
        """to_market_dict() values must mirror the SessionGateResult attributes."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        d = result.to_market_dict()
        assert d["apply_gate"] == result.apply_gate
        assert d["session_id"] == result.session_id
        assert d["quota_urgent"] == result.quota_urgent
        assert d["llm_mode"] == result.llm_mode
        assert d["suggested_min_confidence"] == result.suggested_min_confidence


# ─────────────────────────────────────────────────────────────────────
# TestAttachSessionGateToMarketState
# ─────────────────────────────────────────────────────────────────────


class TestAttachSessionGateToMarketState:
    """Verify attach_session_gate_to_market_state mutates market_state correctly."""

    def test_apply_gate_true_injects_session_gate_key(self, make_bkk_dt):
        """apply_gate=True → market_state['session_gate'] is populated."""
        result = resolve_session_gate(now=make_bkk_dt(0, 9, 0))
        state = {}
        attach_session_gate_to_market_state(state, result)
        assert "session_gate" in state
        assert state["session_gate"]["apply_gate"] is True

    def test_apply_gate_false_removes_session_gate_key(self, make_bkk_dt):
        """apply_gate=False → session_gate key is removed from market_state."""
        result = resolve_session_gate(now=make_bkk_dt(0, 3, 0))  # dead zone
        state = {"session_gate": {"old": "data"}}
        attach_session_gate_to_market_state(state, result)
        assert "session_gate" not in state
