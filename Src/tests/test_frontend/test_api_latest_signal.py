"""
GET /api/latest-signal — return llm_logs แถวล่าสุดที่ signal != NULL
เพิ่ม 'provider': 'AI AGENT' ไว้ใน SQL แล้ว
"""


class TestLatestSignalHappyPath:
    def test_returns_signal_row(self, client, fake_db):
        fake_db.set_fetchone(
            {
                "id": 42,
                "signal": "BUY",
                "confidence": 0.85,
                "rationale": "Bullish momentum",
                "provider": "AI AGENT",
            }
        )
        r = client.get("/api/latest-signal")
        assert r.status_code == 200
        body = r.json()
        assert body["signal"] == "BUY"
        assert body["id"] == 42
        assert body["provider"] == "AI AGENT"

    def test_sql_contains_order_and_limit(self, client, fake_db):
        fake_db.set_fetchone({"id": 1, "signal": "HOLD"})
        client.get("/api/latest-signal")
        sql, _params = fake_db.last_cursor.executed[-1]
        assert "ORDER BY id DESC" in sql
        assert "LIMIT 1" in sql
        assert "signal IS NOT NULL" in sql


class TestLatestSignalEdgeCases:
    def test_no_rows_returns_404(self, client, fake_db):
        """No signal row → HTTPException(404) passes through untouched."""
        fake_db.set_fetchone(None)
        r = client.get("/api/latest-signal")
        assert r.status_code == 404
        assert r.json()["detail"] == "No signals found"

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("connection lost"))
        r = client.get("/api/latest-signal")
        assert r.status_code == 500
        assert "connection lost" in r.json()["detail"]
