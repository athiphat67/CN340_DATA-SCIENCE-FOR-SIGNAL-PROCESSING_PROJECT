import pandas as pd

# กำหนด Timezone หลักของโปรเจกต์ไว้ที่เดียว
THAI_TZ = "Asia/Bangkok"

def get_thai_time() -> pd.Timestamp:
    """ดึงเวลาปัจจุบันใน Timezone ประเทศไทย"""
    return pd.Timestamp.now(tz=THAI_TZ)

def convert_index_to_thai_tz(datetime_index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """แปลง Timezone ของ Pandas DatetimeIndex ให้เป็นเวลาไทย"""
    if datetime_index.tz is None:
        # ถ้าไม่มี Timezone ติดมา ให้มองเป็น UTC ก่อน แล้วแปลงเป็นไทย
        return datetime_index.tz_localize("UTC").tz_convert(THAI_TZ)
    return datetime_index.tz_convert(THAI_TZ)