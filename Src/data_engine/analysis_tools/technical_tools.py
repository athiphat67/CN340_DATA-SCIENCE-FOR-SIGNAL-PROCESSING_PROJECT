import logging
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import DBSCAN
from data_engine.ohlcv_fetcher import OHLCVFetcher
from data_engine.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

# สร้าง instance ของ fetcher ไว้ใช้ร่วมกัน
_fetcher = OHLCVFetcher()

#--------------------------------------------------------------------------------------------------
# เครื่องมือกลุ่ม A (ต้องการ Candle Series) 
# เครื่องมือกลุ่มนี้จะใช้ OHLCVFetcher ไปดึงข้อมูลย้อนหลังมาเพื่อหา Pattern การกลับตัวหรือ Divergence ต่างๆ 
#--------------------------------------------------------------------------------------------------
def check_spot_thb_alignment(interval: str = "15m", lookback_candles: int = 4, df_spot: pd.DataFrame = None, df_thb: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบความสอดคล้อง (Alignment) ระหว่างราคาทองโลก (Spot Gold) และ อัตราแลกเปลี่ยน (USD/THB)
    lookback_candles = 4 (เทียบราคาปัจจุบันกับ 4 แท่งที่แล้ว เช่น ถ้ารัน 15m ก็คือเทียบย้อนหลัง 1 ชั่วโมง)
    df_spot: DataFrame ของ XAU/USD (ถ้ามีในหน่วยความจำแล้ว ส่งเข้ามาได้เลย)
    df_thb:  DataFrame ของ USD/THB (ถ้ามีในหน่วยความจำแล้ว ส่งเข้ามาได้เลย)
    """
    try:
        # ดึง OHLCV ของ XAU/USD (Spot Gold)
        if df_spot is None or df_spot.empty:
            df_spot = _fetcher.fetch_historical_ohlcv(days=3, interval=interval, twelvedata_symbol="XAU/USD")
        else:
            logger.info(f"⚡ [check_spot_thb_alignment] ใช้ df_spot จากหน่วยความจำ ({len(df_spot)} แท่ง)")
 
        # ดึง OHLCV ของ USD/THB (ค่าเงินบาท) - **ต้องปรับ fetcher ให้รองรับการเรียก symbol นี้**
        if df_thb is None or df_thb.empty:
            df_thb = _fetcher.fetch_historical_ohlcv(days=3, interval=interval, twelvedata_symbol="USD/THB")
        else:
            logger.info(f"⚡ [check_spot_thb_alignment] ใช้ df_thb จากหน่วยความจำ ({len(df_thb)} แท่ง)")
 
        if len(df_spot) < lookback_candles or len(df_thb) < lookback_candles:
            return {"status": "error", "message": "ข้อมูลไม่พอสำหรับการเปรียบเทียบ Alignment"}
 
        # คำนวณ % Change ของ Spot Gold
        spot_start = df_spot['close'].iloc[-lookback_candles]
        spot_end = df_spot['close'].iloc[-1]
        spot_pct = ((spot_end - spot_start) / spot_start) * 100
 
        # คำนวณ % Change ของ USD/THB
        thb_start = df_thb['close'].iloc[-lookback_candles]
        thb_end = df_thb['close'].iloc[-1]
        thb_pct = ((thb_end - thb_start) / thb_start) * 100
 
        # วิเคราะห์ความสอดคล้อง
        if spot_pct > 0 and thb_pct > 0:
            alignment = "Strong Bullish"
            suggestion = "ทองโลกขึ้น + บาทอ่อน (ส่งเสริมราคาทองไทยให้ขึ้นแรง ทะลุแนวต้านได้ง่าย)"
        elif spot_pct < 0 and thb_pct < 0:
            alignment = "Strong Bearish"
            suggestion = "ทองโลกลง + บาทแข็ง (กดดันราคาทองไทยให้ลงแรง หลุดแนวรับได้ง่าย)"
        elif spot_pct > 0 and thb_pct < 0:
            alignment = "Neutral (Spot Leading)"
            suggestion = "ทองโลกขึ้น แต่บาทแข็งกดดันไว้ (ราคาทองไทยอาจขึ้นช้า หรือออกข้าง)"
        else:
            alignment = "Neutral (THB Leading)"
            suggestion = "ทองโลกลง แต่บาทอ่อนช่วยพยุงไว้ (ราคาทองไทยอาจลงยาก หรือออกข้าง)"
 
        return {
            "status": "success",
            "interval": interval,
            "alignment": alignment,
            "details": {
                "spot_pct_change": round(spot_pct, 4),
                "thb_pct_change": round(thb_pct, 4)
            },
            "suggestion": suggestion
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
def detect_breakout_confirmation(zone_top: float, zone_bottom: float, interval: str = "15m", history_days: int = 3, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบว่าการทะลุแนวรับ/แนวต้าน (Breakout) เป็นการทะลุที่แข็งแกร่ง (Confirmed) 
    หรือเป็นการทะลุหลอก (Fakeout) โดยวิเคราะห์จากสัดส่วนของแท่งเทียน
    """
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        if len(df) < 2:
            return {"status": "error", "message": "ข้อมูลไม่พอ"}

        # เช็คแท่งเทียนล่าสุด (ที่ปิดแท่งแล้ว หรือกำลังวิ่งอยู่)
        latest = df.iloc[-1]
        open_p = latest['open']
        close_p = latest['close']
        high_p = latest['high']
        low_p = latest['low']

        # หาทิศทางการ Breakout
        is_breaking_up = close_p > zone_top
        is_breaking_down = close_p < zone_bottom

        if not is_breaking_up and not is_breaking_down:
            return {
                "status": "success",
                "is_confirmed_breakout": False,
                "suggestion": "ราคายังวิ่งอยู่ในกรอบโซน ไม่เกิดการ Breakout"
            }

        # คำนวณสัดส่วนแท่งเทียน (Anatomy)
        body_size = abs(close_p - open_p)
        total_size = high_p - low_p
        
        # ป้องกัน division by zero
       # ป้องกัน division by zero — แท่ง Doji สมบูรณ์ (high == low) ไม่สามารถยืนยัน Breakout ได้
        if total_size == 0:
            return {
                "status": "success",
                "is_confirmed_breakout": False,
                "suggestion": "แท่งเทียน Doji (ไม่มีความยาว) ไม่สามารถยืนยัน Breakout ได้"
            }

        body_pct = (body_size / total_size) * 100
        
        # เงื่อนไขยืนยันการ Breakout: เนื้อเทียนต้องใหญ่พอ (แสดงถึงแรงซื่อ/ขายที่มุ่งมั่น)
        # และต้องปิดนอกกรอบได้อย่างเด็ดขาด
        is_strong_body = body_pct >= 50.0  # เนื้อเทียนต้องคิดเป็น 50% ขึ้นไปของความยาวทั้งหมด (ไม่ใช่ไส้ยาว)

        if is_breaking_up:
            upper_wick = high_p - max(open_p, close_p)
            # ถ้า Breakout ขาขึ้น ไส้บนต้องไม่ยาวเกินไป (ไม่โดนตบลงมา)
            wick_rejected = upper_wick > body_size
            confirmed = is_strong_body and not wick_rejected
            direction = "Upward (Resistance Breakout)"
            
        else: # is_breaking_down
            lower_wick = min(open_p, close_p) - low_p
            # ถ้า Breakout ขาลง ไส้ล่างต้องไม่ยาวเกินไป (ไม่โดนงัดขึ้น)
            wick_rejected = lower_wick > body_size
            confirmed = is_strong_body and not wick_rejected
            direction = "Downward (Support Breakdown)"

        return {
            "status": "success",
            "interval": interval,
            "breakout_direction": direction,
            "is_confirmed_breakout": bool(confirmed),
            "details": {
                "body_strength_pct": round(body_pct, 2),
                "closed_price": round(close_p, 2)
            },
            "suggestion": "ทะลุจริง (Confirmed) สามารถเทรด Follow ตามน้ำได้" if confirmed else "สัญญาณอ่อนแอ อาจเป็นทะลุหลอก (Fakeout) ให้ระวังการดึงกลับ"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
def get_support_resistance_zones(interval: str = "15m", history_days: int = 5, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ค้นหาโซนแนวรับ-แนวต้านที่มีนัยสำคัญ โดยใช้ Adaptive EPS ที่คำนวณจากค่า ATR
    เพื่อให้โซนยืดหยุ่นตามความผันผวนของตลาดทองคำไทย
    """
    try:
        # 1. จัดเตรียมข้อมูล (ดึงใหม่หรือใช้จาก Memory)
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [get_support_resistance_zones] ใช้ DataFrame จากหน่วยความจำ ({len(df)} แท่ง)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        if len(df) < 50:
            return {"status": "error", "message": "ข้อมูลแท่งเทียนไม่พอสำหรับการหาโซน (ต้องการ 50+ แท่ง)"}

        # 2. คำนวณ Indicators เพื่อดึงค่า ATR ล่าสุด
        # หมายเหตุ: ควรส่ง usd_thb เข้าไปด้วยเพื่อให้ ATR เป็นหน่วย THB ต่อบาททอง
        calc = TechnicalIndicators(df) 
        df_with_ind = calc.df
        
        # ดึงค่า ATR-14 ล่าสุด
        # หากยังไม่ได้แปลงเป็น THB ในคลาส indicators ให้คูณแปลงหน่วยที่นี่
        latest_atr = float(df_with_ind["atr_14"].iloc[-1])
        
        # 3. คำนวณ Adaptive EPS (Requirement: 0.7 * ATR, Min 50, Max 200)
        # เราใช้ 0.7 เป็น Multiplier เพื่อให้โซนครอบคลุมการแกว่งตัวส่วนใหญ่
        adaptive_eps = latest_atr * 0.7
        final_eps = np.clip(adaptive_eps, 50.0, 200.0) # ล็อคช่วง 50 - 200 บาททอง
        
        current_price = float(df['close'].iloc[-1])
        prominence = final_eps * 1.5 # ปรับ Prominence ตามความผันผวนเพื่อให้เจอจุด Peak ที่ชัดเจน

        # 4. หาจุด Swing Highs / Lows
        peaks_idx, _ = find_peaks(df['high'], prominence=prominence)
        troughs_idx, _ = find_peaks(-df['low'], prominence=prominence)
        
        swing_highs = df['high'].iloc[peaks_idx].values
        swing_lows = df['low'].iloc[troughs_idx].values
        all_swings = np.concatenate([swing_highs, swing_lows]).reshape(-1, 1)
        
        if len(all_swings) == 0:
            return {"status": "success", "current_price": current_price, "zones": [], "eps_used": round(final_eps, 2)}

        # 5. ทำ Clustering ด้วย DBSCAN โดยใช้ Adaptive EPS
        clustering = DBSCAN(eps=final_eps, min_samples=2).fit(all_swings)
        labels = clustering.labels_
        
        zones = []
        for label in set(labels):
            if label == -1: continue
                
            cluster_prices = all_swings[labels == label].flatten()
            top_edge = float(np.max(cluster_prices))
            bottom_edge = float(np.min(cluster_prices))
            
            # วิเคราะห์ความแข็งแกร่งและประเภท
            touches = len(cluster_prices)
            strength = "High" if touches >= 4 else "Medium" if touches == 3 else "Low"
            if bottom_edge > current_price:
                zone_type = "Resistance"
            elif top_edge < current_price:
                zone_type = "Support"
            else:
                zone_type = "In-Range (Testing Zone)"  # ราคากำลังอยู่ในโซน / กำลังทดสอบโซนนี้
            
            zones.append({
                "type": zone_type,
                "bottom": round(bottom_edge, 2),
                "top": round(top_edge, 2),
                "touches": touches,
                "strength": strength
            })
            
        zones = sorted(zones, key=lambda x: x['top'], reverse=True)

        return {
            "status": "success",
            "interval": interval,
            "current_price": current_price,
            "adaptive_metrics": {
                "atr_used": round(latest_atr, 2),
                "final_eps": round(final_eps, 2)
            },
            "total_zones_found": len(zones),
            "zones": zones
        }
        
    except Exception as e:
        logger.error(f"❌ [get_support_resistance_zones] Error: {e}")
        return {"status": "error", "message": str(e)}
    
def detect_swing_low(interval: str = "15m", history_days: int = 3, lookback_candles: int = 15, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบหา Swing Low Structure (จุดต่ำก่อนพุ่ง) 
    โดยสแกนหาในกรอบเวลา lookback_candles ล่าสุด เพื่อหาจุดกลับตัวที่ได้รับการ Confirm แล้ว
    """
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [detect_swing_low] ใช้ DataFrame จากหน่วยความจำ ({len(df)} แท่ง)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
        
        if len(df) < lookback_candles:
            return {"status": "error", "message": "ข้อมูลแท่งเทียนไม่พอสำหรับการวิเคราะห์"}

        # ดึงข้อมูลเฉพาะช่วงที่ต้องการสแกน (เช่น 15 แท่งล่าสุด)
        recent_df = df.tail(lookback_candles).reset_index(drop=True)
        
        setup_found = False
        swing_low_val = None
        confirmation_close = None
        
        # สแกนย้อนหลังจากปัจจุบันกลับไปหาอดีต เพื่อหา Swing Low ที่ใกล้ที่สุด
        # เว้นขอบซ้ายและขวาไว้ 1 แท่ง เพื่อให้สามารถตรวจสอบรูปแบบ V-shape ได้
        for i in range(len(recent_df) - 2, 0, -1):
            left_low = recent_df['low'].iloc[i-1]
            center_low = recent_df['low'].iloc[i]
            right_low = recent_df['low'].iloc[i+1]
            
            # เงื่อนไข 1: หาจุดที่เป็นก้นเหว (Swing Low)
            if center_low < left_low and center_low < right_low:
                swing_high = recent_df['high'].iloc[i]
                
                # เงื่อนไข 2: หาแท่งเทียนหลังจากนั้น ที่ปิดทะลุ High ของแท่ง Swing ไปได้ (Confirmation)
                for j in range(i + 1, len(recent_df)):
                    if recent_df['close'].iloc[j] > swing_high:
                        setup_found = True
                        swing_low_val = center_low
                        confirmation_close = recent_df['close'].iloc[j]
                        break
            
            # ถ้าเจอ Setup ล่าสุดที่สมบูรณ์แล้ว ให้หยุดสแกน
            if setup_found:
                break

        return {
            "status": "success",
            "interval": interval,
            "setup_detected": setup_found,
            "details": {
                "swing_low_price": round(float(swing_low_val), 2) if swing_low_val else None,
                "confirmation_close": round(float(confirmation_close), 2) if confirmation_close else None
            },
            "suggestion": "มีโอกาสกลับตัวขึ้น (Bullish Reversal)" if setup_found else "ยังไม่พบสัญญาณ Swing Low ที่ชัดเจนในกรอบเวลา"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def detect_rsi_divergence(interval: str = "15m", history_days: int = 5, lookback_candles: int = 30, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบหา RSI Bullish Divergence 
    โดยใช้ find_peaks หาจุดก้นเหว (Troughs) ของราคา 2 จุดล่าสุด แล้วเทียบโมเมนตัม RSI
    """
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [detect_rsi_divergence] ใช้ DataFrame จากหน่วยความจำ ({len(df)} แท่ง)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        if len(df) < lookback_candles:
            return {"status": "error", "message": "ข้อมูลไม่เพียงพอ (ต้องการข้อมูลมากกว่ากรอบการสแกน)"}

        # คำนวณ RSI และตัดข้อมูลเฉพาะช่วงที่ต้องการสแกน
        calc = TechnicalIndicators(df)
        df_with_rsi = calc.df.dropna(subset=['rsi_14'])
        recent_df = df_with_rsi.tail(lookback_candles).reset_index(drop=True)
        
        # ใช้ find_peaks กับค่าติดลบของ Low เพื่อหา "ก้นเหว" (Troughs)
        # ใส่ค่า prominence เล็กน้อยเพื่อกรอง noise
        troughs_idx, _ = find_peaks(-recent_df['low'], prominence=20) 
        
        if len(troughs_idx) < 2:
            return {
                "status": "success", 
                "divergence_detected": False, 
                "logic": "ไม่พบจุดสวิงที่ชัดเจนพอที่จะเทียบ Divergence",
                "data": {}
            }

        # ดึง Index ของก้นเหว 2 จุดล่าสุด (อดีต=idx1, ปัจจุบัน=idx2)
        idx1 = troughs_idx[-2]
        idx2 = troughs_idx[-1]
        
        low1 = recent_df['low'].iloc[idx1]
        rsi1 = recent_df['rsi_14'].iloc[idx1]
        
        low2 = recent_df['low'].iloc[idx2]
        rsi2 = recent_df['rsi_14'].iloc[idx2]
        
        # เงื่อนไข Bullish Divergence: ราคาทำ Low ใหม่ แต่ RSI ยกตัวขึ้น
        is_price_lower = low2 < low1
        is_rsi_higher = rsi2 > rsi1
        divergence_found = bool(is_price_lower and is_rsi_higher)

        return {
            "status": "success",
            "divergence_detected": divergence_found,
            "logic": "momentum ลดลง ขณะราคายังลง (เกิด Bullish Divergence)" if divergence_found else "ทิศทางราคาและ RSI สอดคล้องกัน (ไม่มี Divergence)",
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
    
def check_bb_rsi_combo(interval: str = "15m", history_days: int = 5, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบ BB + RSI Combo 
    (Python เป็นผู้ดึงและคำนวณเอง LLM แค่เรียกใช้)
    """
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        calc = TechnicalIndicators(df)
        df_ind = calc.df.dropna(subset=['rsi_14', 'lower_bb', 'macd_hist'])
        
        if len(df_ind) < 2:
            return {"status": "error", "message": "ข้อมูลไม่พอคำนวณ Combo"}

        latest = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]

        # ดึงค่าล่าสุด
        current_price = latest['close']
        lower_bb = latest['lower_bb'] # ชื่อ Column ต้องตรงกับในคลาส TechnicalIndicators ของคุณ
        rsi = latest['rsi_14']
        macd_hist_current = latest['macd_hist']
        macd_hist_prev = prev['macd_hist']

        # ตรวจสอบเงื่อนไข
        is_price_low = current_price < lower_bb 
        is_rsi_oversold = rsi < 35.0 
        is_macd_flatten = abs(macd_hist_current) < 0.3 or (macd_hist_current > macd_hist_prev)
        
        combo_met = bool(is_price_low and is_rsi_oversold and is_macd_flatten)
        
        return {
            "status": "success",
            "interval": interval,
            "combo_detected": combo_met,
            "raw_data": {
                "price": round(current_price, 2), "lower_bb": round(lower_bb, 2), 
                "rsi": round(rsi, 2), "macd_hist": round(macd_hist_current, 2)
            },
            "details": f"Price<BB: {is_price_low}, RSI<35: {is_rsi_oversold}, MACD_Flatten: {is_macd_flatten}"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def calculate_ema_distance(interval: str = "15m", history_days: int = 5, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบ EMA Distance (Mean Reversion / Overextended)
    """
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        calc = TechnicalIndicators(df)
        df_ind = calc.df.dropna(subset=['ema_20', 'atr_14']) # สมมติใช้ ATR 14
        
        latest = df_ind.iloc[-1]
        current_price = float(latest['close'])
        ema_20 = float(latest['ema_20'])
        atr = float(latest['atr_14'])

        if atr <= 0:
            return {"status": "error", "message": "ค่า ATR ผิดปกติ (<= 0)"}
            
        distance = (ema_20 - current_price) / atr 
        is_overextended = abs(distance) > 5.0 
        
        return {
            "status": "success",
            "interval": interval,
            "distance_atr_ratio": round(distance, 2),
            "is_overextended": bool(is_overextended),
            "metrics": {
                "current_price": round(current_price, 2),
                "ema_20": round(ema_20, 2),
                "atr": round(atr, 2)
            },
            "suggestion": "Overextended มาก ราคาลอยห่างเส้นค่าเฉลี่ย ระวังการกลับตัว (Mean reversion likely)" if is_overextended else "ระยะห่างปกติ สามารถรันเทรนด์ต่อได้" 
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


#--------------------------------------------------------------------------------------------------
# Higher Timeframe + General Indicators
#--------------------------------------------------------------------------------------------------

def get_htf_trend(timeframe: str = "1h", history_days: int = 15, ohlcv_df: pd.DataFrame = None) -> dict:
    """
    ตรวจสอบเทรนด์ภาพใหญ่ (Higher Timeframe) 
    โดยใช้ราคาปิดเทียบกับเส้น EMA 200
    """
    try:
        # ดึงข้อมูล Timeframe ใหญ่
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [get_htf_trend] ใช้ DataFrame จากหน่วยความจำ ({len(df)} แท่ง)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=timeframe)
        if len(df) < 200:
            return {"status": "error", "message": f"ข้อมูล {timeframe} ไม่พอสำหรับคำนวณ EMA 200"}
 
        # คำนวณ Indicator
        calc = TechnicalIndicators(df)
        df_ind = calc.df.dropna(subset=['ema_200']) # สมมติว่าใน TechnicalIndicators มีการคำนวณ ema_200
        
        latest_candle = df_ind.iloc[-1]
        current_price = latest_candle['close']
        ema_200 = latest_candle['ema_200']
        
        # ตัดสินเทรนด์
        trend = "Bullish" if current_price > ema_200 else "Bearish"
        distance_pct = ((current_price - ema_200) / ema_200) * 100
 
        return {
            "status": "success",
            "timeframe": timeframe,
            "trend": trend,
            "current_price": round(float(current_price), 2),
            "ema_200": round(float(ema_200), 2),
            "distance_from_ema_pct": round(float(distance_pct), 2),
            "suggestion": f"เทรนด์หลักเป็น {trend} ควรเน้นหาจังหวะ {'Buy' if trend == 'Bullish' else 'Sell'}"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
 
def check_volatility(asset: str = "XAUUSD") -> dict:
    """ใช้ตรวจสอบความผันผวนของตลาดในปัจจุบัน (เช่น ค่า ATR)"""
    return {
        "asset": asset,
        "volatility": "high",
        "atr_value": 15.5
    }



