"""
test_database_robustness.py — Tests สำหรับ RunDatabase error handling

ครอบคลุม (ส่วนที่ test_database.py ยังไม่ได้ test):
  1. Connection pool exhaustion   — getconn() raise PoolError → caller ได้รับ exception
  2. execute() failure            — execute() raise → commit() ไม่ถูกเรียก
  3. commit() failure             — commit() raise → exception propagate
  4. NULL / None fields           — save_run/save_llm_log รับ None ได้โดยไม่ crash
  5. Large JSON                   — react_trace ขนาดใหญ่ → serialize ได้
  6. putconn() always called      — คืน connection กลับ pool แม้มี error
  7. get_run_detail NULL JSON fields — ไม่ parse None fields

Strategy: mock psycopg2 pool — ไม่ต้องมี PostgreSQL จริง
"""

import sys
import os
import json
import threading
import pytest
from unittest.mock import patch, MagicMock, call

# ── pre-mock dependencies ────────────────────────────────────────
if "psycopg2" not in sys.modules:
    _mock_pg = MagicMock()
    _mock_pg.extras.RealDictCursor = MagicMock()
    sys.modules["psycopg2"] = _mock_pg
    sys.modules["psycopg2.extras"] = _mock_pg.extras

if "psycopg2.pool" not in sys.modules:
    sys.modules["psycopg2.pool"] = MagicMock()

if "logs" not in sys.modules:
    sys.modules["logs"] = MagicMock()
    sys.modules["logs.logger_setup"] = MagicMock()

# force-load database.database submodule ก่อนใช้ patch
import database.database  # noqa: E402  — ต้องอยู่หลัง sys.modules mocks

pytestmark = pytest.mark.integration

# ══════════════════════════════════════════════════════════════════
# Mock Infrastructure (เหมือน test_database.py)
# ══════════════════════════════════════════════════════════════════


def _make_mock_cursor():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"id": 1}
    cursor.fetchall.return_value = []
    cursor.rowcount = 1
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _make_mock_conn(cursor=None):
    if cursor is None:
        cursor = _make_mock_cursor()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def mock_db():
    """สร้าง RunDatabase instance โดย mock pool"""
    cursor = _make_mock_cursor()
    conn = _make_mock_conn(cursor)

    mock_pool = MagicMock()
    mock_pool.getconn.return_value = conn
    mock_pool.putconn = MagicMock()
    mock_pool.closeall = MagicMock()

    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake:5432/test"}),
        patch("database.database.ThreadedConnectionPool", return_value=mock_pool),
        patch("database.database.sys_logger"),
    ):
        from database.database import RunDatabase

        db = RunDatabase()
        cursor.execute.reset_mock()
        conn.commit.reset_mock()
        yield db, cursor, conn, mock_pool


def _result(**overrides):
    base = {
        "signal": "BUY",
        "confidence": 0.85,
        "rationale": "Test",
        "entry_price": 45000,
        "stop_loss": 44700,
        "take_profit": 45450,
        "iterations_used": 3,
        "tool_calls_used": 1,
        "react_trace": [{"step": "THOUGHT_1"}],
    }
    base.update(overrides)
    return base


def _market():
    return {
        "market_data": {
            "spot_price_usd": {"price_usd_per_oz": 2350.0},
            "forex": {"usd_thb": 35.5},
            "thai_gold_thb": {"sell_price_thb": 45000},
        },
        "technical_indicators": {"rsi": {"value": 60.0}},
    }


# ══════════════════════════════════════════════════════════════════
# 1. Connection pool exhaustion
# ══════════════════════════════════════════════════════════════════


class TestConnectionPoolFailure:
    """getconn() fail → method ควร raise หรือ return gracefully"""

    def test_getconn_failure_propagates_on_save_run(self, mock_db):
        """pool.getconn() raise → save_run() ควร raise"""
        db, cursor, conn, mock_pool = mock_db
        mock_pool.getconn.side_effect = Exception("PoolError: connection exhausted")

        with pytest.raises(Exception, match="PoolError"):
            db.save_run(
                result=_result(),
                market_state=_market(),
                interval_tf="1h",
                provider="mock",
            )

    def test_getconn_failure_propagates_on_get_recent_runs(self, mock_db):
        """pool.getconn() raise → get_recent_runs() ควร raise"""
        db, _, _, mock_pool = mock_db
        mock_pool.getconn.side_effect = Exception("PoolError")

        with pytest.raises(Exception):
            db.get_recent_runs()

    def test_getconn_failure_propagates_on_delete_run(self, mock_db):
        """pool.getconn() raise → delete_run() ควร raise"""
        db, _, _, mock_pool = mock_db
        mock_pool.getconn.side_effect = Exception("PoolError")

        with pytest.raises(Exception):
            db.delete_run(run_id=1)


