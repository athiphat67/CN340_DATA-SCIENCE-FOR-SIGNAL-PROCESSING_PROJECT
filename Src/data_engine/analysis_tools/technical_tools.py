import logging
import pandas as pd
from data_engine.ohlcv_fetcher import OHLCVFetcher
from data_engine.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

# สร้าง instance ของ fetcher ไว้ใช้ร่วมกัน
_fetcher = OHLCVFetcher()

#--------------------------------------------------------------------------------------------------
# เครื่องมือกลุ่ม A (ต้องการ Candle Series) 
# เครื่องมือกลุ่มนี้จะใช้ OHLCVFetcher ไปดึงข้อมูลย้อนหลังมาเพื่อหา Pattern การกลับตัวหรือ Divergence ต่างๆ 
#--------------------------------------------------------------------------------------------------

def detect_swing_low(interval: str = "15m", history_days: int = 3, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบหา Swing Low Structure (จุดต่ำก่อนพุ่ง) [cite: 6, 8, 10]
    นิยาม: แท่งเทียนมี Low ต่ำกว่า N แท่งซ้ายและ N แท่งขวา [cite: 9] 
    และแท่งถัดมาต้องปิดเหนือ High ของแท่ง Swing Low (Confirmation) [cite: 11]
    """
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [detect_swing_low] ใช้ DataFrame จากหน่วยความจำ ({len(df)} แท่ง)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
        
        if len(df) < 5:
            return {"status": "error", "message": "ข้อมูลแท่งเทียนไม่พอ"}

        # ดู 3 แท่งล่าสุด (t-2, t-1, t) เพื่อหา Swing Low ที่แท่ง t-1
        # N = 1 (1 ซ้าย, 1 ขวา) สำหรับตัวอย่างนี้
        left_candle = df.iloc[-3]
        swing_candle = df.iloc[-2]
        right_candle = df.iloc[-1] # แท่งปัจจุบันที่เพิ่งปิด หรือกำลังวิ่ง

        # เงื่อนไข 1: Low ต่ำกว่าซ้ายและขวา [cite: 9]
        is_lowest_low = (swing_candle['low'] < left_candle['low']) and (swing_candle['low'] < right_candle['low'])
        
        # เงื่อนไข 2: แท่งขวาต้องปิดเหนือ High ของแท่ง Swing (Confirm) [cite: 11]
        is_confirmed = right_candle['close'] > swing_candle['high']

        setup_found = is_lowest_low and is_confirmed

        return {
            "status": "success",
            "interval": interval,
            "setup_detected": setup_found,
            "details": {
                "swing_low_price": round(float(swing_candle['low']), 2),
                "confirmation_close": round(float(right_candle['close']), 2)
            },
            "suggestion": "มีโอกาสกลับตัวขึ้น (Bullish Reversal)" if setup_found else "ยังไม่พบสัญญาณ Swing Low ที่ชัดเจน"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def detect_rsi_divergence(interval: str = "15m", history_days: int = 5, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบหา RSI Bullish Divergence [cite: 14, 18]
    ใช้ข้อมูลย้อนหลังอย่างน้อย 10-20 แท่ง [cite: 21] 
    เพื่อดูว่า ราคา Low ใหม่ ต่ำกว่า Low เดิม แต่ RSI ยกตัวสูงขึ้นหรือไม่ [cite: 15, 16]
    """
    try:
        # 🎯 ถ้ามี DataFrame โยนมาให้ ให้ใช้เลย
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [detect_rsi_divergence] ใช้ DataFrame จากหน่วยความจำ ({len(df)} แท่ง)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        if len(df) < 20:
            return {"status": "error", "message": "ข้อมูลไม่เพียงพอ (ต้องการ 20+ แท่ง)"}

        # ใช้ TechnicalIndicators คลาสของคุณเพื่อคำนวณ RSI ทั้ง DataFrame
        calc = TechnicalIndicators(df)
        
        df_with_rsi = calc.df 
        
        # สกัด 20 แท่งล่าสุดมาวิเคราะห์
        recent_df = df_with_rsi.tail(20)
        
        # หาจุด Low ต่ำสุด 2 จุดใน 20 แท่งนี้ (แบบง่าย)
        # แบ่งครึ่งเพื่อหา Low อดีต (Low1) และ Low ปัจจุบัน (Low2)
        past_half = recent_df.iloc[:10]
        recent_half = recent_df.iloc[10:]
        
        low1_idx = past_half['low'].idxmin()
        low2_idx = recent_half['low'].idxmin()
        
        low1 = past_half.loc[low1_idx, 'low']
        rsi1 = past_half.loc[low1_idx, 'rsi_14']
        
        low2 = recent_half.loc[low2_idx, 'low']
        rsi2 = recent_half.loc[low2_idx, 'rsi_14']
        
        # เงื่อนไข: ราคา Low2 < Low1 [cite: 15] แต่ RSI_Low2 > RSI_Low1 [cite: 16]
        is_price_lower = low2 < low1
        is_rsi_higher = rsi2 > rsi1
        divergence_found = is_price_lower and is_rsi_higher

        return {
            "status": "success",
            "divergence_detected": bool(divergence_found),
            "logic": "momentum ลดลง ขณะราคายังลง (ของหมดแรงขาย)" if divergence_found else "ไม่มี divergence", # [cite: 17]
            "data": {
                "Low1": round(float(low1), 2), "RSI1": round(float(rsi1), 2),
                "Low2": round(float(low2), 2), "RSI2": round(float(rsi2), 2)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

    
#--------------------------------------------------------------------------------------------------
# เครื่องมือกลุ่ม B (ใช้ Snapshot + Threshold) 
#--------------------------------------------------------------------------------------------------
    
def check_bb_rsi_combo(current_price: float, lower_bb: float, rsi: float, macd_hist_current: float, macd_hist_prev: float) -> dict:
    """
    ตรวจสอบ BB + RSI Combo [cite: 23, 28]
    เงื่อนไข: ราคา < lower BB AND RSI < 35 AND MACD hist เริ่ม flatten [cite: 25, 26, 27, 29]
    """
    is_price_low = current_price < lower_bb # [cite: 25]
    is_rsi_oversold = rsi < 35.0 # [cite: 26]
    
    # MACD hist เริ่ม flatten (abs(hist) < 0.3 หรือ hist[t] > hist[t-1]) [cite: 29]
    is_macd_flatten = abs(macd_hist_current) < 0.3 or (macd_hist_current > macd_hist_prev)
    
    combo_met = is_price_low and is_rsi_oversold and is_macd_flatten
    
    return {
        "status": "success",
        "combo_detected": combo_met,
        "details": f"Price<BB: {is_price_low}, RSI<35: {is_rsi_oversold}, MACD_Flatten: {is_macd_flatten}"
    }


def calculate_ema_distance(current_price: float, ema_20: float, atr: float) -> dict:
    """
    ตรวจสอบ EMA Distance (Mean Reversion) [cite: 31, 34]
    สูตร: ระยะห่าง = (EMA20 - price) / ATR [cite: 32]
    ถ้าค่า > 5 ATR แปลว่า Overextended มาก มีโอกาสเกิด Mean Reversion [cite: 33, 35]
    """
    if atr <= 0:
        return {"status": "error", "message": "ค่า ATR ต้องมากกว่า 0"}
        
    distance = (ema_20 - current_price) / atr # [cite: 32]
    is_overextended = abs(distance) > 5.0 # [cite: 33]
    
    return {
        "status": "success",
        "distance_atr": round(distance, 2),
        "is_overextended": is_overextended,
        "suggestion": "Overextended มาก (Mean reversion likely)" if is_overextended else "ระยะห่างปกติ" # [cite: 33, 35]
    }


#--------------------------------------------------------------------------------------------------
# Higher Timeframe + General Indicators
#--------------------------------------------------------------------------------------------------

def get_htf_trend(timeframe: str = "4h") -> dict:
    """
    ใช้สำหรับดึงข้อมูลเทรนด์จาก Timeframe ที่ใหญ่กว่า (Higher Timeframe)
    เพื่อให้ LLM ดูภาพรวมก่อนตัดสินใจ
    """
    # TODO: ใส่ Logic ดึงข้อมูลจริงจาก DB หรือ Exchange API
    # อันนี้ Mock data ไว้ก่อน
    return {
        "tool_name": "get_htf_trend",
        "timeframe": timeframe,
        "trend": "bullish",
        "ema_200_status": "price_above_ema",
        "key_support": 2350.0,
        "key_resistance": 2420.0
    }


def check_volatility(asset: str = "XAUUSD") -> dict:
    """ใช้ตรวจสอบความผันผวนของตลาดในปัจจุบัน (เช่น ค่า ATR)"""
    return {
        "asset": asset,
        "volatility": "high",
        "atr_value": 15.5
    }


#--------------------------------------------------------------------------------------------------
# ฟังก์ชันที่ยังไม่ได้รับการ implement (ต้องการ development)
#--------------------------------------------------------------------------------------------------

def detect_liquidity_sweep(timeframe: str = "15m", lookback: int = 20) -> dict:
    """
    ตรวจสอบพฤติกรรมกวาดสภาพคล่อง (Stop Hunt / Liquidity Sweep)
    ตรวจสอบว่าราคาทะลุ Low/High เดิมลงไปสั้นๆ แล้วทิ้งไส้เทียนดึงกลับอย่างรวดเร็วหรือไม่
    เหตุผลที่ LLM ควรใช้: ถ้าเจอสภาพนี้ มักเป็นจุดกลับตัวที่ Smart Money เข้าซื้อ
    """
    return {"status": "not_implemented", "message": "รอการพัฒนาเพิ่มเติม"}


def identify_supply_demand_zones(timeframe: str = "1h") -> dict:
    """
    ค้นหาโซน Supply (แนวต้านจากแท่งเทียนแรงขาย) และ Demand (แนวรับจากแท่งเทียนแรงซื้อ) ที่ยังไม่ถูกทดสอบ
    เหตุผลที่ LLM ควรใช้: เพื่อหาจุดตั้ง Pending Order หรือจุดวาง Stop Loss ที่ปลอดภัยกว่าจุดปกติ
    """
    return {"status": "not_implemented", "message": "รอการพัฒนาเพิ่มเติม"}


def check_volume_anomaly(interval: str = "5m") -> dict:
    """
    ตรวจสอบความผิดปกติของ Volume (Volume Climax / Anomaly)
    เช็คว่าแท่งเทียนปัจจุบันมี Volume สูงกว่าค่าเฉลี่ย 20 แท่งย้อนหลังแบบผิดปกติหรือไม่ (เช่น โตขึ้น 300%)
    เหตุผลที่ LLM ควรใช้: ใช้กรองว่าการ Breakout แนวต้านนั้นเป็นของจริง (Volume ซัพพอร์ต) หรือหลอก (Fakeout)
    """
    return {"status": "not_implemented", "message": "รอการพัฒนาเพิ่มเติม"}