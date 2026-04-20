"""
GET /api/active-positions — 2 signals ล่าสุดที่เป็น BUY/SELL

DB error → raise 500 (visible error state for frontend).
"""
from datetime import datetime


class TestActivePositionsHappyPath:
    def test_formats_positions_correctly(self, client, fake_db):
        fake_db.set_fetchall(
            [
                {
                    "id": 101,
                    "open_time": datetime(2026, 4, 19, 10, 30),
                    "type": "BUY",
                    "entry": 45000.0,
                    "tp": 45500.0,
                    "sl": 44500.0,
                    "confidence": 0.85,
                }
            ]
        )
        r = client.get("/api/active-positions")
        assert r.status_code == 200
        pos = r.json()[0]
        assert pos["id"] == "POS-101"
        assert pos["type"] == "BUY"
        assert pos["entry"] == 45000.0
        assert pos["tp"] == 45500.0
        assert pos["sl"] == 44500.0
        assert pos["asset"] == "XAU/THB (96.5%)"
        # current = entry × 1.002
        assert pos["current"] == 45000.0 * 1.002

    def test_handles_iso_string_open_time(self, client, fake_db):
        """ถ้า open_time มาเป็น string ISO → parse ถูก"""
        fake_db.set_fetchall(
            [
                {
                    "id": 1,
                    "open_time": "2026-04-19T10:30:00Z",
                    "type": "SELL",
                    "entry": 45000,
                    "tp": 44500,
                    "sl": 45500,
                    "confidence": 0.7,
                }
            ]
        )
        r = client.get("/api/active-positions")
        assert r.status_code == 200
        assert "Apr" in r.json()[0]["openTime"]

    def test_sql_filters_buy_sell_only(self, client, fake_db):
        fake_db.set_fetchall([])
        client.get("/api/active-positions")
        sql, _ = fake_db.last_cursor.executed[-1]
        assert "signal IN ('BUY', 'SELL')" in sql
        assert "LIMIT 2" in sql


class TestActivePositionsEdgeCases:
    def test_empty_result_returns_empty_list(self, client, fake_db):
        fake_db.set_fetchall([])
        r = client.get("/api/active-positions")
        assert r.status_code == 200
        assert r.json() == []

    def test_db_error_returns_500(self, client, fake_db):
        """DB error must surface as 500 so UI shows real error state."""
        fake_db.set_raise(Exception("db down"))
        r = client.get("/api/active-positions")
        assert r.status_code == 500
        assert "db down" in r.json()["detail"]

    def test_none_values_coerce_to_zero(self, client, fake_db):
        """entry/tp/sl อาจเป็น None ใน DB → coerce 0.0"""
        fake_db.set_fetchall(
            [
                {
                    "id": 5,
                    "open_time": datetime(2026, 4, 19, 10, 30),
                    "type": "BUY",
                    "entry": None,
                    "tp": None,
                    "sl": None,
                    "confidence": 0.5,
                }
            ]
        )
        r = client.get("/api/active-positions")
        assert r.status_code == 200
        pos = r.json()[0]
        assert pos["entry"] == 0.0
        assert pos["tp"] == 0.0
        assert pos["sl"] == 0.0
