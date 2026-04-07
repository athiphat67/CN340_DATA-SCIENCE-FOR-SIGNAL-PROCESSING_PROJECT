import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from datetime import datetime
from typing import Optional
from logs.logger_setup import sys_logger

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
    entry_price      REAL,        -- THB/gram (ราคาจาก LLM โดยตรง — ไม่ใช่ USD)
    stop_loss        REAL,        -- THB/gram
    take_profit      REAL,        -- THB/gram
    entry_price_thb  REAL,        -- alias เหมือน entry_price (backward compat)
    stop_loss_thb    REAL,
    take_profit_thb  REAL,
    usd_thb_rate     REAL,
    rationale        TEXT,
    iterations_used  INTEGER,
    tool_calls_used  INTEGER,
    gold_price       REAL,        -- USD/oz
    gold_price_thb   REAL,        -- THB/gram (sell price จาก ออม NOW)
    rsi              REAL,
    macd_line        REAL,
    signal_line      REAL,
    trend            TEXT,
    react_trace      TEXT,        -- JSON array ของ trace steps
    market_snapshot  TEXT         -- JSON snapshot ของ market_data + indicators
);
"""

# ── LLM Logs Table ─────────────────────────────────────────────────────────────
# เก็บกระบวนการคิดทั้งหมดของ LLM ต่อ 1 run:
#   - ทุก step ของ ReAct loop (THOUGHT / ACTION / OBSERVATION / THOUGHT_FINAL)
#   - Token usage (input / output / total)
#   - Elapsed time ต่อ call
#   - Full prompt + response text
#
# TODO (react.py): ให้ ReactOrchestrator include "prompt_text" และ "response_raw"
#                  ในแต่ละ trace entry เพื่อให้ full_prompt / full_response ไม่เป็น NULL
_CREATE_LLM_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS llm_logs (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    logged_at       TEXT    NOT NULL,
    interval_tf     TEXT,
    step_type       TEXT,           -- THOUGHT / ACTION / OBSERVATION / THOUGHT_FINAL
    iteration       INTEGER DEFAULT 0,
    provider        TEXT,
    signal          TEXT,           -- ผลตัดสิน (มีเฉพาะ THOUGHT_FINAL)
    confidence      REAL,
    rationale       TEXT,
    entry_price     REAL,           -- THB/gram
    stop_loss       REAL,           -- THB/gram
    take_profit     REAL,           -- THB/gram
    full_prompt     TEXT,           -- prompt ที่ส่งไป LLM (NULL จนกว่า react.py จะ expose)
    full_response   TEXT,           -- response ดิบจาก LLM (NULL จนกว่า react.py จะ expose)
    trace_json      TEXT,           -- JSON ของ trace steps ทั้งหมดในรอบนี้
    token_input     INTEGER,
    token_output    INTEGER,
    token_total     INTEGER,
    elapsed_ms      INTEGER,
    iterations_used INTEGER DEFAULT 0,
    tool_calls_used INTEGER DEFAULT 0,
    is_fallback     BOOLEAN DEFAULT FALSE,
    fallback_from   TEXT            -- provider ต้นทางที่ fail ก่อน fallback
);
"""

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
    iterations_used, gold_price, gold_price_thb, rsi, macd_line, trend, rationale
