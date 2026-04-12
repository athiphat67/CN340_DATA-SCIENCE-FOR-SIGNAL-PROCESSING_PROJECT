import logging
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import DBSCAN
from data_engine.ohlcv_fetcher import OHLCVFetcher
from data_engine.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

# Shared fetcher instance
_fetcher = OHLCVFetcher()

#--------------------------------------------------------------------------------------------------
# Group A Tools (Requires Candle Series) 
#--------------------------------------------------------------------------------------------------
def check_spot_thb_alignment(interval: str = "15m", lookback_candles: int = 4, df_spot: pd.DataFrame = None, df_thb: pd.DataFrame = None) -> dict:
    try:
        if df_spot is None or df_spot.empty:
            df_spot = _fetcher.fetch_historical_ohlcv(days=3, interval=interval, twelvedata_symbol="XAU/USD")
        else:
            logger.info(f"⚡ [check_spot_thb_alignment] Using memory df_spot ({len(df_spot)} candles)")
 
        if df_thb is None or df_thb.empty:
            df_thb = _fetcher.fetch_historical_ohlcv(days=3, interval=interval, twelvedata_symbol="USD/THB")
        else:
            logger.info(f"⚡ [check_spot_thb_alignment] Using memory df_thb ({len(df_thb)} candles)")
 
        if len(df_spot) < lookback_candles or len(df_thb) < lookback_candles:
            return {"status": "error", "message": "Insufficient data for alignment comparison"}
 
        spot_start = df_spot['close'].iloc[-lookback_candles]
        spot_end = df_spot['close'].iloc[-1]
        spot_pct = ((spot_end - spot_start) / spot_start) * 100
 
        thb_start = df_thb['close'].iloc[-lookback_candles]
        thb_end = df_thb['close'].iloc[-1]
        thb_pct = ((thb_end - thb_start) / thb_start) * 100
 
        if spot_pct > 0 and thb_pct > 0:
            alignment = "Strong Bullish"
            suggestion = "Spot UP & THB Weak (Bullish for Thai Gold)"
        elif spot_pct < 0 and thb_pct < 0:
            alignment = "Strong Bearish"
            suggestion = "Spot DOWN & THB Strong (Bearish for Thai Gold)"
        elif spot_pct > 0 and thb_pct < 0:
            alignment = "Neutral (Spot Leading)"
            suggestion = "Spot UP & THB Strong (Slow rise or ranging)"
        else:
            alignment = "Neutral (THB Leading)"
            suggestion = "Spot DOWN & THB Weak (Slow drop or ranging)"
 
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
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        if len(df) < 2:
            return {"status": "error", "message": "Insufficient data"}

        latest = df.iloc[-1]
        open_p = latest['open']
        close_p = latest['close']
        high_p = latest['high']
        low_p = latest['low']

        is_breaking_up = close_p > zone_top
        is_breaking_down = close_p < zone_bottom

        if not is_breaking_up and not is_breaking_down:
            return {
                "status": "success",
                "is_confirmed_breakout": False,
                "suggestion": "Price ranging inside zone, no breakout"
            }

        body_size = abs(close_p - open_p)
        total_size = high_p - low_p
        
        if total_size == 0:
            return {
                "status": "success",
                "is_confirmed_breakout": False,
                "suggestion": "Doji candle detected, cannot confirm breakout"
            }

        body_pct = (body_size / total_size) * 100
        is_strong_body = body_pct >= 50.0 

        if is_breaking_up:
            upper_wick = high_p - max(open_p, close_p)
            wick_rejected = upper_wick > body_size
            confirmed = is_strong_body and not wick_rejected
            direction = "Upward (Resistance Breakout)"
        else:
            lower_wick = min(open_p, close_p) - low_p
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
            "suggestion": "Confirmed breakout, safe to follow trend" if confirmed else "Weak signal, potential fakeout"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
