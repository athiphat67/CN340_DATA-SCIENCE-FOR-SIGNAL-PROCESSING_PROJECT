"""
GET /api/market-bias — runs ล่าสุด → map signal → direction (Bullish/Bearish/Neutral)

DB error → raise 500 (visible error state for frontend).
"""


class TestMarketBiasMapping:
    def test_buy_becomes_bullish(self, client, fake_db):
        fake_db.set_fetchone(
            {"signal": "BUY", "confidence": 0.9, "rationale": "Strong uptrend"}
        )
        r = client.get("/api/market-bias")
        assert r.status_code == 200
        body = r.json()
        assert body["direction"] == "Bullish"
        assert body["conviction"] == 0.9
        assert body["reason"] == "Strong uptrend"

    def test_sell_becomes_bearish(self, client, fake_db):
        fake_db.set_fetchone({"signal": "SELL", "confidence": 0.75, "rationale": "RSI overbought"})
        r = client.get("/api/market-bias")
        assert r.json()["direction"] == "Bearish"

    def test_hold_becomes_neutral(self, client, fake_db):
        fake_db.set_fetchone({"signal": "HOLD", "confidence": 0.5, "rationale": "Sideways"})
        r = client.get("/api/market-bias")
        assert r.json()["direction"] == "Neutral"


class TestMarketBiasFallbacks:
    def test_no_run_returns_neutral_defaults(self, client, fake_db):
        fake_db.set_fetchone(None)
        r = client.get("/api/market-bias")
        assert r.status_code == 200
        assert r.json() == {
            "direction": "Neutral",
            "conviction": 0,
            "reason": "No recent runs found.",
        }

    def test_db_error_returns_500(self, client, fake_db):
        """DB error must raise 500 so UI can display error state."""
        fake_db.set_raise(Exception("boom"))
        r = client.get("/api/market-bias")
        assert r.status_code == 500
        assert "boom" in r.json()["detail"]

    def test_empty_confidence_and_rationale(self, client, fake_db):
        """confidence=None + rationale=None → fallback strings"""
        fake_db.set_fetchone({"signal": "HOLD", "confidence": None, "rationale": None})
        r = client.get("/api/market-bias")
        body = r.json()
        assert body["conviction"] == 0
        assert body["reason"] == "Analysis in progress..."
