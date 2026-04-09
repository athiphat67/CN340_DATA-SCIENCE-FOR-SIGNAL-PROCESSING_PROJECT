"""
Src/tests/test_unit/test_session_manager.py
══════════════════════════════════════════════════════════════════════
ทดสอบ TradingSessionManager (backtest/engine/session_manager.py)

โครงสร้าง Session ออม NOW:
  จันทร์–ศุกร์ : LATE(00:00–01:59) | MORN(06:15–11:59)
                  AFTN(12:00–17:59) | EVEN(18:00–23:59)
  Dead zone    : 02:00–06:14
  เสาร์–อาทิตย์ : E(09:30–17:30)
══════════════════════════════════════════════════════════════════════
"""

import pytest
import pandas as pd

from backtest.engine.session_manager import (
    TradingSessionManager,
    SessionInfo,
    SessionResult,
    TimeRange,
    SessionDef,
    WEEKDAY_SESSIONS,
    WEEKEND_SESSIONS,
)

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _ts(dt_str: str) -> pd.Timestamp:
    """สร้าง Timestamp จาก string เช่น '2026-04-06 06:15'"""
    return pd.Timestamp(dt_str)

def _sm() -> TradingSessionManager:
    """สร้าง instance ใหม่ทุกครั้ง (stateless)"""
    return TradingSessionManager()


# ══════════════════════════════════════════════
# TimeRange
# ══════════════════════════════════════════════

class TestTimeRange:
    """ทดสอบ TimeRange.contains()"""

    def test_contains_start_boundary(self):
        """เวลาเท่ากับ start → อยู่ใน range"""
        from datetime import time
        tr = TimeRange(time(6, 15), time(11, 59))
        assert tr.contains(time(6, 15)) is True

    def test_contains_end_boundary(self):
        """เวลาเท่ากับ end → อยู่ใน range"""
        from datetime import time
        tr = TimeRange(time(6, 15), time(11, 59))
        assert tr.contains(time(11, 59)) is True

    def test_contains_middle(self):
        """เวลากลาง range → อยู่ใน range"""
        from datetime import time
        tr = TimeRange(time(6, 15), time(11, 59))
        assert tr.contains(time(9, 0)) is True

    def test_not_contains_before_start(self):
        """เวลาก่อน start → ไม่อยู่ใน range"""
        from datetime import time
        tr = TimeRange(time(6, 15), time(11, 59))
        assert tr.contains(time(6, 14)) is False

    def test_not_contains_after_end(self):
        """เวลาหลัง end → ไม่อยู่ใน range"""
        from datetime import time
        tr = TimeRange(time(6, 15), time(11, 59))
        assert tr.contains(time(12, 0)) is False


# ══════════════════════════════════════════════
# SessionDef
# ══════════════════════════════════════════════

class TestSessionDef:
    """ทดสอบ SessionDef.contains() และ last_end"""

    def test_weekday_sessions_ids(self):
        """WEEKDAY_SESSIONS ต้องมี LATE, MORN, AFTN, EVEN"""
        ids = {s.id for s in WEEKDAY_SESSIONS}
        assert ids == {"LATE", "MORN", "AFTN", "EVEN"}

    def test_weekend_sessions_ids(self):
        """WEEKEND_SESSIONS ต้องมี E"""
        ids = {s.id for s in WEEKEND_SESSIONS}
        assert ids == {"E"}

    def test_morn_session_starts_at_0615(self):
        """MORN session ต้องเริ่มที่ 06:15 ไม่ใช่ 06:00"""
        from datetime import time
        morn = next(s for s in WEEKDAY_SESSIONS if s.id == "MORN")
        assert morn.ranges[0].start == time(6, 15)

    def test_late_last_end(self):
        """LATE session ต้อง last_end = 01:59"""
        from datetime import time
        late = next(s for s in WEEKDAY_SESSIONS if s.id == "LATE")
        assert late.last_end == time(1, 59)


# ══════════════════════════════════════════════
# _find_session — Weekday
# ══════════════════════════════════════════════