"""

# FIX: whitelist สำหรับ migration — ป้องกัน f-string injection ถ้า migrations list
#      เคยถูกย้ายมาจาก config ภายนอกในอนาคต
_ALLOWED_MIGRATION_TABLES = {"runs", "portfolio", "llm_logs"}
_ALLOWED_MIGRATION_TYPES  = {"REAL", "INTEGER", "TEXT", "BOOLEAN"}


class RunDatabase:
    def __init__(self):
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise ValueError(
                "⚠️ DATABASE_URL is not set. "
                "Please add it to your .env file or Render environment variables."
            )
        # FIX: ใช้ connection pool แทนการเปิด connection ใหม่ทุกครั้ง
        # min=1, max=5 เหมาะกับ Render free tier (ลิมิต ~10 connections)
        self._pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=self.db_url,
            cursor_factory=RealDictCursor,
        )
        sys_logger.info("DB connection pool initialized (min=1, max=5)")
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Context manager ที่ดึง connection จาก pool และคืนกลับเมื่อเสร็จ"""
        conn = self._pool.getconn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def close(self) -> None:
        """ปิด pool ทั้งหมด — เรียกตอน shutdown"""
        self._pool.closeall()
        sys_logger.info("DB connection pool closed")

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_CREATE_TABLE)
                cursor.execute(_CREATE_PORTFOLIO_TABLE)
                cursor.execute(_CREATE_LLM_LOGS_TABLE)

                # ── Idempotent column migrations ───────────────────────────
                migrations = [
                    ("runs", "entry_price_thb",  "REAL"),
                    ("runs", "stop_loss_thb",    "REAL"),
                    ("runs", "take_profit_thb",  "REAL"),
                    ("runs", "usd_thb_rate",     "REAL"),
                    ("runs", "gold_price_thb",   "REAL"),
                ]
                for table, col, typ in migrations:
                    # FIX: whitelist ก่อน interpolate เข้า f-string
                    if table not in _ALLOWED_MIGRATION_TABLES:
                        raise ValueError(f"Migration rejected: unknown table '{table}'")
                    if typ not in _ALLOWED_MIGRATION_TYPES:
                        raise ValueError(f"Migration rejected: unknown type '{typ}'")
                    cursor.execute(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ};"
                    )
            conn.commit()
        sys_logger.info("DB init OK — tables: runs, portfolio, llm_logs")

    # ── runs ──────────────────────────────────────────────────────────────────

    def save_run(
        self,
        provider: str,
        result: dict,
        market_state: dict,
        interval_tf: str = "",
        period: str = "",
    ) -> int:
        """
        บันทึกผล analysis 1 ครั้งลง table runs

        FIX (v3.3): ราคา entry_price / stop_loss / take_profit จาก LLM
                    เป็น THB/gram อยู่แล้ว (เห็นจาก llm_trace.log)
                    → เก็บตรงๆ ไม่ต้องแปลงจาก USD อีก
        FIX (v3.3): ลบ @log_method decorator ออก เพื่อป้องกัน double-log
                    (decorator wrapper ใน caller เป็นคนจัดการ elapsed แล้ว)
        """
        sys_logger.debug(
            f"save_run START — provider={provider}, interval={interval_tf}, period={period}"
        )

        signal_val    = result.get("signal", "HOLD")
        conf_val      = result.get("confidence", 0.0)
        rationale_val = result.get("rationale", "")
        if not rationale_val:
            breakdown = result.get("voting_breakdown", {})
            if breakdown.get(signal_val):
                rationale_val = f"Weighted voting result: {signal_val}"

        md = market_state.get("market_data", {})
        ti = market_state.get("technical_indicators", {})

        gold_price_usd = md.get("spot_price_usd", {}).get("price_usd_per_oz")
        usd_thb        = md.get("forex", {}).get("usd_thb")
        gold_price_thb = md.get("thai_gold_thb", {}).get("sell_price_thb")

        rsi_val     = ti.get("rsi", {}).get("value")
        macd_line   = ti.get("macd", {}).get("macd_line")
        signal_line = ti.get("macd", {}).get("signal_line")
        trend_dir   = ti.get("trend", {}).get("trend")

        # ─── ราคา THB/gram จาก LLM โดยตรง (ไม่แปลง) ──────────────────────
        entry_thb = result.get("entry_price")   # THB/gram
        stop_thb  = result.get("stop_loss")      # THB/gram
        take_thb  = result.get("take_profit")    # THB/gram

        query = """
            INSERT INTO runs (
                run_at, provider, interval_tf, period,
                signal, confidence,
                entry_price, stop_loss, take_profit,
                entry_price_thb, stop_loss_thb, take_profit_thb,
                usd_thb_rate, gold_price_thb,
                rationale, iterations_used, tool_calls_used,
                gold_price, rsi, macd_line, signal_line, trend,
                react_trace, market_snapshot
            ) VALUES (
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,
                %s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s
            )
            RETURNING id;
        """
        values = (
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            provider, interval_tf, period,
            signal_val, conf_val,
            entry_thb, stop_thb, take_thb,
            entry_thb, stop_thb, take_thb,   # _thb aliases
            usd_thb, gold_price_thb,
            rationale_val,
            result.get("iterations_used", 0),
            result.get("tool_calls_used", 0),
            gold_price_usd, rsi_val, macd_line, signal_line, trend_dir,
            json.dumps(result.get("react_trace", []), ensure_ascii=False),
            json.dumps(
                {"market_data": md, "technical_indicators": ti},
                ensure_ascii=False, default=str,
            ),
        )

        # FIX: wrap DB write ด้วย try/except — log payload ที่ fail แล้ว re-raise
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, values)
                    new_id = cursor.fetchone()["id"]
                conn.commit()
        except Exception as e:
            sys_logger.error(
                f"save_run FAILED — provider={provider} interval={interval_tf} "
                f"signal={signal_val} error={e}"
            )
            raise

        sys_logger.info(
            f"save_run OK — ID={new_id} | {signal_val} {conf_val:.1%} | provider={provider}"
        )
        return new_id

    def get_recent_runs(self, limit: int = 50) -> list[dict]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT {_HISTORY_COLS} FROM runs ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
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
        # FIX: เพิ่ม try/except และ guard กรณี row เป็น None
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT
                            COUNT(*)                                         AS total,
                            SUM(CASE WHEN signal='BUY'  THEN 1 ELSE 0 END)  AS buy_count,
                            SUM(CASE WHEN signal='SELL' THEN 1 ELSE 0 END)  AS sell_count,
                            SUM(CASE WHEN signal='HOLD' THEN 1 ELSE 0 END)  AS hold_count,
                            AVG(confidence)                                  AS avg_confidence,
                            AVG(gold_price_thb)                              AS avg_price
                        FROM runs
                    """)
                    row = cursor.fetchone()
        except Exception as e:
            sys_logger.error(f"get_signal_stats FAILED: {e}")
            row = None

        if not row:
            return {
                "total": 0, "buy_count": 0, "sell_count": 0,
                "hold_count": 0, "avg_confidence": 0.0, "avg_price": 0.0,
            }

        return {
            "total":          row["total"] or 0,
            "buy_count":      row["buy_count"] or 0,
            "sell_count":     row["sell_count"] or 0,
            "hold_count":     row["hold_count"] or 0,
            "avg_confidence": round(row["avg_confidence"] or 0, 3),
            "avg_price":      round(row["avg_price"] or 0, 2),  # THB/gram
        }

    def delete_run(self, run_id: int) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM runs WHERE id = %s", (run_id,))
                deleted_count = cursor.rowcount
            conn.commit()
        return deleted_count > 0

    # ── llm_logs ──────────────────────────────────────────────────────────────

    def save_llm_log(self, run_id: int, log_data: dict) -> int:
        """
        บันทึก 1 LLM log entry ลง llm_logs

        log_data keys (ทั้งหมด optional ยกเว้น interval_tf):
            interval_tf       : str   — ชื่อ interval เช่น "1h"
            step_type         : str   — "THOUGHT_FINAL" / "THOUGHT" / "ACTION" / "OBSERVATION"
            iteration         : int   — ลำดับ iteration ใน ReAct loop
            provider          : str   — provider ที่ใช้จริง
            signal            : str   — BUY / SELL / HOLD
            confidence        : float
            rationale         : str   — เหตุผลของ LLM
            entry_price       : float — THB/gram
            stop_loss         : float — THB/gram
            take_profit       : float — THB/gram
            full_prompt       : str   — prompt ที่ส่งไป (None จนกว่า react.py จะ expose)
            full_response     : str   — response ดิบ (None จนกว่า react.py จะ expose)
            trace_json        : list  — trace steps ทั้งหมด
            token_input       : int
            token_output      : int
            token_total       : int
            elapsed_ms        : int   — milliseconds
            iterations_used   : int
            tool_calls_used   : int
            is_fallback       : bool
            fallback_from     : str   — provider ต้นทางที่ fail
        """
        trace_json = log_data.get("trace_json")
        if isinstance(trace_json, list):
            trace_json = json.dumps(trace_json, ensure_ascii=False, default=str)

        query = """
            INSERT INTO llm_logs (
                run_id, logged_at, interval_tf, step_type, iteration,
                provider, signal, confidence, rationale,
                entry_price, stop_loss, take_profit,
                full_prompt, full_response, trace_json,
                token_input, token_output, token_total,
                elapsed_ms, iterations_used, tool_calls_used,
                is_fallback, fallback_from
            ) VALUES (
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s
            )
            RETURNING id;
        """
        values = (
            run_id,
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            log_data.get("interval_tf", ""),
            log_data.get("step_type", "THOUGHT_FINAL"),
            log_data.get("iteration", 0),
            log_data.get("provider", ""),
            log_data.get("signal", "HOLD"),
            log_data.get("confidence", 0.0),
            log_data.get("rationale", ""),
            log_data.get("entry_price"),
            log_data.get("stop_loss"),
            log_data.get("take_profit"),
            log_data.get("full_prompt"),
            log_data.get("full_response"),
            trace_json,
            log_data.get("token_input"),
            log_data.get("token_output"),
            log_data.get("token_total"),
            log_data.get("elapsed_ms"),
            log_data.get("iterations_used", 0),
            log_data.get("tool_calls_used", 0),
            bool(log_data.get("is_fallback", False)),
            log_data.get("fallback_from"),
        )

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
                new_id = cursor.fetchone()["id"]
            conn.commit()

        sys_logger.debug(
            f"save_llm_log OK — log_id={new_id} run_id={run_id} "
            f"interval={log_data.get('interval_tf')} tokens={log_data.get('token_total')}"
        )
        return new_id

    def save_llm_logs_batch(self, run_id: int, logs: list[dict]) -> list[int]:
        """บันทึก llm_logs หลาย entry (1 run = หลาย interval = หลาย logs)"""
        if not logs:
            return []

        ids    = []
        errors = []
        for log_data in logs:
            try:
                log_id = self.save_llm_log(run_id, log_data)
                ids.append(log_id)
            except Exception as e:
                interval = log_data.get("interval_tf", "unknown")
                sys_logger.error(
                    f"save_llm_logs_batch: error for interval={interval}: {e}"
                )
                # FIX: เก็บ error detail ไว้เพื่อ traceability
                errors.append({"interval": interval, "error": str(e)})

        sys_logger.info(
            f"save_llm_logs_batch: {len(ids)}/{len(logs)} logs saved for run_id={run_id}"
        )
        # FIX: log summary ของที่ fail ทั้งหมด ไม่ใช่แค่นับ
        if errors:
            sys_logger.warning(
                f"save_llm_logs_batch: {len(errors)} failed entries — {errors}"
            )
        return ids

    def get_llm_logs_for_run(self, run_id: int) -> list[dict]:
        """ดึง llm_logs ทั้งหมดของ run เรียงตามเวลา"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, logged_at, interval_tf, step_type, iteration,
                           provider, signal, confidence, rationale,
                           entry_price, stop_loss, take_profit,
                           full_prompt, full_response, trace_json,
                           token_input, token_output, token_total,
                           elapsed_ms, iterations_used, tool_calls_used,
                           is_fallback, fallback_from
                    FROM llm_logs
                    WHERE run_id = %s
                    ORDER BY logged_at ASC, id ASC
                    """,
                    (run_id,),
                )
                rows = cursor.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            if d.get("trace_json"):
                try:
                    d["trace_json"] = json.loads(d["trace_json"])
                except json.JSONDecodeError:
                    pass
            result.append(d)
        return result

    def get_recent_llm_logs(self, limit: int = 20) -> list[dict]:
        """ดึง llm_logs ล่าสุด (ข้ามรอบ) สำหรับ monitoring"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT l.id, l.run_id, l.logged_at, l.interval_tf,
                           l.provider, l.signal, l.confidence,
                           l.token_input, l.token_output, l.token_total,
                           l.elapsed_ms, l.is_fallback, l.fallback_from,
                           r.run_at
                    FROM llm_logs l
                    LEFT JOIN runs r ON r.id = l.run_id
                    ORDER BY l.id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
        return [dict(r) for r in rows]

    # ── portfolio ─────────────────────────────────────────────────────────────

    def save_portfolio(self, data: dict) -> None:
        """UPSERT portfolio — มีแค่ 1 row เสมอ (id = 1)"""
        sys_logger.info(
            f"save_portfolio: cash={data.get('cash_balance')}, gold={data.get('gold_grams')}"
        )
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
        """ดึง portfolio row (id=1) ถ้าไม่มีคืน default"""
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
        except Exception as e:
            # FIX: log ให้รู้ว่า DB fail — ไม่ใช่แค่ "ยังไม่มี portfolio"
            sys_logger.warning(f"get_portfolio failed, returning default: {e}")