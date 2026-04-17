"""
test_database.py — Pytest สำหรับทดสอบ RunDatabase

Strategy: Mock psycopg2 (I/O boundary)
- RunDatabase เชื่อมต่อ PostgreSQL จริง → ต้อง mock psycopg2.connect
- Logic ที่ test: SQL params ถูกต้อง, data extraction, JSON serialize, defaults
- ไม่ต้องมี PostgreSQL running

Mock pattern:
  mock psycopg2.connect → return mock connection
  mock connection.cursor → return mock cursor
  mock cursor.execute    → capture SQL + params
  mock cursor.fetchone   → return fake row
  mock cursor.fetchall   → return fake rows

ครอบคลุม:
  1. __init__  — ต้องมี DATABASE_URL, เรียก _init_db, migrations
  2. save_run  — params ถูก, market data extraction, rationale fallback, return id
  3. get_recent_runs  — return list[dict], ORDER BY + LIMIT
  4. get_run_detail   — return dict, JSON parsed, not-found, bad JSON
  5. get_signal_stats — aggregation, None→0 defaults
  6. delete_run       — return bool, DELETE SQL
  7. save_llm_log     — params ถูก, trace_json serialized, defaults, is_fallback
  8. save_llm_logs_batch — หลาย logs, empty, partial failure
  9. get_llm_logs_for_run — return list, trace_json parsed, bad JSON
  10. get_recent_llm_logs — return list, JOIN SQL, limit
  11. save_portfolio / get_portfolio — UPSERT, defaults, missing keys, error
  12. Error handling — DB connection errors, commit verification
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime

# ── Module-level mocks ──────────────────────────────────────────
# psycopg2 และ logs อาจไม่ได้ install ใน test environment
# mock ก่อน import database.database
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


# ══════════════════════════════════════════════════════════════════
# Mock Infrastructure
# ══════════════════════════════════════════════════════════════════


def _make_mock_cursor():
    """สร้าง mock cursor ที่ track execute calls"""
    cursor = MagicMock()
    cursor.fetchone.return_value = {"id": 1}
    cursor.fetchall.return_value = []
    cursor.rowcount = 1
    # context manager support
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _make_mock_conn(cursor=None):
    """สร้าง mock connection ที่คืน mock cursor"""
    if cursor is None:
        cursor = _make_mock_cursor()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    # context manager support
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def mock_db():
    """
    สร้าง RunDatabase instance โดย mock psycopg2.connect ทั้งหมด
    return (db, cursor, conn) เพื่อให้ test ตรวจ cursor.execute calls ได้
    """
    cursor = _make_mock_cursor()
    conn = _make_mock_conn(cursor)

    mock_pool = MagicMock()
    mock_pool.getconn.return_value = conn

    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake:5432/test"}),
        patch("database.database.ThreadedConnectionPool", return_value=mock_pool),
        patch("database.database.sys_logger"),
    ):
        from database.database import RunDatabase

        db = RunDatabase()

        # reset execute call history หลัง _init_db
        cursor.execute.reset_mock()
        conn.commit.reset_mock()
        yield db, cursor, conn


# ══════════════════════════════════════════════════════════════════
# Helper — สร้าง input data ที่สมจริง
# ══════════════════════════════════════════════════════════════════


def _full_result(**overrides):
    """สร้าง result dict ที่สมจริงสำหรับ save_run"""
    data = {
        "signal": "BUY",
        "confidence": 0.85,
        "rationale": "Strong uptrend with RSI support",
        "entry_price": 45000,
        "stop_loss": 44700,
        "take_profit": 45450,
        "iterations_used": 3,
        "tool_calls_used": 1,
        "react_trace": [{"step": "THOUGHT_1"}, {"step": "THOUGHT_FINAL"}],
    }
    data.update(overrides)
    return data


def _full_market_state(**overrides):
    """สร้าง market_state dict ที่สมจริงสำหรับ save_run"""
    data = {
        "market_data": {
            "spot_price_usd": {"price_usd_per_oz": 2350.50},
            "forex": {"usd_thb": 35.5},
            "thai_gold_thb": {"sell_price_thb": 45000},
        },
        "technical_indicators": {
            "rsi": {"value": 65.3},
            "macd": {"macd_line": 0.5, "signal_line": 0.3},
            "trend": {"trend": "uptrend"},
        },
    }
    data.update(overrides)
    return data


# ══════════════════════════════════════════════════════════════════
# 1. __init__ — DATABASE_URL, _init_db, migrations
# ══════════════════════════════════════════════════════════════════


class TestInit:
    def test_missing_database_url_raises(self):
        """ไม่มี DATABASE_URL → ValueError"""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with pytest.raises(ValueError, match="DATABASE_URL"):
                from database.database import RunDatabase

                RunDatabase()

    def test_init_creates_tables(self):
        """__init__ ต้องเรียก CREATE TABLE"""
        cursor = _make_mock_cursor()
        conn = _make_mock_conn(cursor)

        mock_pool = MagicMock()
        mock_pool.getconn.return_value = conn

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake:5432/test"}),
            patch("database.database.ThreadedConnectionPool", return_value=mock_pool),
            patch("database.database.sys_logger"),
        ):
            from database.database import RunDatabase

            RunDatabase()

        # ต้องเรียก execute หลายครั้ง (CREATE TABLE + migrations)
        assert cursor.execute.call_count >= 3

    def test_init_calls_commit(self):
        """__init__ ต้องเรียก conn.commit() หลัง CREATE TABLE"""
        cursor = _make_mock_cursor()
        conn = _make_mock_conn(cursor)

        mock_pool = MagicMock()
        mock_pool.getconn.return_value = conn

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake:5432/test"}),
            patch("database.database.ThreadedConnectionPool", return_value=mock_pool),
            patch("database.database.sys_logger"),
        ):
            from database.database import RunDatabase

            RunDatabase()

        conn.commit.assert_called()

    def test_init_runs_migrations(self):
        """__init__ ต้องรัน ALTER TABLE migrations"""
        cursor = _make_mock_cursor()
        conn = _make_mock_conn(cursor)

        mock_pool = MagicMock()
        mock_pool.getconn.return_value = conn

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake:5432/test"}),
            patch("database.database.ThreadedConnectionPool", return_value=mock_pool),
            patch("database.database.sys_logger"),
        ):
            from database.database import RunDatabase

            RunDatabase()

        # รวบรวม SQL ทุกครั้งที่เรียก execute
        all_sql = [str(c[0][0]) for c in cursor.execute.call_args_list if c[0]]
        alter_calls = [s for s in all_sql if "ALTER TABLE" in s]
        # ต้องมีอย่างน้อย 5 migrations (entry_price_thb, stop_loss_thb, etc.)
        assert len(alter_calls) >= 5

    def test_db_url_stored(self):
        """db_url ต้องถูกเก็บไว้ใน instance"""
        cursor = _make_mock_cursor()
        conn = _make_mock_conn(cursor)
        test_url = "postgresql://user:pass@host:5432/mydb"

        with (
            patch.dict(os.environ, {"DATABASE_URL": test_url}),
            patch("database.database.psycopg2.connect", return_value=conn),
            patch("database.database.sys_logger"),
        ):
            from database.database import RunDatabase

            db = RunDatabase()

        assert db.db_url == test_url

    def test_dsn_passed_to_connect(self):
        """DATABASE_URL ต้องถูกส่งไป ThreadedConnectionPool(dsn=...)"""
        cursor = _make_mock_cursor()
        conn = _make_mock_conn(cursor)

        mock_pool = MagicMock()
        mock_pool.getconn.return_value = conn
        mock_pool_cls = MagicMock(return_value=mock_pool)

        test_url = "postgresql://user:pass@localhost:5432/mydb"
        with (
            patch.dict(os.environ, {"DATABASE_URL": test_url}),
            patch("database.database.ThreadedConnectionPool", mock_pool_cls),
            patch("database.database.sys_logger"),
        ):
            from database.database import RunDatabase

            RunDatabase()

        # check that mock_pool_cls was called with dsn=test_url
        assert mock_pool_cls.call_args[1].get("dsn") == test_url


# ══════════════════════════════════════════════════════════════════
# 2. save_run — params, market data extraction, rationale fallback
# ══════════════════════════════════════════════════════════════════


class TestSaveRun:
    def test_returns_new_id(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 42}

        new_id = db.save_run(
            "gemini", _full_result(), _full_market_state(), "1h", "short"
        )
        assert new_id == 42

    def test_execute_called_with_insert(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_run("gemini", {"signal": "HOLD"}, {}, "5m", "day")

        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO runs" in sql
        assert "RETURNING id" in sql

    def test_params_include_signal_and_confidence(self, mock_db):
        """params tuple ต้องมี provider, signal, confidence ตรง"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_run("claude", {"signal": "SELL", "confidence": 0.9}, {}, "1h", "week")

        params = cursor.execute.call_args[0][1]
        assert "claude" in params
        assert "SELL" in params
        assert 0.9 in params

    def test_market_data_extracted_correctly(self, mock_db):
        """gold_price_usd, usd_thb, gold_price_thb, rsi, macd ต้องถูกดึงจาก market_state"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        market = _full_market_state()
        db.save_run("gemini", _full_result(), market, "1h", "day")

        params = cursor.execute.call_args[0][1]
        # gold_price_usd (spot_price_usd.price_usd_per_oz)
        assert 2350.50 in params
        # usd_thb
        assert 35.5 in params
        # gold_price_thb (thai_gold_thb.sell_price_thb)
        assert 45000 in params
        # rsi
        assert 65.3 in params
        # macd_line
        assert 0.5 in params
        # signal_line
        assert 0.3 in params

    def test_trend_extracted(self, mock_db):
        """trend direction ต้องอยู่ใน params"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_run("gemini", _full_result(), _full_market_state(), "1h", "day")

        params = cursor.execute.call_args[0][1]
        assert "uptrend" in params

    def test_react_trace_json_serialized(self, mock_db):
        """react_trace ต้องถูก serialize เป็น JSON string"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        trace = [{"step": "THOUGHT_1", "response": {"signal": "BUY"}}]
        db.save_run("gemini", {"react_trace": trace}, {}, "1h", "day")

        params = cursor.execute.call_args[0][1]
        json_params = [p for p in params if isinstance(p, str) and "THOUGHT_1" in p]
        assert len(json_params) >= 1
        # ต้อง parse กลับได้
        parsed = json.loads(json_params[0])
        assert parsed[0]["step"] == "THOUGHT_1"

    def test_market_snapshot_json_serialized(self, mock_db):
        """market_snapshot ต้องถูก serialize เป็น JSON พร้อม market_data + indicators"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        market = _full_market_state()
        db.save_run("gemini", _full_result(), market, "1h", "day")

        params = cursor.execute.call_args[0][1]
        # หา param ที่เป็น JSON snapshot (มี market_data key)
        json_params = [p for p in params if isinstance(p, str) and "market_data" in p]
        assert len(json_params) >= 1
        parsed = json.loads(json_params[0])
        assert "market_data" in parsed
        assert "technical_indicators" in parsed

    def test_rationale_fallback_voting_breakdown(self, mock_db):
        """rationale ว่าง + มี voting_breakdown → ใช้ weighted voting result"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        result = {
            "signal": "BUY",
            "confidence": 0.8,
            "rationale": "",  # ว่าง!
            "voting_breakdown": {
                "BUY": {"count": 2, "weighted_score": 0.7},
            },
        }
        db.save_run("gemini", result, {}, "1h", "day")

        params = cursor.execute.call_args[0][1]
        # ต้องมี fallback rationale ที่มีคำว่า voting
        rationale_candidates = [
            p for p in params if isinstance(p, str) and "voting" in p.lower()
        ]
        assert len(rationale_candidates) >= 1

    def test_empty_market_state_uses_none(self, mock_db):
        """market_state ว่าง → ค่า market data เป็น None ไม่ crash"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        new_id = db.save_run("gemini", {"signal": "HOLD"}, {}, "1h", "day")
        assert new_id == 1

    def test_entry_price_thb_duplicated(self, mock_db):
        """entry_price_thb alias ต้องเท่ากับ entry_price (THB/gram จาก LLM)"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        result = _full_result(entry_price=45000, stop_loss=44700, take_profit=45450)
        db.save_run("gemini", result, {}, "1h", "day")

        params = cursor.execute.call_args[0][1]
        # entry_price ต้องปรากฏ 2 ครั้ง (entry_price + entry_price_thb)
        count_entry = sum(1 for p in params if p == 45000)
        assert count_entry >= 2  # entry_price + entry_price_thb

    def test_commit_called_after_insert(self, mock_db):
        """save_run ต้องเรียก conn.commit()"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_run("gemini", _full_result(), {}, "1h", "day")
        conn.commit.assert_called()


