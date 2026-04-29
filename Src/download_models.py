import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification

def download_and_cache(model_name):
    print(f"\n⏳ กำลังดาวน์โหลดและ Cache โมเดล: {model_name}...")
    print("   (อาจจะใช้เวลาหลายนาที ขึ้นอยู่กับความเร็วเน็ต ห้ามปิดหน้าต่างนี้นะครับ)")
    
    # โหลด Tokenizer และ Model มาเก็บไว้ในเครื่อง
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    
    print(f"✅ ดาวน์โหลด {model_name} เสร็จสมบูรณ์!")

if __name__ == "__main__":
    print("🚀 เริ่มระบบ Auto-Pilot: เตรียมสมอง AI ล่วงหน้า...")
    print("=" * 60)
    
    try:
        # 1. โหลด FinBERT (ตัวช่วยเรื่องศัพท์การเงิน)
        download_and_cache("ProsusAI/finbert")
        
        # 2. โหลด DeBERTa-v3 (ตัวหลักวิเคราะห์บริบท)
        # ใช้เวอร์ชัน Base ซึ่งเป็นมาตรฐานที่เพื่อนเธอน่าจะหยิบมาจูนต่อ
        download_and_cache("microsoft/deberta-v3-base")
        
        print("=" * 60)
        print("🎉 [SUCCESS] โหลดสมอง AI ครบทุกตัวแล้ว! ระบบพร้อมประกอบร่างตอนดึกครับ")
        print("   (สามารถพับจอ หรือทิ้งคอมไว้แบบนี้ไปทำธุระได้เลยครับ 🚶‍♀️💨)")
        
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาด: {e}")