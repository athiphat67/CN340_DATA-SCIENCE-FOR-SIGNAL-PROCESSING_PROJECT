"""Smoke test — ตรวจว่า conftest import frontend.api.main สำเร็จ + client ใช้งานได้"""

import pytest


def test_client_fixture_works(client):
    """TestClient สร้างได้ + app attribute พร้อม"""
    assert client is not None


def test_fake_db_is_patched_into_api_main(client, fake_db):
    """fake_db ถูก monkeypatch เข้า frontend.api.main.db"""
    from frontend.api import main as api_main

    assert api_main.db is fake_db


def test_fake_supabase_is_patched(client, fake_supabase):
    """fake_supabase ถูก monkeypatch เข้า frontend.api.main.supabase"""
    from frontend.api import main as api_main

    assert api_main.supabase is fake_supabase


def test_unknown_route_returns_404(client):
    """FastAPI routing ยังทำงาน — 404 สำหรับ path ที่ไม่มี"""
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
