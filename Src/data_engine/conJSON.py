import json
import os
from datetime import datetime
from orchestrator import GoldTradingOrchestrator

def export_to_json(output_dir="output", filename="custom_gold_data.json"):
    """
    ดึงข้อมูลจาก Orchestrator และบันทึกเป็นไฟล์ JSON
    """
    print("⏳ กำลังรวบรวมข้อมูลตลาดทองคำและคำนวณ Indicators...")
    
    # 1. เรียกใช้งาน Orchestrator (ดึงข้อมูลย้อนหลัง 90 วัน, ข่าว 5 หัวข้อต่อหมวด)
# ในไฟล์ conJSON.py
    orchestrator = GoldTradingOrchestrator(history_days=30, interval="5m", max_news_per_cat=5)
    
    # 2. สั่งรันเพื่อรับค่าเป็น Dictionary (ตั้ง save_to_file=False เพื่อไม่ให้ orchestrator เซฟซ้ำซ้อน)
    payload_dict = orchestrator.run(save_to_file=False)
    
    # 3. เตรียมโฟลเดอร์สำหรับเก็บไฟล์
    os.makedirs(output_dir, exist_ok=True)
    
    # หากต้องการให้ชื่อไฟล์มี Timestamp ด้วยสามารถเปิดใช้บรรทัดด้านล่างได้
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gold_data_{timestamp}.json"
    
    file_path = os.path.join(output_dir, filename)
    
    # 4. เขียนข้อมูลลงไฟล์ JSON
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(
            payload_dict, 
            json_file, 
            indent=4,              # จัดย่อหน้าให้มนุษย์อ่านง่าย (Pretty Print)
            ensure_ascii=False,    # รองรับการแสดงผลภาษาไทย
            default=str            # แปลง object แปลกๆ (เช่น datetime) ให้เป็น string อัตโนมัติ
        )
        
    print(f"✅ บันทึกไฟล์ JSON สำเร็จ: {file_path}")

if __name__ == "__main__":
    export_to_json()