class TestFindSessionWeekday:
    """ทดสอบ _find_session() วันจันทร์–ศุกร์"""

    def test_late_session_at_0030(self):
        """00:30 จันทร์ → LATE"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 00:30"))
        assert result is not None and result.id == "LATE"

    def test_late_session_boundary_0159(self):
        """01:59 จันทร์ → ยังเป็น LATE"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 01:59"))
        assert result is not None and result.id == "LATE"

    def test_dead_zone_at_0200(self):
        """02:00 → Dead zone, คืน None"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 02:00"))
        assert result is None

    def test_dead_zone_at_0201(self):
        """02:01 → Dead zone"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 02:01"))
        assert result is None

    def test_dead_zone_midpoint_0430(self):
        """04:30 → Dead zone"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 04:30"))
        assert result is None

    def test_dead_zone_boundary_0614(self):
        """06:14 → ยัง Dead zone (ยังไม่เปิด)"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 06:14"))
        assert result is None

    def test_morn_opens_at_0615(self):
        """06:15 → MORN เปิดพอดี"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 06:15"))
        assert result is not None and result.id == "MORN"

    def test_morn_session_at_0616(self):
        """06:16 → MORN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 06:16"))
        assert result is not None and result.id == "MORN"

    def test_morn_session_boundary_1159(self):
        """11:59 → MORN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 11:59"))
        assert result is not None and result.id == "MORN"

    def test_aftn_session_at_1200(self):
        """12:00 → AFTN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 12:00"))
        assert result is not None and result.id == "AFTN"

    def test_aftn_session_at_1500(self):
        """15:00 → AFTN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 15:00"))
        assert result is not None and result.id == "AFTN"

    def test_aftn_boundary_1759(self):
        """17:59 → AFTN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 17:59"))
        assert result is not None and result.id == "AFTN"

    def test_even_session_at_1800(self):
        """18:00 → EVEN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 18:00"))
        assert result is not None and result.id == "EVEN"

    def test_even_session_at_2300(self):
        """23:00 → EVEN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 23:00"))
        assert result is not None and result.id == "EVEN"

    def test_even_boundary_2359(self):
        """23:59 → EVEN"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-06 23:59"))
        assert result is not None and result.id == "EVEN"

    def test_friday_same_as_monday(self):
        """ศุกร์ 06:15 → MORN เหมือนจันทร์"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-10 06:15"))  # ศุกร์
        assert result is not None and result.id == "MORN"


# ══════════════════════════════════════════════
# _find_session — Weekend
# ══════════════════════════════════════════════

class TestFindSessionWeekend:
    """ทดสอบ _find_session() วันเสาร์–อาทิตย์"""

    def test_saturday_before_open(self):
        """เสาร์ 09:29 → ยังปิด, คืน None"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-11 09:29"))  # เสาร์
        assert result is None

    def test_saturday_opens_at_0930(self):
        """เสาร์ 09:30 → E เปิดพอดี"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-11 09:30"))
        assert result is not None and result.id == "E"

    def test_saturday_midday(self):
        """เสาร์ 13:00 → E"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-11 13:00"))
        assert result is not None and result.id == "E"

    def test_saturday_closes_at_1730(self):
        """เสาร์ 17:30 → E ยังเปิด (inclusive boundary)"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-11 17:30"))
        assert result is not None and result.id == "E"

    def test_saturday_after_close(self):
        """เสาร์ 17:31 → ปิดแล้ว, คืน None"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-11 17:31"))
        assert result is None

    def test_sunday_same_as_saturday(self):
        """อาทิตย์ 10:00 → E เหมือนเสาร์"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-12 10:00"))  # อาทิตย์
        assert result is not None and result.id == "E"

    def test_weekend_dead_zone_not_applicable(self):
        """เสาร์ 02:00–06:14 ไม่มี session E → คืน None (weekend ไม่มี dead zone เหมือน weekday)"""
        sm = _sm()
        result = sm._find_session(_ts("2026-04-11 03:00"))
        assert result is None


# ══════════════════════════════════════════════
# process_candle
# ══════════════════════════════════════════════