# ══════════════════════════════════════════════════════════════════
# 2. execute() failure
# ══════════════════════════════════════════════════════════════════


class TestExecuteFailure:
    """execute() raise → commit() ไม่ถูกเรียก"""

    def test_execute_failure_skips_commit_on_save_run(self, mock_db):
        """execute() raise → commit() ไม่ถูกเรียก"""
        db, cursor, conn, mock_pool = mock_db
        cursor.execute.side_effect = Exception("DB error: column not found")

        with pytest.raises(Exception):
            db.save_run(
                result=_result(),
                market_state=_market(),
                interval_tf="1h",
                provider="mock",
            )

        conn.commit.assert_not_called()

    def test_execute_failure_skips_commit_on_save_llm_log(self, mock_db):
        """save_llm_log execute() fail → commit() ไม่ถูกเรียก"""
        db, cursor, conn, mock_pool = mock_db
        cursor.execute.side_effect = Exception("column type mismatch")

        with pytest.raises(Exception):
            db.save_llm_log(
                run_id=1,
                log_data={
                    "interval_tf": "1h",
                    "provider": "mock",
                    "signal": "BUY",
                    "confidence": 0.8,
                    "rationale": "test",
                },
            )

        conn.commit.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# 3. commit() failure
# ══════════════════════════════════════════════════════════════════


class TestCommitFailure:
    """commit() raise → exception propagate ออกมา"""

    def test_commit_failure_propagates_on_save_run(self, mock_db):
        """commit() raise → save_run() raise"""
        db, cursor, conn, _ = mock_db
        conn.commit.side_effect = Exception("Transaction rollback: deadlock")

        with pytest.raises(Exception, match="deadlock"):
            db.save_run(
                result=_result(),
                market_state=_market(),
                interval_tf="1h",
                provider="mock",
            )

    def test_commit_failure_propagates_on_save_llm_log(self, mock_db):
        """save_llm_log commit() fail → raise"""
        db, cursor, conn, _ = mock_db
        conn.commit.side_effect = Exception("commit failed")

        with pytest.raises(Exception):
            db.save_llm_log(
                run_id=1,
                log_data={
                    "interval_tf": "1h",
                    "provider": "mock",
                    "signal": "HOLD",
                    "confidence": 0.5,
                    "rationale": "r",
                },
            )

    def test_commit_failure_on_delete_run(self, mock_db):
        """delete_run() commit fail → raise"""
        db, cursor, conn, _ = mock_db
        conn.commit.side_effect = Exception("commit error")

        with pytest.raises(Exception):
            db.delete_run(run_id=42)


# ══════════════════════════════════════════════════════════════════
# 4. NULL / None fields
# ══════════════════════════════════════════════════════════════════


class TestNullFields:
    """None values ใน result → ไม่ crash เมื่อ save"""

    def test_save_run_with_none_react_trace(self, mock_db):
        """react_trace=None → serialize เป็น 'null' ได้"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {"id": 5}

        result = db.save_run(
            result=_result(react_trace=None),
            market_state=_market(),
            interval_tf="1h",
            provider="mock",
        )

        assert result == 5
        conn.commit.assert_called_once()

    def test_save_run_with_none_rationale(self, mock_db):
        """rationale=None → ไม่ crash"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {"id": 6}

        result = db.save_run(
            result=_result(rationale=None),
            market_state=_market(),
            interval_tf="1h",
            provider="mock",
        )

        assert result == 6

    def test_save_llm_log_with_none_trace_json(self, mock_db):
        """trace_json=None → serialize เป็น JSON null"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {"id": 7}

        result = db.save_llm_log(
            run_id=1,
            log_data={
                "interval_tf": "1h",
                "provider": "mock",
                "signal": "HOLD",
                "confidence": 0.5,
                "rationale": "r",
                "trace_json": None,
            },
        )

        assert result == 7

    def test_save_run_none_entry_price(self, mock_db):
        """entry_price=None → ไม่ crash"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {"id": 8}

        result = db.save_run(
            result=_result(entry_price=None),
            market_state=_market(),
            interval_tf="1h",
            provider="mock",
        )

        assert result == 8


# ══════════════════════════════════════════════════════════════════
# 5. Large JSON fields
# ══════════════════════════════════════════════════════════════════