def get_support_resistance_zones(interval: str = "15m", history_days: int = 5, ohlcv_df: pd.DataFrame = None) -> dict:
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [get_support_resistance_zones] Using memory df ({len(df)} candles)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        if len(df) < 50:
            return {"status": "error", "message": "Insufficient candles for zone detection (needs 50+)"}

        calc = TechnicalIndicators(df) 
        df_with_ind = calc.df
        
        latest_atr = float(df_with_ind["atr_14"].iloc[-1])
        adaptive_eps = latest_atr * 0.7
        final_eps = np.clip(adaptive_eps, latest_atr * 0.3, latest_atr * 3.0)

        current_price = float(df['close'].iloc[-1])
        prominence = latest_atr * 1.5

        peaks_idx, _ = find_peaks(df['high'], prominence=prominence)
        troughs_idx, _ = find_peaks(-df['low'], prominence=prominence)
        
        swing_highs = df['high'].iloc[peaks_idx].values
        swing_lows = df['low'].iloc[troughs_idx].values
        all_swings = np.concatenate([swing_highs, swing_lows]).reshape(-1, 1)
        
        if len(all_swings) == 0:
            return {"status": "success", "current_price": current_price, "zones": [], "eps_used": round(final_eps, 2)}

        clustering = DBSCAN(eps=final_eps, min_samples=2).fit(all_swings)
        labels = clustering.labels_
        
        zones = []
        for label in set(labels):
            if label == -1: continue
                
            cluster_prices = all_swings[labels == label].flatten()
            top_edge = float(np.max(cluster_prices))
            bottom_edge = float(np.min(cluster_prices))
            
            touches = len(cluster_prices)
            strength = "High" if touches >= 4 else "Medium" if touches == 3 else "Low"
            if bottom_edge > current_price:
                zone_type = "Resistance"
            elif top_edge < current_price:
                zone_type = "Support"
            else:
                zone_type = "In-Range (Testing Zone)"
            
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
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [detect_swing_low] Using memory df ({len(df)} candles)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
        
        if len(df) < lookback_candles:
            return {"status": "error", "message": "Insufficient candles for analysis"}

        recent_df = df.tail(lookback_candles).reset_index(drop=True)
        
        setup_found = False
        swing_low_val = None
        confirmation_close = None
        
        for i in range(len(recent_df) - 2, 0, -1):
            left_low = recent_df['low'].iloc[i-1]
            center_low = recent_df['low'].iloc[i]
            right_low = recent_df['low'].iloc[i+1]
            
            if center_low < left_low and center_low < right_low:
                swing_high = recent_df['high'].iloc[i]
                
                for j in range(i + 1, len(recent_df)):
                    if recent_df['close'].iloc[j] > swing_high:
                        setup_found = True
                        swing_low_val = center_low
                        confirmation_close = recent_df['close'].iloc[j]
                        break
            
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
            "suggestion": "Potential Bullish Reversal" if setup_found else "No clear swing low detected"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def detect_rsi_divergence(interval: str = "15m", history_days: int = 5, lookback_candles: int = 30, ohlcv_df: pd.DataFrame = None) -> dict:
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [detect_rsi_divergence] Using memory df ({len(df)} candles)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        if len(df) < lookback_candles:
            return {"status": "error", "message": "Insufficient data (needs more than lookback window)"}

        calc = TechnicalIndicators(df)
        df_with_rsi = calc.df.dropna(subset=['rsi_14'])
        recent_df = df_with_rsi.tail(lookback_candles).reset_index(drop=True)

        atr = float(calc.df['atr_14'].iloc[-1])
        troughs_idx, _ = find_peaks(-recent_df['low'], prominence=atr * 1.0)
        
        if len(troughs_idx) < 2:
            return {
                "status": "success", 
                "divergence_detected": False, 
                "logic": "No clear swings to compare divergence",
                "data": {}
            }

        idx1 = troughs_idx[-2]
        idx2 = troughs_idx[-1]
        
        low1 = recent_df['low'].iloc[idx1]
        rsi1 = recent_df['rsi_14'].iloc[idx1]
        
        low2 = recent_df['low'].iloc[idx2]
        rsi2 = recent_df['rsi_14'].iloc[idx2]
        
        is_price_lower = low2 < low1
        is_rsi_higher = rsi2 > rsi1
        divergence_found = bool(is_price_lower and is_rsi_higher)

        return {
            "status": "success",
            "divergence_detected": divergence_found,
            "logic": "Price lower but RSI higher (Bullish Divergence)" if divergence_found else "Price and RSI aligned (No Divergence)",
            "data": {
                "Low1": round(float(low1), 2), "RSI1": round(float(rsi1), 2),
                "Low2": round(float(low2), 2), "RSI2": round(float(rsi2), 2)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
#--------------------------------------------------------------------------------------------------
# Group B Tools (Snapshot + Threshold) 
#--------------------------------------------------------------------------------------------------
    
def check_bb_rsi_combo(interval: str = "15m", history_days: int = 5, ohlcv_df: pd.DataFrame = None) -> dict:
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        calc = TechnicalIndicators(df)
        df_ind = calc.df.dropna(subset=['rsi_14', 'bb_low', 'macd_hist'])
        
        if len(df_ind) < 2:
            return {"status": "error", "message": "Insufficient data for combo calculation"}

        latest = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]

        current_price = latest['close']
        lower_bb = latest['bb_low']
        rsi = latest['rsi_14']
        macd_hist_current = latest['macd_hist']
        macd_hist_prev = prev['macd_hist']
        atr = float(latest['atr_14'])

        is_price_low = current_price < lower_bb
        is_rsi_oversold = rsi < 35.0
        is_macd_flatten = abs(macd_hist_current) < (atr * 0.05) or (macd_hist_current > macd_hist_prev)
        
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
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=interval)
            
        calc = TechnicalIndicators(df)
        df_ind = calc.df.dropna(subset=['ema_20', 'atr_14']) 
        
        latest = df_ind.iloc[-1]
        current_price = float(latest['close'])
        ema_20 = float(latest['ema_20'])
        atr = float(latest['atr_14'])

        if atr <= 0:
            return {"status": "error", "message": "Invalid ATR value (<= 0)"}
            
        distance = (current_price - ema_20) / atr
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
            "suggestion": "Highly overextended, mean reversion likely" if is_overextended else "Normal distance, trend continuation possible" 
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

