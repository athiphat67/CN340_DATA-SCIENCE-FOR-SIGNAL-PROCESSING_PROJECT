import json
import os
import pandas as pd
from datetime import datetime


def build_feature_dataset(json_file_path, csv_file_path):
    """
    อ่านไฟล์ JSON ล่าสุด สกัดเฉพาะ Feature ที่จำเป็นสำหรับ ML
    พร้อมเพิ่ม Time Features และ Trading Sessions
    แล้วนำไปต่อท้าย (Append) ในตาราง CSV
    """
    if not os.path.exists(json_file_path):
        print(f"❌ ไม่พบไฟล์ {json_file_path}")
        print(
            "💡 คำแนะนำ: รัน python orchestrator.py หรือ conJSON.py เพื่อสร้าง latest.json ก่อน"
        )
        return

    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ==========================================
    # 1. TIME FEATURES & TRADING SESSIONS
    # ==========================================
    timestamp_str = data["meta"]["generated_at"]
    dt = pd.to_datetime(timestamp_str)

    hour = dt.hour
    day_of_week = dt.dayofweek  # 0=วันจันทร์, 6=วันอาทิตย์

    # รอบเวลาตลาดทองคำ (เวลาไทย UTC+7)
    # Asian Session (โตเกียว): 07:00 - 15:00
    # London Session (ยุโรป): 15:00 - 23:00
    # New York Session (อเมริกา): 20:00 - 04:00 (ทับซ้อนกับลอนดอนช่วง 20:00-23:00 ซึ่งราคามักจะสวิงแรงสุด)
    is_asian = 1 if 7 <= hour < 15 else 0
    is_london = 1 if 15 <= hour < 23 else 0
    is_ny = 1 if (20 <= hour <= 23) or (0 <= hour < 4) else 0

    # ==========================================
    # 2. MARKET & TECHNICAL FEATURES
    # ==========================================
    market = data["market_data"]
    tech = data["technical_indicators"]

    # Categorical Encoding (แปลงข้อความเป็นตัวเลขให้ ML)
    trend_map = {"uptrend": 1, "downtrend": -1, "sideways": 0}

    features = {
        # --- Time ---
        "datetime": timestamp_str,
        "hour": hour,
        "day_of_week": day_of_week,
        "is_asian_session": is_asian,
        "is_london_session": is_london,
        "is_ny_session": is_ny,
        # --- Price Data ---
        "spot_price": market["spot_price_usd"]["price_usd_per_oz"],
        "usd_thb": market["forex"]["usd_thb"],
        "thai_gold_sell": market["thai_gold_thb"]["sell_price_thb"],
        # --- Indicators ---
        "rsi": tech["rsi"]["value"],
        "macd_hist": tech["macd"]["histogram"],
        "bollinger_pct_b": tech["bollinger"]["pct_b"],
        "bollinger_bw": tech["bollinger"]["bandwidth"],
        "atr": tech["atr"]["value"],
        "trend_encoded": trend_map.get(tech["trend"]["trend"], 0),
        "ema_20": tech["trend"]["ema_20"],
        "sma_200": tech["trend"]["sma_200"],
    }

    # ==========================================
    # 3. SENTIMENT FEATURES (NLP)
    # ==========================================
    news_cats = data["news"]["by_category"]
    target_categories = [
        "thai_gold_market",
        "gold_price",
        "geopolitics",
        "dollar_index",
        "fed_policy",
    ]

    for cat in target_categories:
        cat_data = news_cats.get(cat, {})
        articles = cat_data.get("articles", [])

        if articles:
            # หาค่าเฉลี่ย Sentiment ของแต่ละหมวด (-1.0 ถึง 1.0)
            avg_sent = sum(a.get("sentiment_score", 0.0) for a in articles) / len(
                articles
            )
        else:
            avg_sent = 0.0

        features[f"sentiment_{cat}"] = round(avg_sent, 4)

    # ==========================================
    # 4. EXPORT TO CSV
    # ==========================================
    df_new = pd.DataFrame([features])

    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    file_exists = os.path.isfile(csv_file_path)

    # บันทึกแบบ Append (ต่อท้ายเรื่อยๆ)
    df_new.to_csv(
        csv_file_path, mode="a", header=not file_exists, index=False, encoding="utf-8"
    )

    print(f"✅ สกัด Features ลง {os.path.basename(csv_file_path)} สำเร็จ!")
    print(
        f"   📊 Spot: {features['spot_price']} | RSI: {features['rsi']} | NY Session: {bool(features['is_ny_session'])}"
    )


if __name__ == "__main__":
    # หาตำแหน่งไฟล์ extract_features.py (ใน Src/data_engine)
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # ชี้เป้าไปที่ output/latest.json และ Data/features_master.csv นอกสุด
    json_path = os.path.join(current_dir, "..", "agent_core", "data", "latest.json")
    csv_path = os.path.join(current_dir, "..", "..", "Data", "features_master.csv")

    build_feature_dataset(json_file_path=json_path, csv_file_path=csv_path)
