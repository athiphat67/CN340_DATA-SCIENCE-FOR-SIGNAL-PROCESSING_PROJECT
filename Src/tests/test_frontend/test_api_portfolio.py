"""
GET /api/portfolio — คำนวณ pnl_percent + total_equity จาก db.get_portfolio()
"""


class TestPortfolioHappyPath:
    def test_response_shape_complete(self, client, fake_db):
        fake_db.set_portfolio(
            {
                "cash_balance": 1500.0,
                "gold_grams": 1.5,
                "cost_basis_thb": 45000.0,
                "unrealized_pnl": 200.0,
                "trades_today": 3,
            }
        )
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {
            "available_cash",
            "unrealized_pnl",
            "pnl_percent",
            "trades_today",
            "total_equity",
        }
        assert body["available_cash"] == 1500.0
        assert body["unrealized_pnl"] == 200.0
        assert body["trades_today"] == 3

    def test_total_equity_formula(self, client, fake_db):
        """total_equity = cash + (cost_basis × gold_grams) + unrealized_pnl"""
        fake_db.set_portfolio(
            {
                "cash_balance": 1000.0,
                "gold_grams": 2.0,
                "cost_basis_thb": 45000.0,
                "unrealized_pnl": 500.0,
                "trades_today": 1,
            }
        )
        r = client.get("/api/portfolio")
        # 1000 + (45000 * 2) + 500 = 91500
        assert r.json()["total_equity"] == 91500.0

    def test_pnl_percent_calculation(self, client, fake_db):
        """pnl_percent = round(unrealized_pnl / total_cost × 100, 2)"""
        fake_db.set_portfolio(
            {
                "cash_balance": 0.0,
                "gold_grams": 1.0,
                "cost_basis_thb": 10000.0,  # total_cost = 10000
                "unrealized_pnl": 500.0,
                "trades_today": 0,
            }
        )
        r = client.get("/api/portfolio")
        # 500 / 10000 × 100 = 5.0
        assert r.json()["pnl_percent"] == 5.0


class TestPortfolioEdgeCases:
    def test_zero_cost_avoids_division_by_zero(self, client, fake_db):
        """cost_basis=0 หรือ gold_grams=0 → pnl_percent = 0.0 (ไม่ crash)"""
        fake_db.set_portfolio(
            {
                "cash_balance": 1500.0,
                "gold_grams": 0.0,
                "cost_basis_thb": 0.0,
                "unrealized_pnl": 0.0,
                "trades_today": 0,
            }
        )
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        assert r.json()["pnl_percent"] == 0.0

    def test_none_values_coerce_to_zero(self, client, fake_db):
        """DB return None สำหรับ numeric → convert เป็น 0.0 ไม่ crash"""
        fake_db.set_portfolio(
            {
                "cash_balance": 1000.0,
                "gold_grams": None,
                "cost_basis_thb": None,
                "unrealized_pnl": None,
                "trades_today": 0,
            }
        )
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert body["unrealized_pnl"] == 0.0
        assert body["pnl_percent"] == 0.0

    def test_db_exception_returns_500(self, client, fake_db):
        fake_db.raise_on_portfolio(RuntimeError("db down"))
        r = client.get("/api/portfolio")
        assert r.status_code == 500
        assert "db down" in r.json()["detail"]
