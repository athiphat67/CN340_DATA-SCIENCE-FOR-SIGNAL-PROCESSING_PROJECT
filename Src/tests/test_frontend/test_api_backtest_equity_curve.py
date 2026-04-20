"""
GET /api/backtest/equity-curve?model=&limit=2000 — equity curve for chart
"""


def _curve_row(ts: str = "2026-04-19 10:00") -> dict:
    return {
        "timestamp": ts,
        "portfolio_value": 10500.0,
        "signal": "BUY",
        "pnl": 150.0,
        "price": 45000.0,
        "profitable": True,
    }


class TestBacktestEquityCurveHappyPath:
    def test_returns_formatted_points(self, client, fake_db):
        fake_db.set_fetchall([_curve_row()])
        r = client.get("/api/backtest/equity-curve?limit=100")
        assert r.status_code == 200
        p = r.json()[0]
        assert set(p.keys()) == {
            "date",
            "value",
            "signal",
            "pnl",
            "price",
            "raw_ts",
            "profitable",
        }
        assert p["value"] == 10500.0
        assert p["price"] == 45000.0
        assert p["raw_ts"] == "2026-04-19 10:00"
        assert p["profitable"] is True

    def test_default_limit_2000(self, client, fake_db):
        fake_db.set_fetchall([])
        client.get("/api/backtest/equity-curve")
        _sql, params = fake_db.last_cursor.executed[-1]
        assert params == (2000,)

    def test_model_filter(self, client, fake_db):
        fake_db.set_fetchall([])
        client.get("/api/backtest/equity-curve?model=gpt4&limit=500")
        sql, params = fake_db.last_cursor.executed[-1]
        assert "WHERE model_name = %s" in sql
        assert params == ("gpt4", 500)


class TestBacktestEquityCurveEdgeCases:
    def test_empty_result_returns_empty_list(self, client, fake_db):
        fake_db.set_fetchall([])
        r = client.get("/api/backtest/equity-curve")
        assert r.json() == []

    def test_none_values_coerce_to_zero(self, client, fake_db):
        row = _curve_row()
        row["portfolio_value"] = None
        row["pnl"] = None
        row["price"] = None
        fake_db.set_fetchall([row])
        r = client.get("/api/backtest/equity-curve")
        p = r.json()[0]
        assert p["value"] == 0
        assert p["pnl"] == 0
        assert p["price"] == 0

    def test_signal_none_becomes_hold(self, client, fake_db):
        """signal=None → fallback 'HOLD' ใน response"""
        row = _curve_row()
        row["signal"] = None
        fake_db.set_fetchall([row])
        r = client.get("/api/backtest/equity-curve")
        assert r.json()[0]["signal"] == "HOLD"

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("boom"))
        r = client.get("/api/backtest/equity-curve")
        assert r.status_code == 500
