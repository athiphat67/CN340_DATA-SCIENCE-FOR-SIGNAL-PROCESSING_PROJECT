import pandas as pd
from typing import Dict, Any

class MarketStateBuilder:
    
    @staticmethod
    def build(
        row: pd.Series, 
        past_5_rows: pd.DataFrame, 
        current_time: pd.Timestamp, 
        data_mode: str = "csv_backtest",
        portfolio_dict: dict = None,
        interval: str = "5m"  # ตาม Data ใหม่ที่เป็น 5 นาที
    ) -> dict:
    
        # 1. ดึงราคาทองปัจจบัน (ถ้าเพื่อนไม่ส่ง USD มา จะ fallback เป็น 0.0)
        current_usd = float(row.get("gold_spot_usd", 0.0)) 
        current_thb = float(row.get("sell_price", row.get("close", 0.0)))
        
        # 2. จัดการข้อมูลราคาย้อนหลัง & คำนวณ Price Trend
        recent_price_action = []
        price_trend = {
            "current_usd": current_usd,
            "prev_usd": current_usd,
            "1_bar_chg_pct": 0.0,
            "5_bar_chg_pct": 0.0,
            "10_bar_high": current_usd,
            "10_bar_low": current_usd
        }

        if past_5_rows is not None and not past_5_rows.empty:
            for _, r in past_5_rows.iterrows():
                recent_price_action.append({
                    "datetime": str(r.get("time", r.get("timestamp", ""))), # รองรับทั้ง time และ timestamp
                    "open":  float(r.get("open",  0)),
                    "high":  float(r.get("high",  0)),
                    "low":   float(r.get("low",   0)),
                    "close": float(r.get("close", 0)),
                })
                
            # คำนวณ 1-bar และ 5-bar change (ถ้ามีข้อมูล USD)
            if current_usd > 0:
                try:
                    usd_col = "gold_spot_usd"
                    if usd_col in past_5_rows.columns:
                        prev_usd = float(past_5_rows.iloc[-1][usd_col])
                        oldest_usd = float(past_5_rows.iloc[0][usd_col])
                        
                        price_trend["prev_usd"] = prev_usd
                        if prev_usd > 0:
                            price_trend["1_bar_chg_pct"] = round(((current_usd - prev_usd) / prev_usd) * 100, 2)
                        if oldest_usd > 0:
                            price_trend["5_bar_chg_pct"] = round(((current_usd - oldest_usd) / oldest_usd) * 100, 2)
                        
                        price_trend["10_bar_high"] = max(past_5_rows[usd_col].max(), current_usd)
                        price_trend["10_bar_low"] = min(past_5_rows[usd_col].min(), current_usd)
                except Exception:
                    pass

        # 3. แมป Technical Indicators ตามคอลัมน์ใหม่เป๊ะๆ
        rsi_val = float(row.get("rsi_14", 50))
        rsi_sig = "overbought" if rsi_val > 70 else "oversold" if rsi_val < 30 else "neutral"
        
        macd_hist = float(row.get("macd_hist", 0))
        macd_sig = "bullish" if macd_hist > 0 else "bearish_zone" if macd_hist < 0 else "neutral"

        ema20 = float(row.get("ema_20", 0))
        ema50 = float(row.get("ema_50", 0))
        trend_sig = "uptrend" if ema20 > ema50 else "downtrend" if ema20 < ema50 else "neutral"

        # 4. จัดการ Portfolio
        portfolio = portfolio_dict if portfolio_dict is not None else {}
        cash = portfolio.get("cash", 0.0)
        gold = portfolio.get("gold_grams", 0.0)
        
        portfolio["can_buy"] = "YES" if cash >= 1000.0 else "NO — insufficient cash (min 1,000 THB)"
        portfolio["can_sell"] = "YES" if gold > 0.0001 else "NO — no gold held"

        # 5. จัดการ News จาก Data ใหม่โดยตรง
        news_data = {
            "overall_sentiment": float(row.get("news_overall_sentiment", 0.0)),
            "headlines": str(row.get("news_top_headlines", "")).split(" | ") if pd.notna(row.get("news_top_headlines")) else [],
            "sent_hl_1": float(row.get("sent_hl_1", 0.0)),
            "sent_hl_2": float(row.get("sent_hl_2", 0.0))
        }

        # 6. ประกอบร่าง JSON
        state = {
            "meta": {
                "generated_at": str(current_time),
                "time": current_time.strftime("%H:%M") if isinstance(current_time, pd.Timestamp) else "",
                "data_mode": data_mode
            },
            "market_data": {
                "spot_price_usd": {
                    "price_usd_per_oz": current_usd,
                    "spread_points":    0.0,
                    "source":           "premium_csv"
                },
                "forex": {
                    "usd_thb":        float(row.get("usd_thb", 0.0)), # ใช้ชื่อ usd_thb ใหม่
                    "spread_points":  0.0,
                    "source":         "premium_csv"
                },
                "thai_gold_thb": {
                    "buy_price_thb":  float(row.get("buy_price", 0)), # ใช้ buy_price ใหม่
                    "sell_price_thb": current_thb, # ใช้ sell_price ใหม่
                    "mid_price_thb": float(row.get("close", 0)),
                    "ohlcv": {  
                        "open":   float(row.get("open",  0)),
                        "high":   float(row.get("high",  0)),
                        "low":    float(row.get("low",   0)),
                        "close":  float(row.get("close", 0)),
                        "volume": 0.0, # Data ใหม่ไม่มี Volume
                    },
                    "source":            "mock_hsh_csv",
                    "timestamp":         str(current_time)
                },
                "recent_price_action": recent_price_action,
                "price_trend": price_trend 
            },
            "technical_indicators": {
                "rsi": {"value": rsi_val, "signal": rsi_sig},
                "macd": {
                    "macd_line": float(row.get("macd_line", 0)),
                    "signal_line": float(row.get("macd_signal", 0)),
                    "histogram": macd_hist,
                    "signal": macd_sig
                },
                "bollinger": {
                    "upper": float(row.get("bb_up", 0)),   # แมป bb_up
                    "middle": float(row.get("bb_mid", 0)), # แมป bb_mid
                    "lower": float(row.get("bb_low", 0))   # แมป bb_low
                },
                "atr": {"value": float(row.get("atr_14", 0)), "unit": "THB_PER_BAHT_WEIGHT"},
                "trend": {
                    "ema_20": ema20,
                    "ema_50": ema50,
                    "trend_signal": trend_sig
                }
            },
            "news": news_data,
            "portfolio": portfolio,
            "session_gate": {}, 
            "interval": str(interval),
            "timestamp": str(current_time),
        }
        return state