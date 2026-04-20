"""
GET /api/recent-signals?limit=20 — llm_logs ล่าสุด (signal != NULL)
"""


class TestRecentSignalsHappyPath:
    def test_default_limit_20(self, client, fake_db):
        fake_db.set_fetchall(
            [
                {"id": 1, "signal": "BUY", "confidence": 0.9},
                {"id": 2, "signal": "SELL", "confidence": 0.7},
            ]
        )
        r = client.get("/api/recent-signals")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        # ตรวจ query param default: limit=20
        _sql, params = fake_db.last_cursor.executed[-1]
        assert params == (20,)

    def test_custom_limit(self, client, fake_db):
        fake_db.set_fetchall([])
        client.get("/api/recent-signals?limit=5")
        _sql, params = fake_db.last_cursor.executed[-1]
        assert params == (5,)

    def test_returned_columns_match_spec(self, client, fake_db):
        """SQL ต้อง SELECT เฉพาะคอลัมน์ที่ frontend ใช้"""
        fake_db.set_fetchall([{"id": 1, "signal": "BUY"}])
        client.get("/api/recent-signals?limit=10")
        sql, _ = fake_db.last_cursor.executed[-1]
        for col in [
            "id",
            "logged_at",
            "interval_tf",
            "entry_price",
            "take_profit",
            "stop_loss",
            "signal",
            "confidence",
        ]:
            assert col in sql


class TestRecentSignalsEdgeCases:
    def test_empty_result_returns_empty_list(self, client, fake_db):
        fake_db.set_fetchall([])
        r = client.get("/api/recent-signals?limit=10")
        assert r.status_code == 200
        assert r.json() == []

    def test_invalid_limit_returns_422(self, client, fake_db):
        """limit=abc → FastAPI int validation"""
        r = client.get("/api/recent-signals?limit=abc")
        assert r.status_code == 422

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("boom"))
        r = client.get("/api/recent-signals")
        assert r.status_code == 500
