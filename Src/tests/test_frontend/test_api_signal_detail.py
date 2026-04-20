"""
GET /api/signals/{signal_id} — return llm_logs row ที่ id = signal_id
"""


class TestSignalDetailHappyPath:
    def test_returns_matching_row(self, client, fake_db):
        fake_db.set_fetchone(
            {"id": 597, "signal": "SELL", "rationale": "RSI overbought"}
        )
        r = client.get("/api/signals/597")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 597
        assert body["signal"] == "SELL"

    def test_sql_uses_parameterized_id(self, client, fake_db):
        fake_db.set_fetchone({"id": 1, "signal": "BUY"})
        client.get("/api/signals/1")
        sql, params = fake_db.last_cursor.executed[-1]
        assert "WHERE id = %s" in sql
        assert params == (1,)


class TestSignalDetailEdgeCases:
    def test_not_found_returns_404(self, client, fake_db):
        """Missing id → 404 passes through."""
        fake_db.set_fetchone(None)
        r = client.get("/api/signals/999999")
        assert r.status_code == 404
        assert r.json()["detail"] == "Signal not found"

    def test_invalid_id_returns_422(self, client, fake_db):
        """FastAPI path validator: non-int → 422 (ไม่เข้า try block → ไม่โดน bug)"""
        r = client.get("/api/signals/not-a-number")
        assert r.status_code == 422

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("boom"))
        r = client.get("/api/signals/1")
        assert r.status_code == 500

    def test_zero_id_still_queries_db(self, client, fake_db):
        """boundary: id=0 valid int → query executes → None row → 404."""
        fake_db.set_fetchone(None)
        r = client.get("/api/signals/0")
        assert r.status_code == 404
