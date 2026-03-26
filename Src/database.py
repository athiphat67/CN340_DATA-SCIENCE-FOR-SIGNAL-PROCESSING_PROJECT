"""
database.py — Run History Storage
SQLite-based storage for goldtrader agent runs.
Zero extra dependencies — uses Python built-in sqlite3.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
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

# Only the columns we need for the history table display — avoids pulling heavy JSON
_HISTORY_COLS = """
    id, run_at, provider, interval_tf, period,
    signal, confidence, entry_price, stop_loss, take_profit,
    iterations_used, gold_price, rsi, macd_line, trend, rationale
"""


class RunDatabase:
    """
    SQLite-backed store for agent run history.

    Usage:
        db = RunDatabase("runs/history.db")
        db.save_run(provider, result, market_state, interval, period)
        rows = db.get_recent_runs(limit=50)
        detail = db.get_run_detail(run_id=7)
    """

    def __init__(self, db_path: str = "runs/history.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Public API ─────────────────────────────────────────

    def save_run(
        self,
        provider: str,
        result: dict,
        market_state: dict,
        interval_tf: str = "",
        period: str = "",
    ) -> int:
        """
        Persist a completed run.
        Returns the new row id.
        """
        fd = result.get("final_decision", {})
        md = market_state.get("market_data", {})
        ti = market_state.get("technical_indicators", {})

        gold_price  = md.get("spot_price_usd", {}).get("price_usd_per_oz")
        rsi_val     = ti.get("rsi", {}).get("value")
        macd_line   = ti.get("macd", {}).get("macd_line")
        signal_line = ti.get("macd", {}).get("signal_line")
        trend_dir   = ti.get("trend", {}).get("trend")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs (
                    run_at, provider, interval_tf, period,
                    signal, confidence, entry_price, stop_loss, take_profit,
                    rationale, iterations_used, tool_calls_used,
                    gold_price, rsi, macd_line, signal_line, trend,
                    react_trace, market_snapshot
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    provider,
                    interval_tf,
                    period,
                    fd.get("signal", "HOLD"),
                    fd.get("confidence"),
                    fd.get("entry_price"),
                    fd.get("stop_loss"),
                    fd.get("take_profit"),
                    fd.get("rationale", ""),
                    result.get("iterations_used", 0),
                    result.get("tool_calls_used", 0),
                    gold_price,
                    rsi_val,
                    macd_line,
                    signal_line,
                    trend_dir,
                    # Store trace as compact JSON (no indent = saves disk space)
                    json.dumps(result.get("react_trace", []), ensure_ascii=False),
                    # Store only essential market fields, not full payload
                    json.dumps({
                        "market_data": md,
                        "technical_indicators": ti,
                    }, ensure_ascii=False, default=str),
                ),
            )
            return cursor.lastrowid

    def get_recent_runs(self, limit: int = 50) -> list[dict]:
        """
        Returns lightweight rows for history table display.
        Does NOT load react_trace / market_snapshot to keep response fast.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT {_HISTORY_COLS} FROM runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_run_detail(self, run_id: int) -> Optional[dict]:
        """
        Returns full row including react_trace and market_snapshot.
        Called only when user clicks a specific run.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        # Deserialize JSON columns
        for col in ("react_trace", "market_snapshot"):
            if d.get(col):
                try:
                    d[col] = json.loads(d[col])
                except json.JSONDecodeError:
                    pass
        return d

    def get_signal_stats(self) -> dict:
        """
        Quick summary stats — no heavy JSON, just aggregates.
        Used for stats panel at top of history tab.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*)                                         AS total,
                    SUM(CASE WHEN signal='BUY'  THEN 1 ELSE 0 END)  AS buy_count,
                    SUM(CASE WHEN signal='SELL' THEN 1 ELSE 0 END)  AS sell_count,
                    SUM(CASE WHEN signal='HOLD' THEN 1 ELSE 0 END)  AS hold_count,
                    AVG(confidence)                                  AS avg_confidence,
                    AVG(gold_price)                                  AS avg_price
                FROM runs
            """).fetchone()
        return {
            "total":          row[0] or 0,
            "buy_count":      row[1] or 0,
            "sell_count":     row[2] or 0,
            "hold_count":     row[3] or 0,
            "avg_confidence": round(row[4] or 0, 3),
            "avg_price":      round(row[5] or 0, 2),
        }

    def delete_run(self, run_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        return result.rowcount > 0

    # ── Private ───────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_CREATE_TABLE)
            conn.execute("PRAGMA journal_mode=WAL")  # better concurrent write perf