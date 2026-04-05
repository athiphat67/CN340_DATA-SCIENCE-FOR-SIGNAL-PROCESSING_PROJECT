"""
backtest/engine/session_manager.py
══════════════════════════════════════════════════════════════════════
TradingSessionManager — ชั่วโมงซื้อขาย ออม NOW จริง (อัปเดต 2026)

[FIX v2.1] แก้ session window ให้ตรงกับ ออม NOW จริง:
  จันทร์–ศุกร์: 06:15 – 02:00 น. (เช้าวันถัดไป)
  เสาร์–อาทิตย์: 09:30 – 17:30 น.
  Dead zone: 02:01 – 06:14 (ตลาดปิด)

โครงสร้าง session (เพื่อ compliance tracking):
  Session LATE  00:00–02:00   ← ต่อเนื่องจากคืนก่อน
  Session MORN  06:15–11:59   ← เช้า
  Session AFTN  12:00–17:59   ← บ่าย
  Session EVEN  18:00–23:59   ← เย็น-ดึก
  Session E     09:30–17:30   ← เสาร์-อาทิตย์ (เหมือนเดิม)

ข้อสำคัญ:
  - 02:00 เป็นเวลาปิด → 02:00:00 ถือว่านอก session แล้ว
  - 06:15 เป็นเวลาเปิด → 06:14:xx ยังนอก session
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Session Configuration
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TimeRange:
    start: time   # inclusive
    end:   time   # inclusive

    def contains(self, t: time) -> bool:
        return self.start <= t <= self.end


@dataclass(frozen=True)
class SessionDef:
    id:          str
    ranges:      Tuple[TimeRange, ...]
    min_trades:  int
    description: str

    def contains(self, t: time) -> bool:
        return any(r.contains(t) for r in self.ranges)

    @property
    def last_end(self) -> time:
        return max(r.end for r in self.ranges)


# ── [FIX v2.1] ออม NOW sessions จริง ─────────────────────────────
# จันทร์–ศุกร์: 06:15 → 02:00 น. (ข้ามคืน)
# เราแบ่งเป็น 4 session เพื่อ compliance tracking:
#   LATE : 00:00–01:59  (ส่วนที่ข้ามคืนมาจากคืนก่อน)
#   MORN : 06:15–11:59
#   AFTN : 12:00–17:59
#   EVEN : 18:00–23:59
# Dead zone : 02:00–06:14 → can_execute=False

WEEKDAY_SESSIONS: Tuple[SessionDef, ...] = (
    SessionDef(
        id="LATE",
        ranges=(TimeRange(time(0, 0), time(1, 59)),),
        min_trades=1,
        description="00:00–01:59 (ต่อเนื่องจากเย็นวันก่อน)",
    ),
    SessionDef(
        id="MORN",
        ranges=(TimeRange(time(6, 15), time(11, 59)),),  # [FIX] 06:15 ไม่ใช่ 06:00
        min_trades=2,
        description="06:15–11:59",
    ),
    SessionDef(
        id="AFTN",
        ranges=(TimeRange(time(12, 0), time(17, 59)),),
        min_trades=2,
        description="12:00–17:59",
    ),
    SessionDef(
        id="EVEN",
        ranges=(TimeRange(time(18, 0), time(23, 59)),),
        min_trades=2,
        description="18:00–23:59",
    ),
)

WEEKEND_SESSIONS: Tuple[SessionDef, ...] = (
    SessionDef(
        id="E",
        ranges=(TimeRange(time(9, 30), time(17, 30)),),
        min_trades=2,
        description="09:30–17:30",
    ),
)

# Dead zone weekday: 02:00–06:14
_DEAD_START = time(2, 0)
_DEAD_END   = time(6, 14)


# ══════════════════════════════════════════════════════════════════
# Return types
# ══════════════════════════════════════════════════════════════════

@dataclass
class SessionInfo:
    session_id:  Optional[str]
    can_execute: bool
    is_outside:  bool
    description: str = ""

    @property
    def label(self) -> str:
        if self.session_id:
            return f"[{self.session_id}]"
        return "[DEAD]"


@dataclass
class SessionResult:
    date:       str
    session_id: str
    trades:     int
    min_trades: int
    passed:     bool
    no_data:    bool = False

    def to_dict(self) -> dict:
        return {
            "date":       self.date,
            "session_id": self.session_id,
            "trades":     self.trades,
            "min_trades": self.min_trades,
            "passed":     self.passed,
            "no_data":    self.no_data,
        }


# ══════════════════════════════════════════════════════════════════
# TradingSessionManager
# ══════════════════════════════════════════════════════════════════

class TradingSessionManager:
    """
    Session manager ที่ตรง ออม NOW จริง
    [FIX v2.1]: เปิด 06:15 (ไม่ใช่ 06:00) | Dead zone 02:00–06:14
    """

    def __init__(self):
        self._trades:      Dict[Tuple[str, str], int]  = {}
        self._seen:        Dict[Tuple[str, str], bool] = {}
        self._closed:      List[SessionResult]         = []
        self._closed_keys: set                         = set()
        self._last_ts:     Optional[pd.Timestamp]      = None

        logger.info("✓ TradingSessionManager v2.1 (ออม NOW hours)")
        logger.info("  จันทร์–ศุกร์: 00:00–01:59 + 06:15–23:59")
        logger.info("  Dead zone: 02:00–06:14 (ออม NOW ปิด)")
        logger.info("  เสาร์–อาทิตย์: 09:30–17:30")

    # ── Public API ───────────────────────────────────────────────

    def process_candle(self, ts: pd.Timestamp) -> SessionInfo:
        if self._last_ts is not None:
            self._close_expired_sessions(ts)

        self._last_ts = ts
        session_def   = self._find_session(ts)

        if session_def:
            date_str = ts.strftime("%Y-%m-%d")
            key = (date_str, session_def.id)
            self._seen[key] = True
            return SessionInfo(
                session_id=session_def.id,
                can_execute=True,
                is_outside=False,
                description=session_def.description,
            )
        else:
            t = ts.time()
            if _DEAD_START <= t <= _DEAD_END:
                desc = f"dead zone 02:00–06:14 (ออม NOW ปิด)"
            else:
                desc = "outside session"
            return SessionInfo(
                session_id=None,
                can_execute=False,
                is_outside=True,
                description=desc,
            )

    def record_trade(self, ts: pd.Timestamp):
        session_def = self._find_session(ts)
        if session_def is None:
            logger.warning(f"record_trade outside session at {ts}")
            return

        date_str = ts.strftime("%Y-%m-%d")
        key      = (date_str, session_def.id)
        self._trades[key] = self._trades.get(key, 0) + 1
        logger.debug(
            f"  📌 Trade: {ts.strftime('%H:%M')} [{session_def.id}] "
            f"{self._trades[key]}/{session_def.min_trades}"
        )

    def finalize(self):
        if self._last_ts is None:
            return

        ts       = self._last_ts
        dow      = ts.dayofweek
        sessions = WEEKDAY_SESSIONS if dow < 5 else WEEKEND_SESSIONS
        date_str = ts.strftime("%Y-%m-%d")

        for sdef in sessions:
            key = (date_str, sdef.id)
            if key not in self._closed_keys:
                self._close_session(date_str, sdef)

        logger.info(f"✓ SessionManager finalized | {len(self._closed)} sessions")

    def compliance_report(self) -> dict:
        if not self._closed:
            return {
                "total_sessions":    0,
                "passed_sessions":   0,
                "failed_sessions":   0,
                "no_data_sessions":  0,
                "compliance_pct":    0.0,
                "session_fail_flag": False,
                "failed_details":    [],
                "all_details":       [],
            }

        total    = len(self._closed)
        no_data  = sum(1 for s in self._closed if s.no_data)
        passed   = sum(1 for s in self._closed if s.passed and not s.no_data)
        failed   = sum(1 for s in self._closed if not s.passed and not s.no_data)
        eligible = total - no_data

        compliance_pct = round(passed / eligible * 100, 2) if eligible > 0 else 0.0

        return {
            "total_sessions":    total,
            "passed_sessions":   passed,
            "failed_sessions":   failed,
            "no_data_sessions":  no_data,
            "compliance_pct":    compliance_pct,
            "session_fail_flag": failed > 0,
            "failed_details":    [s.to_dict() for s in self._closed if not s.passed and not s.no_data],
            "all_details":       [s.to_dict() for s in self._closed],
        }

    # ── Internal ─────────────────────────────────────────────────

    def _find_session(self, ts: pd.Timestamp) -> Optional[SessionDef]:
        dow      = ts.dayofweek
        t        = ts.time()
        sessions = WEEKDAY_SESSIONS if dow < 5 else WEEKEND_SESSIONS
        for sdef in sessions:
            if sdef.contains(t):
                return sdef
        return None

    def _close_expired_sessions(self, current_ts: pd.Timestamp):
        if self._last_ts is None:
            return

        prev_ts   = self._last_ts
        prev_date = prev_ts.strftime("%Y-%m-%d")
        curr_date = current_ts.strftime("%Y-%m-%d")
        curr_time = current_ts.time()
        prev_dow  = prev_ts.dayofweek

        prev_sessions = WEEKDAY_SESSIONS if prev_dow < 5 else WEEKEND_SESSIONS

        for sdef in prev_sessions:
            key = (prev_date, sdef.id)
            if key in self._closed_keys:
                continue

            last_end    = sdef.last_end
            end_minute  = last_end.hour * 60 + last_end.minute
            curr_minute = curr_time.hour * 60 + curr_time.minute

            if curr_date > prev_date:
                self._close_session(prev_date, sdef)
            elif curr_date == prev_date and curr_minute > end_minute:
                self._close_session(prev_date, sdef)

    def _close_session(self, date_str: str, sdef: SessionDef):
        key = (date_str, sdef.id)
        if key in self._closed_keys:
            return

        self._closed_keys.add(key)

        trades  = self._trades.get(key, 0)
        seen    = self._seen.get(key, False)
        no_data = not seen
        passed  = no_data or (trades >= sdef.min_trades)

        result = SessionResult(
            date=date_str,
            session_id=sdef.id,
            trades=trades,
            min_trades=sdef.min_trades,
            passed=passed,
            no_data=no_data,
        )
        self._closed.append(result)

        if no_data:
            logger.debug(f"  📋 [{sdef.id}] {date_str}: NO DATA")
        elif passed:
            logger.info(f"  ✅ [{sdef.id}] {date_str}: PASS ({trades}/{sdef.min_trades})")
        else:
            logger.warning(f"  ❌ [{sdef.id}] {date_str}: FAIL ({trades}/{sdef.min_trades})")


# ── Self-test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    print("=" * 60)
    print("SessionManager v2.1 — ออม NOW Hours Self Test")
    print("=" * 60)

    sm = TradingSessionManager()

    tests = [
        ("2026-04-06 00:30", "LATE",  True,  "จันทร์ ดึก — ต้องเปิด"),
        ("2026-04-06 01:59", "LATE",  True,  "จันทร์ 01:59 — ยังเปิด"),
        ("2026-04-06 02:00", None,    False, "จันทร์ 02:00 — ปิดพอดี!"),
        ("2026-04-06 02:01", None,    False, "จันทร์ 02:01 — dead zone"),
        ("2026-04-06 04:30", None,    False, "จันทร์ กลางดึก — dead zone"),
        ("2026-04-06 06:14", None,    False, "จันทร์ 06:14 — ยังปิด"),
        ("2026-04-06 06:15", "MORN",  True,  "จันทร์ 06:15 — เปิดพอดี!"),
        ("2026-04-06 06:16", "MORN",  True,  "จันทร์ 06:16 — เปิดแล้ว"),
        ("2026-04-06 11:59", "MORN",  True,  "จันทร์ สาย — เปิด"),
        ("2026-04-06 12:00", "AFTN",  True,  "จันทร์ บ่าย — เปิด"),
        ("2026-04-06 18:00", "EVEN",  True,  "จันทร์ เย็น — เปิด"),
        ("2026-04-06 23:59", "EVEN",  True,  "จันทร์ ดึก — เปิด"),
        ("2026-04-11 09:29", None,    False, "เสาร์ 09:29 — ยังปิด"),
        ("2026-04-11 09:30", "E",     True,  "เสาร์ 09:30 — เปิดพอดี!"),
        ("2026-04-11 17:30", "E",     True,  "เสาร์ 17:30 — ยังเปิด"),
        ("2026-04-11 17:31", None,    False, "เสาร์ 17:31 — ปิดแล้ว"),
    ]

    all_pass = True
    for ts_str, exp_session, exp_exec, label in tests:
        ts   = pd.Timestamp(ts_str)
        info = sm._find_session(ts)
        got_session = info.id if info else None
        got_exec    = info is not None

        ok = (got_session == exp_session) and (got_exec == exp_exec)
        icon = "✓" if ok else "✗"
        if not ok:
            all_pass = False
        print(f"  {icon} {ts_str} [{got_session or 'DEAD':4}] exec={got_exec} — {label}")

    print()
    if all_pass:
        print("✅ ทุก test ผ่าน!")
    else:
        print("❌ มี test ที่ไม่ผ่าน")
    print("=" * 60)