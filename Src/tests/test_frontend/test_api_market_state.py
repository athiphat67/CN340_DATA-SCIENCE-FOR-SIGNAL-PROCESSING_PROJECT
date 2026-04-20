"""
GET /api/market-state — row ล่าสุดจาก gold_prices_ig (ไม่แปลง field)
"""


class TestMarketState:
    def test_returns_full_row(self, client, fake_db):
        fake_db.set_fetchone(
            {
                "id": 100,
                "timestamp": "2026-04-19 12:00",
                "ask_96": 45100.0,
                "bid_96": 44800.0,
                "spot_price": 2350.0,
                "usd_thb": 34.5,
            }
        )
        r = client.get("/api/market-state")
        assert r.status_code == 200
        body = r.json()
        assert body["ask_96"] == 45100.0
        assert body["spot_price"] == 2350.0

    def test_no_data_returns_404(self, client, fake_db):
        """Empty market-state row → 404 passes through."""
        fake_db.set_fetchone(None)
        r = client.get("/api/market-state")
        assert r.status_code == 404
        assert r.json()["detail"] == "No market data"

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.set_raise(Exception("connect timeout"))
        r = client.get("/api/market-state")
        assert r.status_code == 500