# ══════════════════════════════════════════════════════════════════
# 3. get_recent_runs
# ══════════════════════════════════════════════════════════════════


class TestGetRecentRuns:
    def test_returns_list_of_dicts(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = [
            {"id": 1, "signal": "BUY", "confidence": 0.8},
            {"id": 2, "signal": "HOLD", "confidence": 0.5},
        ]
        rows = db.get_recent_runs(limit=10)
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert rows[0]["signal"] == "BUY"

    def test_empty_returns_empty_list(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        assert db.get_recent_runs() == []

    def test_query_has_order_and_limit(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_recent_runs(limit=25)

        sql = cursor.execute.call_args[0][0]
        assert "ORDER BY" in sql
        assert "LIMIT" in sql

    def test_limit_passed_as_param(self, mock_db):
        """limit ต้องส่งเป็น SQL parameter (ป้องกัน SQL injection)"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_recent_runs(limit=25)

        params = cursor.execute.call_args[0][1]
        assert 25 in params

    def test_returns_plain_dicts(self, mock_db):
        """ทุก row ต้องเป็น plain dict (ไม่ใช่ RealDictRow)"""
        db, cursor, conn = mock_db
        mock_row = MagicMock()
        mock_row.__iter__ = MagicMock(return_value=iter([("id", 1)]))
        # dict(mock_row) จะ return dict
        cursor.fetchall.return_value = [{"id": 1, "signal": "BUY"}]
        rows = db.get_recent_runs()
        assert all(isinstance(r, dict) for r in rows)


# ══════════════════════════════════════════════════════════════════
# 4. get_run_detail
# ══════════════════════════════════════════════════════════════════


class TestGetRunDetail:
    def test_returns_dict_with_parsed_json(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "id": 5,
            "signal": "BUY",
            "react_trace": json.dumps([{"step": "THOUGHT_FINAL"}]),
            "market_snapshot": json.dumps({"rsi": 65}),
        }
        detail = db.get_run_detail(5)
        assert detail["id"] == 5
        # react_trace ต้องถูก parse เป็น list
        assert isinstance(detail["react_trace"], list)
        assert detail["react_trace"][0]["step"] == "THOUGHT_FINAL"
        # market_snapshot ต้องถูก parse เป็น dict
        assert isinstance(detail["market_snapshot"], dict)

    def test_not_found_returns_none(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = None
        assert db.get_run_detail(999) is None

    def test_bad_json_stays_string(self, mock_db):
        """JSON parse ไม่ได้ → เก็บเป็น string"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "id": 1,
            "react_trace": "NOT_JSON{{{",
            "market_snapshot": None,
        }
        detail = db.get_run_detail(1)
        assert isinstance(detail["react_trace"], str)

    def test_none_json_fields_not_parsed(self, mock_db):
        """react_trace=None, market_snapshot=None → ไม่ error"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "id": 1,
            "react_trace": None,
            "market_snapshot": None,
        }
        detail = db.get_run_detail(1)
        assert detail["react_trace"] is None
        assert detail["market_snapshot"] is None

    def test_query_uses_param_for_id(self, mock_db):
        """run_id ต้องส่งเป็น SQL parameter (ไม่ใช่ string format)"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "id": 7,
            "react_trace": None,
            "market_snapshot": None,
        }
        db.get_run_detail(7)

        params = cursor.execute.call_args[0][1]
        assert 7 in params


# ══════════════════════════════════════════════════════════════════
# 5. get_signal_stats
# ══════════════════════════════════════════════════════════════════


class TestGetSignalStats:
    def test_returns_aggregated(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "total": 100,
            "buy_count": 30,
            "sell_count": 20,
            "hold_count": 50,
            "avg_confidence": 0.72,
            "avg_price": 45123.45,
        }
        stats = db.get_signal_stats()
        assert stats["total"] == 100
        assert stats["buy_count"] == 30
        assert stats["sell_count"] == 20
        assert stats["hold_count"] == 50
        assert stats["avg_confidence"] == 0.72

    def test_none_values_default_to_zero(self, mock_db):
        """DB คืน None → default 0"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "total": None,
            "buy_count": None,
            "sell_count": None,
            "hold_count": None,
            "avg_confidence": None,
            "avg_price": None,
        }
        stats = db.get_signal_stats()
        assert stats["total"] == 0
        assert stats["buy_count"] == 0
        assert stats["sell_count"] == 0
        assert stats["hold_count"] == 0
        assert stats["avg_confidence"] == 0
        assert stats["avg_price"] == 0

    def test_avg_confidence_rounded(self, mock_db):
        """avg_confidence ต้อง round 3 ตำแหน่ง"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "total": 10,
            "buy_count": 5,
            "sell_count": 3,
            "hold_count": 2,
            "avg_confidence": 0.723456789,
            "avg_price": 45123.456,
        }
        stats = db.get_signal_stats()
        assert stats["avg_confidence"] == 0.723
        assert stats["avg_price"] == 45123.46

    def test_query_has_aggregation_functions(self, mock_db):
        """SQL ต้องมี COUNT, SUM, AVG"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "total": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "avg_confidence": None,
            "avg_price": None,
        }
        db.get_signal_stats()

        sql = cursor.execute.call_args[0][0]
        assert "COUNT" in sql
        assert "SUM" in sql
        assert "AVG" in sql


# ══════════════════════════════════════════════════════════════════
# 6. delete_run
# ══════════════════════════════════════════════════════════════════


class TestDeleteRun:
    def test_returns_true_when_deleted(self, mock_db):
        db, cursor, conn = mock_db
        cursor.rowcount = 1
        assert db.delete_run(5) is True

    def test_returns_false_when_not_found(self, mock_db):
        db, cursor, conn = mock_db
        cursor.rowcount = 0
        assert db.delete_run(999) is False

    def test_executes_delete_sql(self, mock_db):
        db, cursor, conn = mock_db
        db.delete_run(7)
        sql = cursor.execute.call_args[0][0]
        assert "DELETE FROM runs" in sql

    def test_delete_uses_param_for_id(self, mock_db):
        """run_id ต้องส่งเป็น SQL parameter"""
        db, cursor, conn = mock_db
        db.delete_run(42)
        params = cursor.execute.call_args[0][1]
        assert 42 in params

    def test_commit_called_after_delete(self, mock_db):
        """delete ต้องเรียก conn.commit()"""
        db, cursor, conn = mock_db
        db.delete_run(5)
        conn.commit.assert_called()


# ══════════════════════════════════════════════════════════════════
# 7. save_llm_log — params, defaults, is_fallback, trace_json
# ══════════════════════════════════════════════════════════════════


class TestSaveLLMLog:
    def test_returns_log_id(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 99}

        log_data = {
            "interval_tf": "1h",
            "step_type": "THOUGHT_FINAL",
            "provider": "gemini",
            "signal": "BUY",
            "confidence": 0.85,
            "token_input": 500,
            "token_output": 200,
            "token_total": 700,
        }
        log_id = db.save_llm_log(run_id=1, log_data=log_data)
        assert log_id == 99

    def test_trace_json_list_serialized(self, mock_db):
        """trace_json เป็น list → serialize เป็น JSON string"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        log_data = {
            "interval_tf": "5m",
            "trace_json": [{"step": "THOUGHT_1"}, {"step": "THOUGHT_FINAL"}],
        }
        db.save_llm_log(run_id=1, log_data=log_data)

        params = cursor.execute.call_args[0][1]
        json_params = [p for p in params if isinstance(p, str) and "THOUGHT_1" in p]
        assert len(json_params) >= 1
        # ต้อง parse กลับได้
        parsed = json.loads(json_params[0])
        assert len(parsed) == 2

    def test_trace_json_string_passthrough(self, mock_db):
        """trace_json เป็น string → ส่งตรงๆ ไม่ serialize ซ้ำ"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        raw_json = '{"step": "THOUGHT_1"}'
        log_data = {"interval_tf": "1h", "trace_json": raw_json}
        db.save_llm_log(run_id=1, log_data=log_data)

        params = cursor.execute.call_args[0][1]
        assert raw_json in params

    def test_insert_into_llm_logs(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}
        db.save_llm_log(1, {"interval_tf": "1h"})

        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO llm_logs" in sql
        assert "RETURNING id" in sql

    def test_defaults_for_optional_fields(self, mock_db):
        """optional fields ไม่ส่ง → ใช้ default"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        # ส่งเฉพาะ interval_tf
        db.save_llm_log(1, {"interval_tf": "1h"})

        params = cursor.execute.call_args[0][1]
        # step_type default = "THOUGHT_FINAL"
        assert "THOUGHT_FINAL" in params
        # signal default = "HOLD"
        assert "HOLD" in params
        # confidence default = 0.0
        assert 0.0 in params
        # iterations_used default = 0
        # tool_calls_used default = 0

    def test_is_fallback_converted_to_bool(self, mock_db):
        """is_fallback ต้องถูก convert เป็น bool"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        # ส่ง is_fallback=1 (truthy int)
        db.save_llm_log(1, {"interval_tf": "1h", "is_fallback": 1})

        params = cursor.execute.call_args[0][1]
        # ต้องมี True (bool) ใน params
        assert True in params

    def test_is_fallback_false_by_default(self, mock_db):
        """ไม่ส่ง is_fallback → default False"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_llm_log(1, {"interval_tf": "1h"})

        params = cursor.execute.call_args[0][1]
        assert False in params

    def test_run_id_in_params(self, mock_db):
        """run_id ต้องอยู่ใน params"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_llm_log(run_id=42, log_data={"interval_tf": "1h"})

        params = cursor.execute.call_args[0][1]
        assert 42 in params

    def test_commit_called(self, mock_db):
        """save_llm_log ต้องเรียก commit"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_llm_log(1, {"interval_tf": "1h"})
        conn.commit.assert_called()

    def test_full_prompt_and_response_stored(self, mock_db):
        """full_prompt, full_response ต้องถูกเก็บ"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        db.save_llm_log(
            1,
            {
                "interval_tf": "1h",
                "full_prompt": "Analyze gold market...",
                "full_response": "Based on RSI oversold...",
            },
        )

        params = cursor.execute.call_args[0][1]
        assert "Analyze gold market..." in params
        assert "Based on RSI oversold..." in params


# ══════════════════════════════════════════════════════════════════
# 8. save_llm_logs_batch
# ══════════════════════════════════════════════════════════════════


class TestSaveLLMLogsBatch:
    def test_saves_multiple(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        logs = [
            {"interval_tf": "5m", "signal": "BUY"},
            {"interval_tf": "1h", "signal": "HOLD"},
            {"interval_tf": "4h", "signal": "SELL"},
        ]
        ids = db.save_llm_logs_batch(run_id=10, logs=logs)
        assert len(ids) == 3

    def test_empty_returns_empty(self, mock_db):
        db, cursor, conn = mock_db
        assert db.save_llm_logs_batch(1, []) == []

    def test_partial_failure_continues(self, mock_db):
        """1 log fail → ข้าม แต่บันทึกตัวอื่นต่อ"""
        db, cursor, conn = mock_db

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # fail ตัวที่ 2
                raise Exception("DB error")

        cursor.execute.side_effect = side_effect
        cursor.fetchone.return_value = {"id": 1}

        logs = [
            {"interval_tf": "5m"},
            {"interval_tf": "1h"},  # จะ fail
            {"interval_tf": "4h"},
        ]
        ids = db.save_llm_logs_batch(run_id=1, logs=logs)
        # ตัวที่ 1 สำเร็จ, ตัวที่ 2 fail, ตัวที่ 3 อาจ fail หรือไม่
        # อย่างน้อย 1 ตัวต้องสำเร็จ
        assert len(ids) >= 1

    def test_single_log_batch(self, mock_db):
        """batch 1 log → ids มี 1 element"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 77}

        ids = db.save_llm_logs_batch(5, [{"interval_tf": "1h"}])
        assert ids == [77]


