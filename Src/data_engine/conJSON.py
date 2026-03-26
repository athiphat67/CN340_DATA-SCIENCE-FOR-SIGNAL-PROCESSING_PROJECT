import json
import os
from datetime import datetime
from orchestrator import GoldTradingOrchestrator
import argparse

def export_to_json(output_dir="output", filename="custom_gold_data.json"):
    """
    ดึงข้อมูลจาก Orchestrator และบันทึกเป็นไฟล์ JSON
    """
    print("⏳ กำลังรวบรวมข้อมูลตลาดทองคำและคำนวณ Indicators...")
    
    # 1. เรียกใช้งาน Orchestrator (ดึงข้อมูลย้อนหลัง 90 วัน, ข่าว 5 หัวข้อต่อหมวด)
# ในไฟล์ conJSON.py
    orchestrator = GoldTradingOrchestrator(history_days=90, interval="1d", max_news_per_cat=5)
    
    # 2. สั่งรันเพื่อรับค่าเป็น Dictionary (ตั้ง save_to_file=False เพื่อไม่ให้ orchestrator เซฟซ้ำซ้อน)
    payload_dict = orchestrator.run(save_to_file=False)
    
    # 3. เตรียมโฟลเดอร์สำหรับเก็บไฟล์
    os.makedirs(output_dir, exist_ok=True)
    
    # หากต้องการให้ชื่อไฟล์มี Timestamp ด้วยสามารถเปิดใช้บรรทัดด้านล่างได้
    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # filename = f"gold_data_{timestamp}.json"
    
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

def export_to_json():
    # 1. ตั้งค่าเครื่องมือช่วยรับค่าจาก Terminal
    parser = argparse.ArgumentParser(description="Gold Data Exporter")
    parser.add_argument("--days", type=int, default=90, help="จำนวนวันย้อนหลัง")
    parser.add_argument("--interval", type=str, default="1d", help="ความละเอียด (1m, 5m, 1h, 1d)")
    parser.add_argument("--news", type=int, default=5, help="จำนวนข่าวต่อหมวด")
    
    args = parser.parse_args()

    print(f"🚀 กำลังดึงข้อมูล: {args.days} วัน, Timeframe: {args.interval}")

    # 2. เอาค่าจาก args มาใส่ใน Orchestrator
    orchestrator = GoldTradingOrchestrator(
        history_days=args.days, 
        interval=args.interval, 
        max_news_per_cat=args.news
    )
    
    payload_dict = orchestrator.run(save_to_file=False)
    # ... โค้ดส่วนเซฟ JSON เหมือนเดิม ...

if __name__ == "__main__":
    export_to_json()