#--------------------------------------------------------------------------------------------------
# Higher Timeframe + General Indicators
#--------------------------------------------------------------------------------------------------

def get_htf_trend(timeframe: str = "1h", history_days: int = 15, ohlcv_df: pd.DataFrame = None) -> dict:
    try:
        if ohlcv_df is not None and not ohlcv_df.empty:
            df = ohlcv_df
            logger.info(f"⚡ [get_htf_trend] Using memory df ({len(df)} candles)")
        else:
            df = _fetcher.fetch_historical_ohlcv(days=history_days, interval=timeframe)
        if len(df) < 200:
            return {"status": "error", "message": f"Insufficient {timeframe} data for EMA 200"}
 
        calc = TechnicalIndicators(df)
        df_ind = calc.df.dropna(subset=['ema_200']) 
        
        latest_candle = df_ind.iloc[-1]
        current_price = latest_candle['close']
        ema_200 = latest_candle['ema_200']
        
        trend = "Bullish" if current_price > ema_200 else "Bearish"
        distance_pct = ((current_price - ema_200) / ema_200) * 100
 
        return {
            "status": "success",
            "timeframe": timeframe,
            "trend": trend,
            "current_price": round(float(current_price), 2),
            "ema_200": round(float(ema_200), 2),
            "distance_from_ema_pct": round(float(distance_pct), 2),
            "suggestion": f"Main trend is {trend}, look for {'Buy' if trend == 'Bullish' else 'Sell'} setups"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