class TestLargeJSONFields:
    """JSON field ขนาดใหญ่ → serialize ได้โดยไม่ crash"""

    def test_large_react_trace_serializes(self, mock_db):
        """react_trace ที่มี 100 steps → serialize เป็น JSON string"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {"id": 10}

        large_trace = [
            {
                "step": f"THOUGHT_{i}",
                "action": "CALL_TOOL",
                "tool": "get_news",
                "response": "x" * 500,  # text ยาวต่อ step
            }
            for i in range(100)
        ]

        result = db.save_run(
            result=_result(react_trace=large_trace),
            market_state=_market(),
            interval_tf="1h",
            provider="mock",
        )

        assert result == 10
        conn.commit.assert_called_once()

        # ตรวจว่า params ที่ส่งไป execute มี react_trace เป็น string
        execute_call_args = cursor.execute.call_args
        assert execute_call_args is not None
        params = execute_call_args.args[1] if len(execute_call_args.args) > 1 else execute_call_args[1]
        # หา react_trace ใน params (เป็น JSON string)
        react_trace_param = next(
            (p for p in params if isinstance(p, str) and "THOUGHT_0" in p), None
        )
        assert react_trace_param is not None

    def test_large_market_snapshot_serializes(self, mock_db):
        """market_state ที่มี nested data ลึก → serialize ได้"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {"id": 11}

        large_market = {
            "market_data": {
                "spot_price_usd": {"price_usd_per_oz": 2350.0},
                "forex": {"usd_thb": 35.5},
                "thai_gold_thb": {"sell_price_thb": 45000},
                "news": [
                    {"title": f"News {i}", "sentiment": 0.5}
                    for i in range(50)  # 50 ข่าว
                ],
            },
            "technical_indicators": {"rsi": {"value": 60.0}},
        }

        result = db.save_run(
            result=_result(),
            market_state=large_market,
            interval_tf="1h",
            provider="mock",
        )

        assert result == 11


# ══════════════════════════════════════════════════════════════════
# 6. putconn() always called (connection คืน pool แม้มี error)
# ══════════════════════════════════════════════════════════════════


class TestConnectionAlwaysReturned:
    """putconn() ต้องถูกเรียกเสมอ แม้เกิด error"""

    def test_putconn_called_after_successful_save_run(self, mock_db):
        """save_run สำเร็จ → putconn() ถูกเรียกอย่างน้อย 1 ครั้ง"""
        db, cursor, conn, mock_pool = mock_db
        cursor.fetchone.return_value = {"id": 1}
        mock_pool.putconn.reset_mock()

        db.save_run(
            result=_result(),
            market_state=_market(),
            interval_tf="1h",
            provider="mock",
        )

        mock_pool.putconn.assert_called_with(conn)

    def test_putconn_called_after_get_recent_runs(self, mock_db):
        """get_recent_runs() → putconn() ถูกเรียกอย่างน้อย 1 ครั้ง"""
        db, cursor, conn, mock_pool = mock_db
        cursor.fetchall.return_value = []
        mock_pool.putconn.reset_mock()

        db.get_recent_runs()

        mock_pool.putconn.assert_called_with(conn)


# ══════════════════════════════════════════════════════════════════
# 7. get_run_detail NULL JSON fields
# ══════════════════════════════════════════════════════════════════


class TestGetRunDetailNullFields:
    """get_run_detail คืน dict ที่มี None fields → ไม่ parse None"""

    def test_none_react_trace_not_parsed(self, mock_db):
        """react_trace=None → คืน None ไม่ใช่ {} หรือ []"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {
            "id": 1,
            "react_trace": None,
            "market_snapshot": None,
        }

        result = db.get_run_detail(run_id=1)

        assert result is not None
        assert result["react_trace"] is None

    def test_none_market_snapshot_not_parsed(self, mock_db):
        """market_snapshot=None → คืน None"""
        db, cursor, conn, _ = mock_db
        cursor.fetchone.return_value = {
            "id": 1,
            "react_trace": None,
            "market_snapshot": None,
        }

        result = db.get_run_detail(run_id=1)

        assert result["market_snapshot"] is None

    def test_valid_json_react_trace_parsed(self, mock_db):
        """react_trace เป็น JSON string → parse เป็น list"""
        db, cursor, conn, _ = mock_db
        trace = [{"step": "THOUGHT_1", "action": "FINAL_DECISION"}]
        cursor.fetchone.return_value = {
            "id": 1,
            "react_trace": json.dumps(trace),
            "market_snapshot": None,
        }

        result = db.get_run_detail(run_id=1)

        assert isinstance(result["react_trace"], list)
        assert result["react_trace"][0]["step"] == "THOUGHT_1"
