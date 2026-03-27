import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────
# Schema (PostgreSQL)
# ─────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    id               SERIAL PRIMARY KEY,
    run_at           TEXT    NOT NULL,
    provider         TEXT    NOT NULL,
    interval_tf      TEXT,
    period           TEXT,
    signal           TEXT,
    confidence       REAL,
    entry_price      REAL,
    stop_loss        REAL,
    take_profit      REAL,
    rationale        TEXT,
    iterations_used  INTEGER,
    tool_calls_used  INTEGER,
    gold_price       REAL,
    rsi              REAL,
    macd_line        REAL,
    signal_line      REAL,
    trend            TEXT,
    react_trace      TEXT,
    market_snapshot  TEXT
);
"""

# ── [เพิ่มใหม่] Portfolio Table ────────────────────────────────────────────────
# เก็บ portfolio ของ user แค่ 1 row (id=1 เสมอ) ใช้ UPSERT
_CREATE_PORTFOLIO_TABLE = """
CREATE TABLE IF NOT EXISTS portfolio (
    id                SERIAL PRIMARY KEY,
    cash_balance      REAL    NOT NULL DEFAULT 1500.0,
    gold_grams        REAL    NOT NULL DEFAULT 0.0,
    cost_basis_thb    REAL    NOT NULL DEFAULT 0.0,
    current_value_thb REAL    NOT NULL DEFAULT 0.0,
    unrealized_pnl    REAL    NOT NULL DEFAULT 0.0,
    trades_today      INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT    NOT NULL
);
"""

_HISTORY_COLS = """
    id, run_at, provider, interval_tf, period,
    signal, confidence, entry_price, stop_loss, take_profit,
    iterations_used, gold_price, rsi, macd_line, trend, rationale
"""

class RunDatabase:
    def __init__(self):
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise ValueError("⚠️ DATABASE_URL is not set. Please add it to your .env file or Render environment variables.")
        self._init_db()

    def get_connection(self):
        return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_CREATE_TABLE)
                # ── [เพิ่มใหม่] สร้าง portfolio table ด้วย ──────────────────
                cursor.execute(_CREATE_PORTFOLIO_TABLE)
            conn.commit()

    # ── Public API (runs) ──────────────────────────────────────────────────────

    def save_run(self, provider: str, result: dict, market_state: dict, interval_tf: str = "", period: str = "") -> int:
        fd = result.get("final_decision", {})
        md = market_state.get("market_data", {})
        ti = market_state.get("technical_indicators", {})

        gold_price  = md.get("spot_price_usd", {}).get("price_usd_per_oz")
        rsi_val     = ti.get("rsi", {}).get("value")
        macd_line   = ti.get("macd", {}).get("macd_line")
        signal_line = ti.get("macd", {}).get("signal_line")
        trend_dir   = ti.get("trend", {}).get("trend")

        query = """
            INSERT INTO runs (
                run_at, provider, interval_tf, period,
                signal, confidence, entry_price, stop_loss, take_profit,
                rationale, iterations_used, tool_calls_used,
                gold_price, rsi, macd_line, signal_line, trend,
                react_trace, market_snapshot
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id;
        """
        values = (
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            provider, interval_tf, period,
            fd.get("signal", "HOLD"), fd.get("confidence"),
            fd.get("entry_price"), fd.get("stop_loss"), fd.get("take_profit"),
            fd.get("rationale", ""), result.get("iterations_used", 0), result.get("tool_calls_used", 0),
            gold_price, rsi_val, macd_line, signal_line, trend_dir,
            json.dumps(result.get("react_trace", []), ensure_ascii=False),
            json.dumps({"market_data": md, "technical_indicators": ti}, ensure_ascii=False, default=str),
        )

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
                new_id = cursor.fetchone()['id']
            conn.commit()
            return new_id

    def get_recent_runs(self, limit: int = 50) -> list[dict]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT {_HISTORY_COLS} FROM runs ORDER BY id DESC LIMIT %s", (limit,))
                rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def get_run_detail(self, run_id: int) -> Optional[dict]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
                row = cursor.fetchone()
        
        if not row:
            return None
            
        d = dict(row)
        for col in ("react_trace", "market_snapshot"):
            if d.get(col):
                try:
                    d[col] = json.loads(d[col])
                except json.JSONDecodeError:
                    pass
        return d

    def get_signal_stats(self) -> dict:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        COUNT(*)                                         AS total,
                        SUM(CASE WHEN signal='BUY'  THEN 1 ELSE 0 END)  AS buy_count,
                        SUM(CASE WHEN signal='SELL' THEN 1 ELSE 0 END)  AS sell_count,
                        SUM(CASE WHEN signal='HOLD' THEN 1 ELSE 0 END)  AS hold_count,
                        AVG(confidence)                                  AS avg_confidence,
                        AVG(gold_price)                                  AS avg_price
                    FROM runs
                """)
                row = cursor.fetchone()

        return {
            "total":          row['total'] or 0,
            "buy_count":      row['buy_count'] or 0,
            "sell_count":     row['sell_count'] or 0,
            "hold_count":     row['hold_count'] or 0,
            "avg_confidence": round(row['avg_confidence'] or 0, 3),
            "avg_price":      round(row['avg_price'] or 0, 2),
        }

    def delete_run(self, run_id: int) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM runs WHERE id = %s", (run_id,))
                deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count > 0

    # ── [เพิ่มใหม่] Portfolio API ───────────────────────────────────────────────

    def save_portfolio(self, data: dict) -> None:
        """
        UPSERT portfolio — มีแค่ 1 row เสมอ (id = 1)
        ถ้ายังไม่มีจะ INSERT, ถ้ามีแล้วจะ UPDATE
        data keys: cash_balance, gold_grams, cost_basis_thb,
                   current_value_thb, unrealized_pnl, trades_today
        """
        query = """
            INSERT INTO portfolio (id, cash_balance, gold_grams, cost_basis_thb,
                                   current_value_thb, unrealized_pnl, trades_today, updated_at)
            VALUES (1, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                cash_balance      = EXCLUDED.cash_balance,
                gold_grams        = EXCLUDED.gold_grams,
                cost_basis_thb    = EXCLUDED.cost_basis_thb,
                current_value_thb = EXCLUDED.current_value_thb,
                unrealized_pnl    = EXCLUDED.unrealized_pnl,
                trades_today      = EXCLUDED.trades_today,
                updated_at        = EXCLUDED.updated_at;
        """
        values = (
            data.get("cash_balance", 1500.0),
            data.get("gold_grams", 0.0),
            data.get("cost_basis_thb", 0.0),
            data.get("current_value_thb", 0.0),
            data.get("unrealized_pnl", 0.0),
            data.get("trades_today", 0),
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
        )
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
            conn.commit()

    def get_portfolio(self) -> dict:
        """
        ดึง portfolio row (id=1)
        ถ้ายังไม่มีข้อมูล return default (ทุนเริ่มต้น 1500 บาท)
        """
        default = {
            "cash_balance":      1500.0,
            "gold_grams":        0.0,
            "cost_basis_thb":    0.0,
            "current_value_thb": 0.0,
            "unrealized_pnl":    0.0,
            "trades_today":      0,
            "updated_at":        "",
        }
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM portfolio WHERE id = 1")
                    row = cursor.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
        return default