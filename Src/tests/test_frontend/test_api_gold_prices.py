"""
GET /api/gold-prices — sync จาก supabase ก่อน แล้วดึงจาก Postgres
"""


class TestGoldPricesHappyPath:
    def test_returns_mapped_fields(self, client, fake_db, fake_supabase):
        """ask_96 → hsh_sell, bid_96 → hsh_buy + spot_price, usd_thb"""
        fake_supabase.set_rows(
            [
                {
                    "timestamp": "2026-04-19 10:00",
                    "ask_96": 45200.5,
                    "bid_96": 44900.0,
                    "spot_price": 2350.0,
                    "usd_thb": 34.5,
                }
            ]
        )
        fake_db.set_fetchone(
            {
                "ask_96": 45200.5,
                "bid_96": 44900.0,
                "spot_price": 2350.0,
                "usd_thb": 34.5,
            }
        )
        r = client.get("/api/gold-prices")
        assert r.status_code == 200
        body = r.json()
        assert body["hsh_sell"] == 45200.5
        assert body["hsh_buy"] == 44900.0
        assert body["spot_price"] == 2350.0
        assert body["usd_thb"] == 34.5

    def test_triggers_sync_before_fetch(self, client, fake_db, fake_supabase):
        """sync_latest_price() ต้อง execute INSERT ON CONFLICT ก่อน SELECT"""
        fake_supabase.set_rows(
            [
                {
                    "timestamp": "2026-04-19 10:00",
                    "ask_96": 100,
                    "bid_96": 99,
                    "spot_price": 2000,
                    "usd_thb": 34,
                }
            ]
        )
        fake_db.set_fetchone(
            {"ask_96": 100, "bid_96": 99, "spot_price": 2000, "usd_thb": 34}
        )
        client.get("/api/gold-prices")

        executed_sqls = [sql for (sql, _) in fake_db.last_cursor.executed]
        # ต้องมีทั้ง INSERT (sync) และ SELECT (read)
        has_insert = any("INSERT INTO gold_prices_ig" in s for s in executed_sqls)
        has_select = any("SELECT * FROM gold_prices_ig" in s for s in executed_sqls)
        assert has_insert, f"Expected INSERT in {executed_sqls}"
        assert has_select, f"Expected SELECT in {executed_sqls}"


class TestGoldPricesEdgeCases:
    def test_no_data_returns_404(self, client, fake_db, fake_supabase):
        """No gold row in Postgres → 404 passes through."""
        fake_supabase.set_rows([])
        fake_db.set_fetchone(None)
        r = client.get("/api/gold-prices")
        assert r.status_code == 404
        assert r.json()["detail"] == "No gold data found in Postgres"

    def test_supabase_empty_still_queries_postgres(
        self, client, fake_db, fake_supabase
    ):
        """Supabase ไม่มี data (sync skip) แต่ Postgres มี cached → 200"""
        fake_supabase.set_rows([])  # ไม่ INSERT
        fake_db.set_fetchone(
            {"ask_96": 100, "bid_96": 99, "spot_price": 2000, "usd_thb": 34}
        )
        r = client.get("/api/gold-prices")
        assert r.status_code == 200
        assert r.json()["hsh_sell"] == 100

    def test_db_exception_returns_500(self, client, fake_db, fake_supabase):
        fake_supabase.set_rows([])
        fake_db.set_raise(Exception("pg down"))
        r = client.get("/api/gold-prices")
        assert r.status_code == 500
