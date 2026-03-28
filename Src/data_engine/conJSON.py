import json
import os
from orchestrator import GoldTradingOrchestrator
from thailand_timestamp import get_thai_time

def export_to_json(output_dir="output", filename="custom_gold_data.json"):
    print("⏳ กำลังรวบรวมข้อมูลตลาดทองคำและคำนวณ Indicators...")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "..", "..", "output")

    orchestrator = GoldTradingOrchestrator(history_days=30, interval="5m", max_news_per_cat=5)
    payload_dict = orchestrator.run(save_to_file=False)

    os.makedirs(output_dir, exist_ok=True)

    timestamp = get_thai_time().strftime("%Y%m%d_%H%M%S")
    filename = f"gold_data_{timestamp}.json"
    
    file_path = os.path.join(output_dir, filename)
    
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(
            payload_dict, 
            json_file, 
            indent=4,              
            ensure_ascii=False,    
            default=str            
        )
        
    print(f"✅ บันทึกไฟล์ JSON สำเร็จ: {file_path}")

if __name__ == "__main__":
    export_to_json()