"""
conftest.py — Scoped fixtures สำหรับ test_frontend/ เท่านั้น

กลยุทธ์:
  1. ตั้ง dummy env vars ก่อน import ANYTHING (frontend.api.main อ่าน os.environ
     ที่ module level)
  2. Replace `database.database.RunDatabase` class ด้วย FakeDB **ก่อน**
     import `frontend.api.main` — เพราะ main.py ทำ `db = RunDatabase()`
     ที่ module level ซึ่งจะ raise ถ้า RunDatabase ตัวจริงทำงาน
     (ThreadedConnectionPool ต่อ DSN ทันที)
  3. Replace `supabase.create_client` ด้วย lambda ที่คืน FakeSupabase

Side effects ของ conftest นี้ถูกจำกัดใน scope test_frontend/ เท่านั้น —
test_unit/test_integration ไม่โดน เพราะ pytest โหลด conftest.py
เฉพาะ ancestor directory ของ test ที่กำลังรัน

— Benchaphon, เม.ย. 2026
"""

from __future__ import annotations

import os
import sys
from typing import Iterator

# ── 1. ตั้ง dummy env ก่อน import frontend.api.main ─────────────
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost:5432/fake_db")
os.environ.setdefault("SUPABASE_URL", "http://fake.supabase.local")
os.environ.setdefault("SUPABASE_KEY", "fake-anon-key")

import pytest  # noqa: E402

# ── 2. เพิ่ม Src/ ลง sys.path (ปกติ tests/conftest.py ทำให้แล้ว
#    แต่เพิ่มเพื่อความชัดเจน กรณีรันจาก folder ที่ไม่ใช่ Src/) ───
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from tests.fakes import FakeDB, FakeSupabase  # noqa: E402

# ── 3. Monkeypatch database.database.RunDatabase ก่อน import main ──
#    เพื่อให้ `db = RunDatabase()` ใน main.py ได้ FakeDB แทน
import database.database as _db_module  # noqa: E402

_db_module.RunDatabase = FakeDB  # type: ignore[assignment]

# ── 4. Monkeypatch supabase.create_client ก่อน import main ────────
import supabase as _supabase_module  # noqa: E402

_supabase_module.create_client = lambda _url, _key: FakeSupabase()  # type: ignore[assignment]

# ── 5. ตอนนี้ import frontend.api.main ได้อย่างปลอดภัย ────────────
from frontend.api import main as api_main  # noqa: E402

# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeDB:
    """
    FakeDB instance ใหม่ต่อ test — monkeypatch เข้า frontend.api.main.db

    ใช้ method chaining:
        fake_db.set_fetchone({"id": 1, "signal": "BUY"})
        fake_db.set_fetchall([...])
        fake_db.set_raise(Exception("boom"))
        fake_db.set_portfolio({...})
    """
    fake = FakeDB()
    monkeypatch.setattr(api_main, "db", fake)
    return fake


@pytest.fixture
def fake_supabase(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    """FakeSupabase instance ใหม่ — monkeypatch เข้า frontend.api.main.supabase"""
    fake = FakeSupabase()
    monkeypatch.setattr(api_main, "supabase", fake)
    return fake


@pytest.fixture
def client(fake_db: FakeDB, fake_supabase: FakeSupabase) -> Iterator:
    """
    FastAPI TestClient ที่ใช้ fake_db + fake_supabase

    ทุก test ที่ต้องการยิง HTTP request ใช้ fixture นี้:
        def test_xxx(client, fake_db):
            fake_db.set_fetchone({...})
            r = client.get("/api/xxx")
            assert r.status_code == 200
    """
    from fastapi.testclient import TestClient

    with TestClient(api_main.app) as c:
        yield c
