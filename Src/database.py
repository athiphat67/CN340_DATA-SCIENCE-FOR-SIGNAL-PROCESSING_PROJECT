import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────
# Schema (PostgreSQL)
# ─────────────────────────────────────────────

# จุดที่เปลี่ยน: AUTOINCREMENT -> SERIAL
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

_HISTORY_COLS = """
    id, run_at, provider, interval_tf, period,
    signal, confidence, entry_price, stop_loss, take_profit,
    iterations_used, gold_price, rsi, macd_line, trend, rationale
"""

class RunDatabase:
    def __init__(self):
        # ดึง DATABASE_URL จากไฟล์ .env หรือ Environment Variables บน Render
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise ValueError("⚠️ DATABASE_URL is not set. Please add it to your .env file or Render environment variables.")
        self._init_db()

    def get_connection(self):
        # ใช้ RealDictCursor เพื่อให้ผลลัพธ์ออกมาเป็น Dictionary เหมือน sqlite3.Row
        return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_CREATE_TABLE)
            conn.commit()

    # ── Public API ─────────────────────────────────────────

    def save_run(self, provider: str, result: dict, market_state: dict, interval_tf: str = "", period: str = "") -> int:
        fd = result.get("final_decision", {})
        md = market_state.get("market_data", {})
        ti = market_state.get("technical_indicators", {})

        gold_price  = md.get("spot_price_usd", {}).get("price_usd_per_oz")
        rsi_val     = ti.get("rsi", {}).get("value")
        macd_line   = ti.get("macd", {}).get("macd_line")
        signal_line = ti.get("macd", {}).get("signal_line")
        trend_dir   = ti.get("trend", {}).get("trend")

        # จุดที่เปลี่ยน: ใช้ %s แทน ? และใช้ RETURNING id แทน lastrowid
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
                # PostgreSQL ต้องระบุชนิดตัวแปรเพื่อ SUM ให้ถูกต้องหากจำเป็น แต่ในเคสนี้ CASE ให้ผลเป็น 1 หรือ 0 อยู่แล้ว
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