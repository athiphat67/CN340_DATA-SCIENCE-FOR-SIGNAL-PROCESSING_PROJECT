# Calculator/calculator.py
import json
import os

def get_rsi_score(rsi: float) -> float:
    """RSI < 30 = น่าซื้อ (+1), RSI > 70 = น่าขาย (-1)"""
    if rsi < 30: return 1.0
    if rsi > 70: return -1.0
    return (50 - rsi) / 20.0

def get_macd_score(macd_hist: float) -> float:
    """ฮิสโตแกรมบวกคือแรงซื้อ ลบคือแรงขาย"""
    return max(-1.0, min(1.0, macd_hist / 1.0))

def get_trend_score(price: float, ema_50: float, ema_200: float) -> float:
    """ราคาอยู่เหนือ EMA คือเทรนด์ขาขึ้น (+1) อยู่ใต้คือขาลง (-1)"""
    score = 0.0
    if price > ema_50: score += 0.5
    else: score -= 0.5
    if price > ema_200: score += 0.5
    else: score -= 0.5
    return score

def get_news_score(news_list: list) -> float:
    """ดักจับ Keyword ในข่าว คืนค่า -1.0 (แย่ต่อทอง) ถึง 1.0 (ดีต่อทอง)"""
    if not news_list: return 0.0
    
    bullish_keywords = ["rate cuts", "escalate", "safe-haven", "weakens", "tension"] 
    bearish_keywords = ["rate hikes", "cooling", "strong dollar", "growth"]
    
    total_score = 0.0
    for news in news_list:
        title_lower = news.get("title", "").lower()
        score = 0.0
        for word in bullish_keywords:
            if word in title_lower: score += 0.5
        for word in bearish_keywords:
            if word in title_lower: score -= 0.5
        total_score += score

    return max(-1.0, min(1.0, total_score / len(news_list)))

def analyze_market_data(json_path: str) -> dict:
    """
    ฟังก์ชันหลัก: โหลด JSON -> คำนวณกราฟ -> คำนวณข่าว -> สรุปผล
    """
    # 1. โหลดข้อมูล
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"หาไฟล์ไม่เจอ: {json_path}")
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    state = data.get("market_state", {})
    news = data.get("macro_news", [])

    # 2. คำนวณฝั่งตัวเลข (Math/Tech)
    rsi_score = get_rsi_score(state.get("rsi", 50.0))
    macd_score = get_macd_score(state.get("macd_hist", 0.0))
    trend_score = get_trend_score(
        state.get("price", 0.0), 
        state.get("ema_50", 0.0), 
        state.get("ema_200", 0.0)
    )
    math_score = (rsi_score + macd_score + trend_score) / 3.0

    # 3. คำนวณฝั่งข่าว (News)
    news_score = get_news_score(news)

    # 4. สรุปผลรวม (Math 60% + News 40%)
    composite = (math_score * 0.6) + (news_score * 0.4)
    
    if composite > 0.15: direction = "BULLISH"
    elif composite < -0.15: direction = "BEARISH"
    else: direction = "NEUTRAL"

    # ส่งกลับเป็น Dictionary คลีนๆ ให้ AI เอาไปใช้ง่ายๆ
    return {
        "calculator_analysis": {
            "math_score": round(math_score, 2),
            "news_score": round(news_score, 2),
            "composite_score": round(composite, 2),
            "direction": direction
        },
        "raw_market_state": state,
        "raw_news": news
    }

if __name__ == "__main__":
    # 1. ให้ Python หาว่าไฟล์ calculator.py นี้เซฟอยู่ที่ไหน
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. ถอยหลัง 1 ก้าวเพื่อกลับไปที่โฟลเดอร์หลัก (agent_core)
    base_dir = os.path.dirname(current_dir)
    
    # 3. ประกอบร่าง Path ใหม่ ชี้ไปที่โฟลเดอร์ Input แบบเป๊ะๆ
    test_path = os.path.join(base_dir, "Input", "mock_state.json")
    
    print(f"กำลังค้นหาไฟล์ที่: {test_path}") # พิมพ์บอกด้วยว่ากำลังหาไฟล์ที่ไหน
    
    try:
        result = analyze_market_data(test_path)
        print("--- ✅ Calculator รันสำเร็จ! ---")
        print(json.dumps(result["calculator_analysis"], indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")