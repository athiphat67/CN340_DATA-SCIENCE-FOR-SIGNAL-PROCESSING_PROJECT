import pandas as pd
import json
import os
from datetime import datetime

# --- เล่มที่ 1: จดตัวเลขลง CSV ---
def log_market_data(data_dict, file_name='market_data.csv'):
    """
    data_dict: รับค่าเป็น Dictionary เช่น {'price': 2330, 'sentiment': 0.5, ...}
    """
    # เติมเวลาปัจจุบันลงไปในข้อมูลก่อนเซฟ
    data_dict['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # แปลงเป็น DataFrame (ตาราง)
    df = pd.DataFrame([data_dict])
    
    # เช็กว่ามีไฟล์อยู่แล้วหรือยัง? ถ้ายังไม่มีให้เขียน Header (หัวตาราง) ด้วย
    file_exists = os.path.isfile(file_name)
    
    # mode='a' คือการ Append (ต่อท้ายไปเรื่อยๆ ไม่ทับของเดิม)
    df.to_csv(file_name, mode='a', header=not file_exists, index=False)
    print(f"✅ Saved market data to {file_name}")

# --- เล่มที่ 2: จดข่าวลง JSON ---
def log_news_history(news_list, file_name='news_history.json'):
    """
    news_list: รายการข่าวที่ดึงมาได้ในรอบนั้นๆ
    """
    current_log = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "articles": news_list
    }
    
    history = []
    # ถ้ามีไฟล์เดิมอยู่แล้ว ให้โหลดของเก่ามาเพิ่มของใหม่เข้าไป
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            try:
                history = json.load(f)
            except:
                history = []
                
    history.append(current_log)
    
    # เซฟกลับลงไฟล์ (เก็บแค่ 500 รอบล่าสุดพอ เดี๋ยวไฟล์ใหญ่เกิน)
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(history[-500:], f, ensure_ascii=False, indent=4)
    print(f"✅ Saved news history to {file_name}")