class TestProcessCandle:
    """ทดสอบ process_candle() ว่าคืน SessionInfo ถูกต้อง"""

    def test_returns_session_info(self):
        """ต้องคืน SessionInfo เสมอ"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 09:00"))
        assert isinstance(info, SessionInfo)

    def test_can_execute_true_in_session(self):
        """อยู่ใน session → can_execute = True"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 09:00"))
        assert info.can_execute is True
        assert info.is_outside is False

    def test_can_execute_false_in_dead_zone(self):
        """Dead zone → can_execute = False"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 03:30"))
        assert info.can_execute is False
        assert info.is_outside is True

    def test_session_id_correct(self):
        """process_candle ต้องระบุ session_id ถูกต้อง"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 14:00"))
        assert info.session_id == "AFTN"

    def test_dead_zone_session_id_is_none(self):
        """Dead zone → session_id = None"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 04:00"))
        assert info.session_id is None

    def test_dead_zone_description_mentions_dead(self):
        """Dead zone description ต้องมีคำว่า 'dead' หรือ 'zone'"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 04:00"))
        assert "dead" in info.description.lower() or "zone" in info.description.lower()

    def test_label_in_session(self):
        """label ต้องอยู่ใน format [SESSION_ID] เมื่ออยู่ใน session"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 09:00"))
        assert info.label.startswith("[") and info.label.endswith("]")
        assert info.label != "[DEAD]"

    def test_label_dead_zone(self):
        """label ใน Dead zone ต้องเป็น [DEAD]"""
        sm = _sm()
        info = sm.process_candle(_ts("2026-04-06 04:00"))
        assert info.label == "[DEAD]"


# ══════════════════════════════════════════════
# record_trade
# ══════════════════════════════════════════════

class TestRecordTrade:
    """ทดสอบ record_trade() นับเทรดใน session"""

    def test_record_trade_in_session(self):
        """บันทึก trade ใน session → trades ต้องเพิ่มขึ้น"""
        sm = _sm()
        ts = _ts("2026-04-06 09:00")
        sm.process_candle(ts)
        sm.record_trade(ts)
        key = ("2026-04-06", "MORN")
        assert sm._trades.get(key, 0) == 1

    def test_record_multiple_trades(self):
        """บันทึก 3 trade ใน session เดียว → นับได้ 3"""
        sm = _sm()
        date = "2026-04-06"
        for t in ["09:00", "10:00", "11:00"]:
            ts = _ts(f"{date} {t}")
            sm.process_candle(ts)
            sm.record_trade(ts)
        key = (date, "MORN")
        assert sm._trades.get(key, 0) == 3

    def test_record_trade_outside_session_no_crash(self):
        """record_trade นอก session → ต้องไม่ crash"""
        sm = _sm()
        ts = _ts("2026-04-06 03:00")  # dead zone
        sm.process_candle(ts)
        sm.record_trade(ts)  # ต้องไม่ raise

    def test_trades_separated_by_session(self):
        """trades ใน MORN และ AFTN ต้องนับแยกกัน"""
        sm = _sm()
        date = "2026-04-06"
        sm.process_candle(_ts(f"{date} 09:00"))
        sm.record_trade(_ts(f"{date} 09:00"))   # MORN
        sm.process_candle(_ts(f"{date} 14:00"))
        sm.record_trade(_ts(f"{date} 14:00"))   # AFTN
        sm.record_trade(_ts(f"{date} 14:30"))   # AFTN

        assert sm._trades.get((date, "MORN"), 0) == 1
        assert sm._trades.get((date, "AFTN"), 0) == 2


# ══════════════════════════════════════════════
# compliance_report — Empty
# ══════════════════════════════════════════════

class TestComplianceReportEmpty:
    """ทดสอบ compliance_report() เมื่อยังไม่มีข้อมูล"""

    def test_empty_report_structure(self):
        """ยังไม่ได้ process อะไร → report ต้องมี keys ครบ"""
        sm = _sm()
        report = sm.compliance_report()
        expected_keys = {
            "total_sessions", "passed_sessions", "failed_sessions",
            "no_data_sessions", "compliance_pct", "session_fail_flag",
            "failed_details", "all_details",
        }
        assert expected_keys.issubset(report.keys())

    def test_empty_report_zeros(self):
        """ยังไม่มีข้อมูล → total/passed/failed = 0"""
        sm = _sm()
        report = sm.compliance_report()
        assert report["total_sessions"] == 0
        assert report["passed_sessions"] == 0
        assert report["failed_sessions"] == 0
        assert report["compliance_pct"] == 0.0

    def test_empty_report_no_fail_flag(self):
        """ยังไม่มีข้อมูล → session_fail_flag = False"""
        sm = _sm()
        report = sm.compliance_report()
        assert report["session_fail_flag"] is False

    def test_empty_details_lists(self):
        """failed_details และ all_details ต้องเป็น list ว่าง"""
        sm = _sm()
        report = sm.compliance_report()
        assert report["failed_details"] == []
        assert report["all_details"] == []


# ══════════════════════════════════════════════
# compliance_report — After finalize
# ══════════════════════════════════════════════

class TestComplianceReportAfterFinalize:
    """ทดสอบ compliance_report() หลัง finalize()"""

    def _run_one_day_pass(self) -> TradingSessionManager:
        """Simulate วันที่ trade ครบทุก session"""
        sm = _sm()
        date = "2026-04-06"
        # LATE: ต้องการ 1 trade
        sm.process_candle(_ts(f"{date} 00:30"))
        sm.record_trade(_ts(f"{date} 00:30"))
        # MORN: ต้องการ 2 trade
        sm.process_candle(_ts(f"{date} 08:00"))
        sm.record_trade(_ts(f"{date} 08:00"))
        sm.record_trade(_ts(f"{date} 09:00"))
        # AFTN: ต้องการ 2 trade
        sm.process_candle(_ts(f"{date} 13:00"))
        sm.record_trade(_ts(f"{date} 13:00"))
        sm.record_trade(_ts(f"{date} 14:00"))
        # EVEN: ต้องการ 2 trade
        sm.process_candle(_ts(f"{date} 19:00"))
        sm.record_trade(_ts(f"{date} 19:00"))
        sm.record_trade(_ts(f"{date} 20:00"))
        sm.finalize()
        return sm

    def test_pass_sessions_counted(self):
        """trade ครบ → passed_sessions > 0"""
        sm = self._run_one_day_pass()
        report = sm.compliance_report()
        assert report["passed_sessions"] > 0

    def test_no_fail_flag_when_pass(self):
        """ผ่านทุก session → session_fail_flag = False"""
        sm = self._run_one_day_pass()
        report = sm.compliance_report()
        assert report["session_fail_flag"] is False

    def test_compliance_pct_range(self):
        """compliance_pct ต้องอยู่ระหว่าง 0–100"""
        sm = self._run_one_day_pass()
        report = sm.compliance_report()
        assert 0.0 <= report["compliance_pct"] <= 100.0

    def test_all_details_is_list_of_dicts(self):
        """all_details ต้องเป็น list ของ dict"""
        sm = self._run_one_day_pass()
        report = sm.compliance_report()
        assert isinstance(report["all_details"], list)
        for item in report["all_details"]:
            assert isinstance(item, dict)

    def test_all_details_have_required_keys(self):
        """แต่ละ item ใน all_details ต้องมี keys ครบ"""
        sm = self._run_one_day_pass()
        report = sm.compliance_report()
        required = {"date", "session_id", "trades", "min_trades", "passed", "no_data"}
        for item in report["all_details"]:
            assert required.issubset(item.keys())

    def test_fail_flag_when_insufficient_trades(self):
        """trade ไม่ครบ min_trades → session_fail_flag = True"""
        sm = _sm()
        date = "2026-04-06"
        # process ทุก session แต่ไม่ trade เลย
        sm.process_candle(_ts(f"{date} 00:30"))    # LATE (เห็นแต่ไม่ trade)
        sm.process_candle(_ts(f"{date} 08:00"))    # MORN (เห็นแต่ไม่ trade)
        sm.process_candle(_ts(f"{date} 13:00"))    # AFTN
        sm.process_candle(_ts(f"{date} 19:00"))    # EVEN
        sm.finalize()
        report = sm.compliance_report()
        assert report["session_fail_flag"] is True
        assert report["failed_sessions"] > 0


# ══════════════════════════════════════════════
# SessionResult
# ══════════════════════════════════════════════

class TestSessionResult:
    """ทดสอบ SessionResult.to_dict()"""

    def test_to_dict_has_all_keys(self):
        """to_dict() ต้องมี keys ครบ"""
        result = SessionResult(
            date="2026-04-06",
            session_id="MORN",
            trades=2,
            min_trades=2,
            passed=True,
        )
        d = result.to_dict()
        assert set(d.keys()) == {"date", "session_id", "trades", "min_trades", "passed", "no_data"}

    def test_to_dict_values_correct(self):
        """to_dict() ต้องคืนค่าที่ถูกต้อง"""
        result = SessionResult(
            date="2026-04-06",
            session_id="AFTN",
            trades=1,
            min_trades=2,
            passed=False,
            no_data=False,
        )
        d = result.to_dict()
        assert d["trades"] == 1
        assert d["passed"] is False
        assert d["no_data"] is False


# ══════════════════════════════════════════════
# finalize — Edge Cases
# ══════════════════════════════════════════════

class TestFinalize:
    """ทดสอบ finalize() กรณีพิเศษ"""

    def test_finalize_before_any_candle_no_crash(self):
        """finalize() โดยไม่มี candle → ต้องไม่ crash"""
        sm = _sm()
        sm.finalize()  # ต้องไม่ raise

    def test_finalize_twice_no_duplicate(self):
        """finalize() 2 ครั้ง → ต้องไม่เพิ่ม session ซ้ำ"""
        sm = _sm()
        sm.process_candle(_ts("2026-04-06 09:00"))
        sm.finalize()
        count_first = len(sm._closed)
        sm.finalize()
        count_second = len(sm._closed)
        assert count_first == count_second