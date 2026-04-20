"""
GET /api/performance-chart?limit=50 — runs แถวล่าสุด + format เวลาให้สวยงาม
"""


class TestPerformanceChartHappyPath:
    def test_returns_formatted_points(self, client, fake_db):
        fake_db.set_fetchall(
            [
                {
                    "timestamp": "2026-04-19T10:00:00",
                    "signalId": 1,
                    "action": "BUY",
                    "price": 45000.0,
                },
                {
                    "timestamp": "2026-04-19T11:00:00",
                    "signalId": 2,
                    "action": "HOLD",
                    "price": 45100.0,
                },
            ]
        )
        r = client.get("/api/performance-chart")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        for p in body:
            assert set(p.keys()) == {"time", "price", "signalId", "action"}
        assert body[0]["price"] == 45000.0
        assert body[1]["action"] == "HOLD"

    def test_default_limit_50(self, client, fake_db):
        fake_db.set_fetchall([])
        client.get("/api/performance-chart")
        _sql, params = fake_db.last_cursor.executed[-1]
        assert params == (50,)

    def test_action_filter_unknown_becomes_null(self, client, fake_db):
        """action ที่ไม่ใช่ BUY/SELL/HOLD → null"""
        fake_db.set_fetchall(
            [
                {
                    "timestamp": "2026-04-19T10:00:00",
                    "signalId": 1,
                    "action": "WAIT",
                    "price": 45000.0,
                }
            ]
        )
        r = client.get("/api/performance-chart")
        assert r.json()[0]["action"] is None


class TestPerformanceChartEdgeCases:
    def test_empty_data_returns_empty_list(self, client, fake_db):
        fake_db.set_fetchall([])
        r = client.get("/api/performance-chart")
        assert r.status_code == 200
        assert r.json() == []

    def test_bad_timestamp_falls_back_to_raw(self, client, fake_db):
        """timestamp parse ไม่ได้ → ยังคืน raw string แทน ไม่ crash"""
        fake_db.set_fetchall(
            [
                {
                    "timestamp": "INVALID_DATE",
                    "signalId": 1,
                    "action": "BUY",
                    "price": 45000.0,
                }
            ]
        )
        r = client.get("/api/performance-chart")
        assert r.status_code == 200
        assert r.json()[0]["time"] == "INVALID_DATE"

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("boom"))
        r = client.get("/api/performance-chart")
        assert r.status_code == 500
        # endpoint ทำ custom error message
        assert "Failed to fetch chart data" in r.json()["detail"]
