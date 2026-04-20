"""
GET /api/backtest/trades?model=&limit=500&signal= — รายการ trade จาก backtest_equity_curve
ที่ final_signal IN ('BUY', 'SELL')
"""


def _trade_row(ts: str = "2026-04-19 10:00", sig: str = "BUY") -> dict:
    return {
        "timestamp": ts,
        "final_signal": sig,
        "final_confidence": 0.85,
        "net_pnl_thb": 250.5,
        "position_size_thb": 1000.0,
        "stop_loss": 44500.0,
        "take_profit": 45500.0,
        "llm_rationale": "Strong signal",
        "llm_confidence": 0.9,
        "llm_signal": sig,
        "final_correct": True,
        "final_profitable": True,
        "rejection_reason": None,
        "portfolio_value": 10500.0,
        "close_thai": 45100.0,
    }


class TestBacktestTradesHappyPath:
    def test_returns_formatted_trades(self, client, fake_db):
        fake_db.set_fetchall([_trade_row()])
        r = client.get("/api/backtest/trades?limit=100")
        assert r.status_code == 200
        t = r.json()[0]
        assert t["signal"] == "BUY"
        assert t["confidence"] == 0.85
        assert t["pnl"] == 250.5
        assert t["price"] == 45100.0
        assert t["correct"] is True
        assert t["profitable"] is True

    def test_default_limit_500_always_in_where(self, client, fake_db):
        fake_db.set_fetchall([])
        client.get("/api/backtest/trades")
        sql, params = fake_db.last_cursor.executed[-1]
        assert "final_signal IN ('BUY', 'SELL')" in sql
        # limit อยู่ท้ายสุดของ params
        assert params[-1] == 500

    def test_model_and_signal_filters(self, client, fake_db):
        fake_db.set_fetchall([])
        client.get("/api/backtest/trades?model=x&signal=BUY&limit=10")
        sql, params = fake_db.last_cursor.executed[-1]
        assert "model_name = %s" in sql
        assert "final_signal = %s" in sql
        assert "x" in params
        assert "BUY" in params
        assert params[-1] == 10

    def test_invalid_signal_filter_ignored(self, client, fake_db):
        """signal=XYZ → ไม่เติม WHERE clause (validator บน endpoint)"""
        fake_db.set_fetchall([])
        client.get("/api/backtest/trades?signal=INVALID")
        sql, _params = fake_db.last_cursor.executed[-1]
        # final_signal = %s ไม่มี (แค่ IN ('BUY','SELL'))
        count_where = sql.count("final_signal = %s")
        assert count_where == 0

    def test_signal_case_insensitive(self, client, fake_db):
        """signal=buy → normalized เป็น BUY"""
        fake_db.set_fetchall([])
        client.get("/api/backtest/trades?signal=buy")
        _sql, params = fake_db.last_cursor.executed[-1]
        assert "BUY" in params


class TestBacktestTradesEdgeCases:
    def test_empty_result_returns_empty_list(self, client, fake_db):
        fake_db.set_fetchall([])
        r = client.get("/api/backtest/trades")
        assert r.status_code == 200
        assert r.json() == []

    def test_none_numeric_fields_coerce_to_zero(self, client, fake_db):
        row = _trade_row()
        row["net_pnl_thb"] = None
        row["stop_loss"] = None
        row["close_thai"] = None
        fake_db.set_fetchall([row])
        r = client.get("/api/backtest/trades")
        t = r.json()[0]
        assert t["pnl"] == 0
        assert t["stop_loss"] == 0
        assert t["price"] == 0

    def test_bad_timestamp_fallback(self, client, fake_db):
        """timestamp ที่ parse ไม่ได้ → ใช้ str[:16] แทน ไม่ crash"""
        row = _trade_row(ts="NOT_A_DATE")
        fake_db.set_fetchall([row])
        r = client.get("/api/backtest/trades")
        assert r.status_code == 200

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("boom"))
        r = client.get("/api/backtest/trades")
        assert r.status_code == 500
