import pandas as pd
import os
from datetime import datetime
from contextlib import contextmanager

def log_market_data(data_dict, file_name='market_data.csv'):
    data_dict['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df = pd.DataFrame([data_dict])
    file_exists = os.path.isfile(file_name)
    df.to_csv(file_name, mode='a', header=not file_exists, index=False)

class RunDatabase:
    def __init__(self):
        import os
        from psycopg2.pool import ThreadedConnectionPool
        from psycopg2.extras import RealDictCursor
        
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise ValueError(
                "⚠️ DATABASE_URL is not set. "
                "Please add it to your .env file or Render environment variables."
            )
        
        # --- 🔥 FIX 1: จัดการ URL และบังคับเกราะ SSL ขั้นเด็ดขาด ---
        if self.db_url.startswith("postgres://"):
            self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)

        # 🔥 ท่าไม้ตาย: ยัด TCP Keepalives ทะลวง Proxy ของ Render!
        self._pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=self.db_url,
            cursor_factory=RealDictCursor,
            sslmode="require",
            keepalives=1,               # เปิดโหมดกระตุ้นหัวใจ
            keepalives_idle=30,         # ถ้าเงียบไป 30 วิ ให้ส่งคลื่น
            keepalives_interval=10,     # ส่งซ้ำทุกๆ 10 วิถ้าไม่ได้ตอบกลับ
            keepalives_count=5          # พยายาม 5 ครั้งก่อนยอมแพ้
        )
        sys_logger.info("DB connection pool initialized (อัด TCP Keepalives แล้ว!)")
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Context manager ที่ดึง connection จาก pool และคืนกลับเมื่อเสร็จ"""
        conn = self._pool.getconn()
        
        # --- 🔥 FIX 2: ยันต์กันผี Render ตัดสาย (Idle Connection Drop) ---
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            sys_logger.warning("♻️ ตรวจพบสาย DB หลุด! กำลังต่อ Connection ใหม่อัตโนมัติ...")
            # คืนสายเก่าที่ตายแล้วทิ้งไป แล้วเบิกสายใหม่
            self._pool.putconn(conn, close=True)
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
                # รันสคริปต์สร้างตาราง (ดึงจากตัวแปรด้านบนของไฟล์เธอ)
                cursor.execute(_CREATE_TABLE)
                cursor.execute(_CREATE_PORTFOLIO_TABLE)
                cursor.execute(_CREATE_LLM_LOGS_TABLE)
                cursor.execute(_CREATE_TRADE_LOG_TABLE)
                cursor.execute(_CREATE_GOLD_PRICES_TABLE)

                # ── Idempotent column migrations ───────────────────────────
                migrations = [
                    ("runs", "entry_price_thb", "REAL"),
                    ("runs", "stop_loss_thb", "REAL"),
                    ("runs", "take_profit_thb", "REAL"),
                    ("runs", "usd_thb_rate", "REAL"),
                    ("runs", "gold_price_thb", "REAL"),
                    # ── v3.4: data quality & indicators ───────────────────
                    ("runs", "is_weekend", "BOOLEAN"),
                    ("runs", "data_quality", "TEXT"),
                    ("runs", "macd_histogram", "REAL"),
                    ("runs", "bb_pct_b", "REAL"),
                    ("runs", "atr_thb", "REAL"),
                    ("portfolio", "trailing_stop_level_thb", "REAL"),
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
        sys_logger.info("DB init OK — tables: runs, portfolio, llm_logs, trade_log")