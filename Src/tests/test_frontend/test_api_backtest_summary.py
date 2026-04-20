"""
GET /api/backtest/summary?model= — backtest_summary ล่าสุด (filter ตาม model_name)
"""


class TestBacktestSummary:
    def test_default_no_model_filter(self, client, fake_db):
        fake_db.set_fetchone(
            {
                "id": 1,
                "model_name": "gemini-3-flash",
                "run_date": "2026-04-19",
                "total_trades": 50,
                "win_rate": 0.55,
                "sharpe": 1.4,
            }
        )
        r = client.get("/api/backtest/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["model_name"] == "gemini-3-flash"
        # ไม่ส่ง model param → SQL ไม่มี WHERE clause
        sql, _ = fake_db.last_cursor.executed[-1]
        assert "WHERE model_name" not in sql

    def test_model_filter_passed_as_param(self, client, fake_db):
        fake_db.set_fetchone({"model_name": "test-model", "win_rate": 0.5})
        r = client.get("/api/backtest/summary?model=test-model")
        assert r.status_code == 200
        sql, params = fake_db.last_cursor.executed[-1]
        assert "WHERE model_name = %s" in sql
        assert params == ("test-model",)

    def test_not_found_returns_404(self, client, fake_db):
        fake_db.set_fetchone(None)
        r = client.get("/api/backtest/summary")
        assert r.status_code == 404
        assert "No backtest summary" in r.json()["detail"]

    def test_http_exception_not_wrapped_in_500(self, client, fake_db):
        """HTTPException ที่ endpoint raise เอง ต้อง propagate 404 ไม่กลายเป็น 500"""
        fake_db.set_fetchone(None)
        r = client.get("/api/backtest/summary")
        assert r.status_code == 404  # ไม่ใช่ 500

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("boom"))
        r = client.get("/api/backtest/summary")
        assert r.status_code == 500
