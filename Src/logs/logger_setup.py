import logging
import os
import time
from functools import wraps
from datetime import datetime, timezone, timedelta

# 1. กำหนดโฟลเดอร์เก็บ Log
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 2. Custom Formatter สำหรับ TH Time (UTC+7)
class THTimeFormatter(logging.Formatter):
    def converter(self, timestamp):
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return (dt + timedelta(hours=7)).timetuple()

# รูปแบบ Log: [Timestamp] [Level] [Module:Function] - Message
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(filename)s:%(funcName)s] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger(name: str, log_file: str, level=logging.INFO):
    """ฟังก์ชันสร้าง Logger ที่ออกทั้ง Console และ File"""
    logger = logging.getLogger("client")
    logger.propagate = False
    logger.setLevel(level)
    
    # ป้องกันการ add handler ซ้ำ
    if not logger.handlers:
        formatter = THTimeFormatter(LOG_FORMAT, DATE_FORMAT)

        # File Handler
        file_handler = logging.FileHandler(os.path.join(LOG_DIR, log_file), encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

# 3. สร้าง Loggers
sys_logger = setup_logger("system_logger", "system.log", level=logging.DEBUG)
llm_logger = setup_logger("llm_logger", "llm_trace.log", level=logging.DEBUG) 

# 4. Decorator สำหรับจับเวลาการทำงาน (Elapsed Time) & Action
def log_method(logger_instance):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger_instance.debug(f"▶️ START Action: {func.__name__}")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger_instance.info(f"✅ END Action: {func.__name__} | Elapsed: {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger_instance.error(f"❌ ERROR in {func.__name__}: {e} | Elapsed: {elapsed:.2f}s", exc_info=True)
                raise
        return wrapper
    return decorator