"""
fakes.py — Shared Fake DB / Supabase classes สำหรับ Frontend API tests

ไม่มี side effect ที่ module level:
  - ไม่ import fastapi, frontend.api.main, psycopg2
  - เป็น pure Python classes ที่ทำ duck-typing เลียนแบบ RunDatabase + supabase client
  - สามารถนำไปใช้ซ้ำใน test folder อื่นได้ถ้าจำเป็น

ใช้คู่กับ tests/test_frontend/conftest.py ที่ monkeypatch
`database.database.RunDatabase` ด้วย FakeDB class
และ `supabase.create_client` ให้คืน FakeSupabase
ก่อน import `frontend.api.main`.

— เพิ่มเมื่อ เม.ย. 2026 (Benchaphon) สำหรับ test_frontend suite
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, List, Optional


# ══════════════════════════════════════════════════════════════════
# FakeCursor — เลียนแบบ psycopg2 cursor
# ══════════════════════════════════════════════════════════════════


class FakeCursor:
    """
    Cursor ปลอมที่ควบคุมพฤติกรรมได้ต่อ test case

    Usage:
        cursor = FakeCursor()
        cursor.set_fetchone({"id": 1, "signal": "BUY"})
        cursor.set_fetchall([{"id": 1}, {"id": 2}])
        cursor.set_raise(Exception("boom"))   # execute() จะ raise แทน

    หลัง test จะอ่าน:
        cursor.executed  → list ของ (sql, params) ทุกครั้งที่เรียก execute
    """

    def __init__(self, **_kwargs: Any) -> None:
        # รับ cursor_factory=RealDictCursor เป็น kwarg แล้วทิ้งไป
        self._fetchone_value: Any = None
        self._fetchall_value: List[Any] = []
        self._raise_on_execute: Optional[BaseException] = None
        self.executed: List[tuple] = []

    # ── Setters ที่ test เรียก ─────────────────────────────────
    def set_fetchone(self, value: Any) -> "FakeCursor":
        self._fetchone_value = value
        return self

    def set_fetchall(self, rows: Iterable[Any]) -> "FakeCursor":
        self._fetchall_value = list(rows)
        return self

    def set_raise(self, exc: BaseException) -> "FakeCursor":
        self._raise_on_execute = exc
        return self

    # ── API เลียนแบบ psycopg2 cursor ──────────────────────────
    def execute(self, sql: str, params: Any = None) -> None:
        self.executed.append((sql, params))
        if self._raise_on_execute is not None:
            raise self._raise_on_execute

    def fetchone(self) -> Any:
        return self._fetchone_value

    def fetchall(self) -> List[Any]:
        return self._fetchall_value

    def close(self) -> None:
        pass

    # ── Context manager (conn.cursor() as cursor) ─────────────
    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# ══════════════════════════════════════════════════════════════════
# FakeConnection — เลียนแบบ psycopg2 connection
# ══════════════════════════════════════════════════════════════════


class FakeConnection:
    """
    Connection ปลอม — รับ cursor ที่ต้องคืนเมื่อเรียก .cursor()

    รับ cursor_factory=RealDictCursor kwarg แล้วทิ้ง
    """

    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs: Any) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        pass


# ══════════════════════════════════════════════════════════════════
# FakeDB — เลียนแบบ RunDatabase
# ══════════════════════════════════════════════════════════════════


class FakeDB:
    """
    Fake RunDatabase — ไม่ต่อ DB จริง

    Public helpers:
        .set_fetchone(value)      — ค่าที่ cursor.fetchone() จะคืน
        .set_fetchall(rows)       — ค่าที่ cursor.fetchall() จะคืน
        .set_raise(exc)           — cursor.execute() จะ raise
        .set_portfolio(d)         — ค่าที่ .get_portfolio() จะคืน
        .raise_on_portfolio(exc)  — .get_portfolio() จะ raise
        .last_cursor              — FakeCursor ล่าสุดที่ถูกใช้ (ตรวจ SQL ได้)
    """

    def __init__(self) -> None:
        self._cursor = FakeCursor()
        self._connection = FakeConnection(self._cursor)
        self._portfolio: dict = {
            "cash_balance": 1500.0,
            "gold_grams": 0.0,
            "cost_basis_thb": 0.0,
            "current_value_thb": 0.0,
            "unrealized_pnl": 0.0,
            "trades_today": 0,
            "updated_at": "",
        }
        self._raise_on_portfolio: Optional[BaseException] = None

    # ── Helpers ให้ test ตั้งค่า ──────────────────────────────
    def set_fetchone(self, value: Any) -> "FakeDB":
        self._cursor.set_fetchone(value)
        return self

    def set_fetchall(self, rows: Iterable[Any]) -> "FakeDB":
        self._cursor.set_fetchall(rows)
        return self

    def set_raise(self, exc: BaseException) -> "FakeDB":
        self._cursor.set_raise(exc)
        return self

    def set_portfolio(self, portfolio: dict) -> "FakeDB":
        self._portfolio = portfolio
        return self

    def raise_on_portfolio(self, exc: BaseException) -> "FakeDB":
        self._raise_on_portfolio = exc
        return self

    @property
    def last_cursor(self) -> FakeCursor:
        return self._cursor

    # ── RunDatabase surface ที่ frontend.api.main ใช้ ────────
    @contextmanager
    def get_connection(self):
        yield self._connection

    def get_portfolio(self) -> dict:
        if self._raise_on_portfolio is not None:
            raise self._raise_on_portfolio
        return dict(self._portfolio)

    def close(self) -> None:
        pass


# ══════════════════════════════════════════════════════════════════
# FakeSupabase — เลียนแบบ Client สำหรับ sync_latest_price()
# ══════════════════════════════════════════════════════════════════


class _FakeSupabaseResponse:
    def __init__(self, data: List[dict]) -> None:
        self.data = data


class _FakeSupabaseQuery:
    """Chainable query: .select().order().limit().execute()"""

    def __init__(self, data: List[dict]) -> None:
        self._data = data

    def select(self, *_a, **_kw) -> "_FakeSupabaseQuery":
        return self

    def order(self, *_a, **_kw) -> "_FakeSupabaseQuery":
        return self

    def limit(self, *_a, **_kw) -> "_FakeSupabaseQuery":
        return self

    def execute(self) -> _FakeSupabaseResponse:
        return _FakeSupabaseResponse(self._data)


class FakeSupabase:
    """
    Fake Supabase client ที่รองรับ
        supabase.table("gold_prices_ig").select("*").order(...).limit(1).execute()
    """

    def __init__(self, rows: Optional[List[dict]] = None) -> None:
        self._rows = rows or []

    def set_rows(self, rows: List[dict]) -> "FakeSupabase":
        self._rows = rows
        return self

    def table(self, _name: str) -> _FakeSupabaseQuery:
        return _FakeSupabaseQuery(self._rows)
