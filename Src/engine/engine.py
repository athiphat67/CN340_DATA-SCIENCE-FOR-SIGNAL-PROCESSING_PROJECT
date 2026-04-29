import numpy as np
import pandas as pd
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────
GOLD_BAHT_TO_GRAM: float = 15.244

class GoldFeatureWatcher:
    """
    Watcher ด่านแรก: ทำหน้าที่รับ Raw Data และแปลงเป็น 26 Feature Columns 
    เพื่อส่งให้ Dual-Model โดยเฉพาะ (Stateless Transformation)
    """

    def __init__(self, data_orchestrator):
        self.data_orchestrator = data_orchestrator
        # รายชื่อ Feature ให้ตรงกับ feature_columns.json
        self.feature_names = [
            "xauusd_open", "xauusd_high", "xauusd_low", "xauusd_close",
            "xauusd_ret1", "xauusd_ret3", "usdthb_ret1", "xau_macd_delta1",
            "xauusd_dist_ema21", "xauusd_dist_ema50", "usdthb_dist_ema21",
            "trend_regime", "xauusd_rsi14", "xau_rsi_delta1", "xauusd_macd_hist",
            "xauusd_atr_norm", "xauusd_bb_width", "atr_rank50", "wick_bias",
            "body_strength", "hour_sin", "hour_cos", "minute_sin", "minute_cos",
            "session_progress", "day_of_week"
        ]

    def get_latest_feature_set(self) -> Optional[Dict[str, Any]]:
        """
        ฟังก์ชันหลักที่ภายนอกจะเรียกใช้ เพื่อดึง 'ชุดคุณลักษณะ' ล่าสุด
        """
        try:
            # 1. Fetch Raw Data (OHLCV + Indicators)
            market_state = self.data_orchestrator.run(history_days=3, interval="5m")
            
            if not self._is_data_valid(market_state):
                return None

            # 2. Extract & Compute Features
            features = self._compute_all_features(market_state)
            
            return features
        except Exception as e:
            logger.error(f"Error generating features: {e}")
            return None

    def _compute_all_features(self, market_state: dict) -> Dict[str, Any]:
        """คำนวณ 26 Features ตามสเปก feature_columns.json"""
        
        # เตรียมข้อมูลเบื้องต้น
        candles = market_state.get("market_data", {}).get("candles", [])
        ti = market_state.get("technical_indicators", {})
        df = pd.DataFrame(candles) # ใช้ DataFrame ช่วยคำนวณ Rolling/Shift
        
        # ข้อมูล USDTHB (ถ้ามี)
        usdthb_price = market_state.get("market_data", {}).get("usd_thb", {}).get("rate", 35.0)
        
        # --- 1. Price & Returns ---
        last_close = float(df['close'].iloc[-1])
        xau_ret1 = (df['close'].iloc[-1] / df['close'].iloc[-2]) - 1
        xau_ret3 = (df['close'].iloc[-1] / df['close'].iloc[-4]) - 1
        
        # --- 2. Technical Indicators (ดึงจาก TechnicalIndicators service) ---
        rsi = ti.get("rsi", {}).get("value", 50.0)
        rsi_prev = ti.get("rsi", {}).get("prev_value", 50.0)
        macd_hist = ti.get("macd", {}).get("histogram", 0.0)
        macd_hist_prev = ti.get("macd", {}).get("prev_histogram", 0.0)
        
        # --- 3. Distances & Regimes ---
        # สมมติว่า ti มีค่าเหล่านี้มาให้ หรือคำนวณเองจาก df
        ema21 = df['close'].ewm(span=21).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        
        # --- 4. Candlestick Metrics ---
        high, low, open_p, close_p = df['high'].iloc[-1], df['low'].iloc[-1], df['open'].iloc[-1], df['close'].iloc[-1]
        wick_bias = (high - max(open_p, close_p)) - (min(open_p, close_p) - low)
        body_strength = abs(close_p - open_p) / (high - low) if (high - low) > 0 else 0
        
        # --- 5. Time Features (Cyclical Encoding) ---
        now = datetime.now()
        h, m = now.hour, now.minute
        
        # แปลงเวลาเป็น Sin/Cos เพื่อให้ Model เห็นความต่อเนื่อง 23:59 -> 00:00
        hour_sin = np.sin(2 * np.pi * h / 24)
        hour_cos = np.cos(2 * np.pi * h / 24)
        
        # --- 6. รวบรวมข้อมูลตามชื่อ Column เป๊ะๆ ---
        feature_dict = {
            "xauusd_open": float(open_p),
            "xauusd_high": float(high),
            "xauusd_low": float(low),
            "xauusd_close": float(close_p),
            "xauusd_ret1": xau_ret1,
            "xauusd_ret3": xau_ret3,
            "usdthb_ret1": 0.0, # ดึงจากประวัติ USDTHB
            "xau_macd_delta1": macd_hist - macd_hist_prev,
            "xauusd_dist_ema21": (close_p - ema21) / ema21,
            "xauusd_dist_ema50": (close_p - ema50) / ema50,
            "usdthb_dist_ema21": 0.0,
            "trend_regime": 1 if close_p > ema50 else 0,
            "xauusd_rsi14": rsi,
            "xau_rsi_delta1": rsi - rsi_prev,
            "xauusd_macd_hist": macd_hist,
            "xauusd_atr_norm": ti.get("atr", {}).get("value", 0.0) / last_close,
            "xauusd_bb_width": ti.get("bollinger", {}).get("width", 0.0),
            "atr_rank50": 0.5, # ค่า Rank ในหน้าต่าง 50 บาร์
            "wick_bias": wick_bias,
            "body_strength": body_strength,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "minute_sin": np.sin(2 * np.pi * m / 60),
            "minute_cos": np.cos(2 * np.pi * m / 60),
            "session_progress": self._get_session_progress(now), #
            "day_of_week": now.weekday()
        }
        
        return feature_dict

    def _get_session_progress(self, dt: datetime) -> float:
        """คำนวณว่าเวลาปัจจุบันผ่านไปกี่ % ของ Session นั้นๆ"""
        # Logic เดียวกับใน model_using.md ข้อ 6.2
        # (Current_Secs - Start_Secs) / Total_Duration
        return 0.5 # ค่าตัวอย่าง

    def _is_data_valid(self, market_state: dict) -> bool:
        candles = market_state.get("market_data", {}).get("candles", [])
        return len(candles) >= 50

    # ─── Export Function ───────────────────────────────────────────────────

    def export_to_model(self) -> Dict[str, Any]:
        """
        ทำหน้าที่เป็นตัวส่ง Output ออกไปข้างนอก 
        เพื่อเตรียมเข้าสู่กระบวนการ Dual-Model Prediction
        """
        data = self.get_latest_feature_set()
        if not data:
            return {"status": "error", "message": "Failed to generate features"}
            
        # สร้างเป็น Row format ที่ Model ต้องการ
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "feature_vector": [data[k] for k in self.feature_names],
            "feature_dict": data
        }