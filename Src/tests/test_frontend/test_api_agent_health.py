"""
GET /api/agent-health — รวม last run + last price → latency / iterations / api_status

DB error → raise 500 (visible error state for frontend).
⚠️ เทคนิค: endpoint เรียก cursor.execute 2 ครั้ง — FakeCursor คืน fetchone เดียวกัน
    ทั้ง 2 ครั้ง (simplification) — test จะใช้ fetchone เป็นค่ารวม
"""
from datetime import datetime, timezone, timedelta


class TestAgentHealthHappyPath:
    def test_stable_when_price_fresh(self, client, fake_db):
        """price timestamp < 300s → api_status = Stable"""
        # simplification: FakeCursor ใช้ fetchone เดียวกัน ทั้ง run record และ price record
        # → ต้องรวม fields ของทั้งคู่ไว้ใน dict เดียว
        fresh = datetime.now(timezone.utc) - timedelta(seconds=30)
        fake_db.set_fetchone(
            {
                "run_at": "2026-04-19",
                "execution_time_ms": 1500,
                "confidence": 0.85,
                "iterations_used": 3,
                "timestamp": fresh.isoformat(),
            }
        )
        r = client.get("/api/agent-health")
        assert r.status_code == 200
        body = r.json()
        assert body["api_status"] == "Stable"
        assert body["latency"] == 1500
        assert body["iterations"] == 3
        assert body["accuracy"] == 0.85
        assert body["quality_score"] == 95

    def test_warning_when_price_stale(self, client, fake_db):
        """price > 300s → Warning + quality 60"""
        stale = datetime.now(timezone.utc) - timedelta(seconds=600)
        fake_db.set_fetchone(
            {
                "execution_time_ms": 2000,
                "confidence": 0.7,
                "iterations_used": 5,
                "timestamp": stale.isoformat(),
            }
        )
        r = client.get("/api/agent-health")
        body = r.json()
        assert body["api_status"] == "Warning"
        assert body["quality_score"] == 60


class TestAgentHealthFallbacks:
    def test_db_error_returns_500(self, client, fake_db):
        """DB error must raise 500 so UI can show real error state."""
        fake_db.set_raise(Exception("db down"))
        r = client.get("/api/agent-health")
        assert r.status_code == 500
        assert "db down" in r.json()["detail"]

    def test_naive_timestamp_is_treated_as_utc(self, client, fake_db):
        """tz-naive timestamp → endpoint assume UTC (ไม่ crash)"""
        naive = (datetime.now(timezone.utc) - timedelta(seconds=60)).replace(tzinfo=None)
        fake_db.set_fetchone(
            {
                "execution_time_ms": 100,
                "confidence": 0.5,
                "iterations_used": 1,
                "timestamp": naive.isoformat(),
            }
        )
        r = client.get("/api/agent-health")
        assert r.status_code == 200
        # 60s < 300s → Stable
        assert r.json()["api_status"] == "Stable"
