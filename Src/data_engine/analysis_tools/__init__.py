# 1. นำเข้า Technical Tools ทั้งหมด
from .technical_tools import (
    get_htf_trend,
    check_volatility,
    calculate_ema_distance,
    detect_liquidity_sweep,
    identify_supply_demand_zones,
    check_volume_anomaly,
    # --- เครื่องมือใหม่จากเอกสารกลยุทธ์ ---
    detect_swing_low,
    detect_rsi_divergence,
    check_bb_rsi_combo,
)

# 2. นำเข้า Fundamental Tools ทั้งหมด
from .fundamental_tools import (
    get_deep_news_by_category,
    check_upcoming_economic_calendar,
    get_intermarket_correlation,
    check_fed_speakers_schedule,
    get_institutional_positioning,
    get_gold_etf_flow,
)

# 3. ผูกชื่อ Tool (String ที่ LLM จะตอบกลับมา) เข้ากับฟังก์ชันจริง
TOOL_REGISTRY = {
    # Technical
    "get_htf_trend": get_htf_trend,
    "check_volatility": check_volatility,
    "calculate_ema_distance": calculate_ema_distance,
    "detect_liquidity_sweep": detect_liquidity_sweep,
    "identify_supply_demand_zones": identify_supply_demand_zones,
    "check_volume_anomaly": check_volume_anomaly,
    "detect_swing_low": detect_swing_low,
    "detect_rsi_divergence": detect_rsi_divergence,
    "check_bb_rsi_combo": check_bb_rsi_combo,
    # Fundamental
    "get_deep_news_by_category": get_deep_news_by_category,
    "check_upcoming_economic_calendar": check_upcoming_economic_calendar,
    "get_intermarket_correlation": get_intermarket_correlation,
    "check_fed_speakers_schedule": check_fed_speakers_schedule,
    "get_institutional_positioning": get_institutional_positioning,
    "get_gold_etf_flow": get_gold_etf_flow,
}

# 4. คู่มือสำหรับ LLM (จะถูกดึงไปแปะใน Prompt)
# ต้องเขียนให้ชัดเจนว่ารับ Arguments อะไรบ้าง เพื่อป้องกัน LLM ส่งค่าผิดประเภท
AVAILABLE_TOOLS_INFO = """
### TECHNICAL TOOLS (กลุ่มวิเคราะห์โครงสร้างและแท่งเทียน) ###
1. "detect_swing_low": ตรวจสอบหาจุดต่ำก่อนพุ่ง (Swing Low Structure) และการ Confirm กลับตัว [cite: 8, 9, 11]
   - Arguments: {"interval": "15m", "history_days": 3}
2. "detect_rsi_divergence": ตรวจสอบหา RSI Bullish Divergence ดูภาวะของหมดแรงขาย [cite: 14, 16, 17]
   - Arguments: {"interval": "15m", "history_days": 5}
3. "check_bb_rsi_combo": ตรวจสอบจุดกลับตัวเมื่อราคาหลุด BB พร้อม RSI Oversold และ MACD เริ่มแบนราบ [cite: 23, 24, 25, 26, 29]
   - Arguments: {"current_price": <float>, "lower_bb": <float>, "rsi": <float>, "macd_hist_current": <float>, "macd_hist_prev": <float>}
4. "calculate_ema_distance": ตรวจสอบความห่างของราคาปัจจุบันกับเส้นค่าเฉลี่ย (Mean Reversion Check) ดูภาวะ Overextended [cite: 31, 32, 33]
   - Arguments: {"current_price": <float>, "ema_20": <float>, "atr": <float>}
5. "get_htf_trend": ดึงข้อมูลเทรนด์จาก Timeframe ที่ใหญ่กว่า (Higher Timeframe) เพื่อดูภาพรวม
   - Arguments: {"timeframe": "4h"} (รองรับ "1h", "4h", "1d")
6. "check_volatility": ตรวจสอบความผันผวนของตลาดในปัจจุบัน (ATR)
   - Arguments: {"asset": "XAUUSD"}
7. "detect_liquidity_sweep": ตรวจสอบพฤติกรรมกวาดสภาพคล่อง (Stop Hunt / Liquidity Sweep) หาจุดกลับตัว
   - Arguments: {"timeframe": "15m", "lookback": 20}
   - ⏳ Status: รอการพัฒนา
8. "identify_supply_demand_zones": ค้นหาโซน Supply และ Demand ที่ยังไม่ถูกทดสอบ (Unmitigated Zones)
   - Arguments: {"timeframe": "1h"}
   - ⏳ Status: รอการพัฒนา
9. "check_volume_anomaly": ตรวจสอบความผิดปกติของ Volume เพื่อยืนยันการ Breakout ว่าจริงหรือหลอก
   - Arguments: {"interval": "5m"}
   - ⏳ Status: รอการพัฒนา

### FUNDAMENTAL TOOLS (กลุ่มข่าวสารและปัจจัยพื้นฐาน) ###
10. "get_deep_news_by_category": ขออ่านเนื้อหาข่าวแบบเจาะลึกในหมวดหมู่ที่สนใจ
    - ✅ NOW MERGED with enhanced fetch_news() — supports deep dive into single category
    - Arguments: {"category": "fed_policy"} (หมวดที่รองรับ: gold_price, usd_thb, fed_policy, inflation, geopolitics, dollar_index, thai_economy, thai_gold_market)
11. "check_upcoming_economic_calendar": เช็คปฏิทินเศรษฐกิจล่วงหน้าเพื่อหา "ข่าวแดง" (High Impact) ที่อาจทำให้ราคาสวิง พร้อมประเมิน risk_level (critical/high/medium/low)
    - Arguments: {"hours_ahead": 24}
    - ✅ Status: พร้อมใช้งาน (ForexFactory XML feed)
12. "get_intermarket_correlation": ตรวจสอบความสัมพันธ์ข้ามตลาด (DXY + US10Y vs Gold) ดู divergence และ correlation regime
    - Arguments: {}
    - ✅ Status: พร้อมใช้งาน (yfinance: GC=F, DX-Y.NYB, ^TNX)
13. "check_fed_speakers_schedule": ตรวจสอบตารางการให้สัมภาษณ์ของคณะกรรมการ Fed ประจำวัน
    - Arguments: {}
    - ⏳ Status: รอการพัฒนา
14. "get_institutional_positioning": ดึงข้อมูล COT Report เพื่อดูว่ากองทุนใหญ่มีสถานะ Net Long หรือ Short ทองคำอยู่เท่าไหร่
    - Arguments: {}
    - ⏳ Status: รอการพัฒนา
15. "get_gold_etf_flow": ดึงข้อมูล SPDR Gold Trust (GLD) เพื่อดูว่าสถาบันกำลังสะสมหรือเทขายทอง (Ounces in Trust + Volume)
    - Arguments: {}
    - ✅ Status: พร้อมใช้งาน (SPDR XLSX primary, yfinance fallback)

---
### 🔄 MERGED FUNCTIONS (from data_engine/tools) ###

#### ❌ REMOVED (Handled by other tools)
- fetch_market_snapshot() ← Use fetch_price() + fetch_indicators() instead
- get_recent_candles_snapshot() ← Already in fetch_price()["recent_price_action"]

These are NOT LLM tools but data fetchers. They're called internally by ReAct orchestrator.
"""