# ══════════════════════════════════════════════════════════════════
# 9. get_llm_logs_for_run
# ══════════════════════════════════════════════════════════════════


class TestGetLLMLogsForRun:
    def test_returns_list_with_parsed_trace(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = [
            {
                "id": 1,
                "interval_tf": "1h",
                "signal": "BUY",
                "trace_json": json.dumps([{"step": "THOUGHT_FINAL"}]),
            },
        ]
        logs = db.get_llm_logs_for_run(run_id=5)
        assert len(logs) == 1
        assert isinstance(logs[0]["trace_json"], list)
        assert logs[0]["trace_json"][0]["step"] == "THOUGHT_FINAL"

    def test_empty_run_returns_empty(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        assert db.get_llm_logs_for_run(999) == []

    def test_bad_trace_json_stays_string(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = [
            {"id": 1, "trace_json": "BROKEN{json"},
        ]
        logs = db.get_llm_logs_for_run(1)
        assert isinstance(logs[0]["trace_json"], str)

    def test_none_trace_json_not_parsed(self, mock_db):
        """trace_json=None → ไม่ error, ไม่ถูก parse"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = [
            {"id": 1, "trace_json": None},
        ]
        logs = db.get_llm_logs_for_run(1)
        assert logs[0]["trace_json"] is None

    def test_multiple_logs_returned(self, mock_db):
        """หลาย logs → return ครบ"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = [
            {"id": 1, "interval_tf": "5m", "trace_json": None},
            {"id": 2, "interval_tf": "1h", "trace_json": None},
            {"id": 3, "interval_tf": "4h", "trace_json": None},
        ]
        logs = db.get_llm_logs_for_run(1)
        assert len(logs) == 3
        assert [l["interval_tf"] for l in logs] == ["5m", "1h", "4h"]

    def test_query_filters_by_run_id(self, mock_db):
        """SQL ต้อง WHERE run_id = %s"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_llm_logs_for_run(42)

        sql = cursor.execute.call_args[0][0]
        assert "WHERE run_id" in sql
        params = cursor.execute.call_args[0][1]
        assert 42 in params

    def test_query_ordered_by_time(self, mock_db):
        """SQL ต้อง ORDER BY logged_at ASC"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_llm_logs_for_run(1)

        sql = cursor.execute.call_args[0][0]
        assert "ORDER BY" in sql
        assert "ASC" in sql


# ══════════════════════════════════════════════════════════════════
# 10. get_recent_llm_logs (ไม่เคยมี test — เพิ่มใหม่)
# ══════════════════════════════════════════════════════════════════


class TestGetRecentLLMLogs:
    """ทดสอบ get_recent_llm_logs — ดึง llm_logs ล่าสุดข้ามรอบ"""

    def test_returns_list_of_dicts(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = [
            {"id": 10, "run_id": 1, "signal": "BUY", "run_at": "2026-04-06"},
            {"id": 9, "run_id": 1, "signal": "HOLD", "run_at": "2026-04-05"},
        ]
        logs = db.get_recent_llm_logs(limit=20)
        assert isinstance(logs, list)
        assert len(logs) == 2
        assert all(isinstance(l, dict) for l in logs)

    def test_empty_returns_empty_list(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        assert db.get_recent_llm_logs() == []

    def test_query_has_join(self, mock_db):
        """SQL ต้อง JOIN กับ runs table"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_recent_llm_logs(limit=10)

        sql = cursor.execute.call_args[0][0]
        assert "JOIN" in sql
        assert "runs" in sql

    def test_query_ordered_desc(self, mock_db):
        """SQL ต้อง ORDER BY DESC (ล่าสุดก่อน)"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_recent_llm_logs()

        sql = cursor.execute.call_args[0][0]
        assert "ORDER BY" in sql
        assert "DESC" in sql

    def test_limit_passed_as_param(self, mock_db):
        """limit ต้องส่งเป็น SQL parameter"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_recent_llm_logs(limit=15)

        params = cursor.execute.call_args[0][1]
        assert 15 in params

    def test_query_selects_key_fields(self, mock_db):
        """SQL ต้อง SELECT fields ที่สำคัญสำหรับ monitoring"""
        db, cursor, conn = mock_db
        cursor.fetchall.return_value = []
        db.get_recent_llm_logs()

        sql = cursor.execute.call_args[0][0]
        for field in ["signal", "confidence", "token_total", "is_fallback"]:
            assert field in sql


# ══════════════════════════════════════════════════════════════════
# 11. save_portfolio / get_portfolio
# ══════════════════════════════════════════════════════════════════


class TestPortfolio:
    def test_save_executes_upsert(self, mock_db):
        db, cursor, conn = mock_db
        data = {
            "cash_balance": 1200.0,
            "gold_grams": 0.5,
            "cost_basis_thb": 45000.0,
            "current_value_thb": 45500.0,
            "unrealized_pnl": 500.0,
            "trades_today": 2,
        }
        db.save_portfolio(data)

        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO portfolio" in sql
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql

    def test_save_params_correct(self, mock_db):
        db, cursor, conn = mock_db
        db.save_portfolio({"cash_balance": 1200.0, "gold_grams": 0.5})

        params = cursor.execute.call_args[0][1]
        assert 1200.0 in params
        assert 0.5 in params

    def test_save_uses_defaults_for_missing_keys(self, mock_db):
        """keys ที่ไม่ส่ง → ใช้ default (cash=1500, gold=0, etc.)"""
        db, cursor, conn = mock_db
        db.save_portfolio({})  # ว่างทั้งหมด

        params = cursor.execute.call_args[0][1]
        # cash_balance default = 1500.0
        assert 1500.0 in params
        # gold_grams default = 0.0
        assert 0.0 in params

    def test_save_includes_timestamp(self, mock_db):
        """updated_at ต้องเป็น ISO format + Z"""
        db, cursor, conn = mock_db
        db.save_portfolio({"cash_balance": 1000})

        params = cursor.execute.call_args[0][1]
        # หา param ที่เป็น timestamp string
        ts_params = [p for p in params if isinstance(p, str) and "Z" in p and "T" in p]
        assert len(ts_params) == 1

    def test_save_commit_called(self, mock_db):
        """save_portfolio ต้องเรียก commit"""
        db, cursor, conn = mock_db
        db.save_portfolio({"cash_balance": 1000})
        conn.commit.assert_called()

    def test_get_returns_dict(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {
            "id": 1,
            "cash_balance": 1500.0,
            "gold_grams": 0.0,
            "cost_basis_thb": 0.0,
            "current_value_thb": 0.0,
            "unrealized_pnl": 0.0,
            "trades_today": 0,
            "updated_at": "2026-04-06",
        }
        port = db.get_portfolio()
        assert port["cash_balance"] == 1500.0

    def test_get_returns_default_when_empty(self, mock_db):
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = None
        port = db.get_portfolio()
        assert port["cash_balance"] == 1500.0
        assert port["gold_grams"] == 0.0

    def test_get_returns_default_on_exception(self, mock_db):
        db, cursor, conn = mock_db
        cursor.execute.side_effect = Exception("connection lost")
        port = db.get_portfolio()
        assert port["cash_balance"] == 1500.0

    def test_get_default_has_all_keys(self, mock_db):
        """default dict ต้องมี keys ครบ"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = None
        port = db.get_portfolio()

        required_keys = {
            "cash_balance",
            "gold_grams",
            "cost_basis_thb",
            "current_value_thb",
            "unrealized_pnl",
            "trades_today",
            "updated_at",
        }
        assert required_keys.issubset(port.keys())

    def test_get_default_values_correct(self, mock_db):
        """default values ต้องตรงกับที่ code กำหนด"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = None
        port = db.get_portfolio()

        assert port["cash_balance"] == 1500.0
        assert port["gold_grams"] == 0.0
        assert port["cost_basis_thb"] == 0.0
        assert port["current_value_thb"] == 0.0
        assert port["unrealized_pnl"] == 0.0
        assert port["trades_today"] == 0
        assert port["updated_at"] == ""


# ══════════════════════════════════════════════════════════════════
# 12. Error Handling & Edge Cases
# ══════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """ทดสอบ edge cases และ error handling ของ RunDatabase"""

    def test_save_run_with_none_values_in_result(self, mock_db):
        """result มี None values → ไม่ crash"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        result = {
            "signal": None,
            "confidence": None,
            "rationale": None,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
        }
        # ต้องไม่ raise Exception
        new_id = db.save_run("gemini", result, {}, "1h", "day")
        assert new_id == 1

    def test_save_run_empty_result(self, mock_db):
        """result ว่าง → ใช้ defaults ทั้งหมด"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        new_id = db.save_run("gemini", {}, {}, "1h", "day")
        assert new_id == 1

        params = cursor.execute.call_args[0][1]
        # signal default = "HOLD"
        assert "HOLD" in params

    def test_save_llm_log_with_fallback_info(self, mock_db):
        """is_fallback=True + fallback_from → ถูกเก็บ"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        log_data = {
            "interval_tf": "1h",
            "is_fallback": True,
            "fallback_from": "gemini",
            "provider": "ollama",
        }
        db.save_llm_log(1, log_data)

        params = cursor.execute.call_args[0][1]
        assert True in params
        assert "gemini" in params
        assert "ollama" in params

    def test_save_run_special_chars_in_rationale(self, mock_db):
        """rationale มี special chars (emoji, unicode) → ไม่ crash"""
        db, cursor, conn = mock_db
        cursor.fetchone.return_value = {"id": 1}

        result = _full_result(rationale="🟢 ทอง bullish — ส่งสัญญาณ ซื้อ 📈")
        new_id = db.save_run("gemini", result, {}, "1h", "day")
        assert new_id == 1

    def test_get_run_detail_complex_json(self, mock_db):
        """react_trace มี nested JSON ซับซ้อน → parse ได้"""
        db, cursor, conn = mock_db
        complex_trace = [
            {
                "step": "THOUGHT_1",
                "response": {
                    "sentiment": {"score": 0.8, "sources": ["news1", "news2"]}
                },
                "tokens": {"input": 100, "output": 50},
            },
            {
                "step": "TOOL_EXECUTION",
                "observation": {"status": "ok", "data": [1, 2, 3]},
            },
        ]
        cursor.fetchone.return_value = {
            "id": 1,
            "react_trace": json.dumps(complex_trace),
            "market_snapshot": json.dumps({"nested": {"deep": True}}),
        }
        detail = db.get_run_detail(1)
        assert len(detail["react_trace"]) == 2
        assert detail["react_trace"][0]["response"]["sentiment"]["score"] == 0.8
        assert detail["market_snapshot"]["nested"]["deep"] is True
