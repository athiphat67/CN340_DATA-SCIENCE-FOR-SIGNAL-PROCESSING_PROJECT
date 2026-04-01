import pandas as pd
import os

def process_mt5_csv(file_path, suffix):
    encodings_to_try = ['utf-16', 'utf-8', 'utf-16-le', 'cp1252', 'latin1']
    df = None
    
    for enc in encodings_to_try:
        try:
            df = pd.read_csv(file_path, sep='\t', encoding=enc)
            if len(df.columns) < 2:
                df = pd.read_csv(file_path, sep=',', encoding=enc)
            
            if '<DATE>' in df.columns:
                print(f"✅ อ่านไฟล์ {file_path} สำเร็จ (Encoding: {enc})")
                break
        except Exception:
            continue
            
    if df is None or '<DATE>' not in df.columns:
        print(f"❌ อ่านไฟล์ {file_path} ไม่สำเร็จ โปรดเปิดไฟล์ดูว่ามีข้อมูลหรือไม่")
        return None
    
    df['timestamp'] = pd.to_datetime(df['<DATE>'] + ' ' + df['<TIME>'])
    cols = ['timestamp', '<OPEN>', '<HIGH>', '<LOW>', '<CLOSE>']
    df = df[cols]
    df.columns = ['timestamp', f'open_{suffix}', f'high_{suffix}', f'low_{suffix}', f'close_{suffix}']
    
    df.set_index('timestamp', inplace=True)
    return df

def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    print("⏳ กำลังเริ่มรวมข้อมูล ปรับเวลา และใช้สูตรทองไทย 96.5% (0.473)...")

    df_gold = process_mt5_csv('XAUUSDm_M1.csv', 'xau')
    df_thb = process_mt5_csv('USDTHBm_M1.csv', 'thb')

    if df_gold is not None and df_thb is not None:
        df_merged = pd.merge(df_gold, df_thb, left_index=True, right_index=True, how='outer')
        df_merged.sort_index(inplace=True)
        df_merged.ffill(inplace=True)
        df_merged.dropna(inplace=True)

        # 1. ปรับ Timezone เป็นเวลาไทย (GMT+7)
        df_merged.index = df_merged.index + pd.Timedelta(hours=7)

        # 2. คำนวณราคาทองไทย 96.5% ตามสูตรเดิม
        c = 0.473

        # เพิ่มค่า Spread เงินบาทเข้าไปประมาณ 0.16
        thb_spread = 0.16 
        
        adj_open_thb = df_merged['open_thb'] + thb_spread
        adj_high_thb = df_merged['high_thb'] + thb_spread
        adj_low_thb = df_merged['low_thb'] + thb_spread
        adj_close_thb = df_merged['close_thb'] + thb_spread
        
        df_merged['open_thai'] = (df_merged['open_xau'] * adj_open_thb * c).round(2)
        df_merged['high_thai'] = (df_merged['high_xau'] * adj_high_thb * c).round(2)
        df_merged['low_thai'] = (df_merged['low_xau'] * adj_low_thb * c).round(2)
        df_merged['close_thai'] = (df_merged['close_xau'] * adj_close_thb * c).round(2)
        
        # 3. เพิ่มคอลัมน์ Gold Spot USD และ อัตราแลกเปลี่ยนเงินบาท (USD/THB)
        df_merged['gold_spot_usd'] = df_merged['close_xau']
        df_merged['usd_thb_rate'] = df_merged['close_thb']

        # จัดเรียงคอลัมน์ใหม่ ให้ดูง่ายขึ้น (ข้อมูล 1M)
        final_df = df_merged[['gold_spot_usd', 'usd_thb_rate', 'open_thai', 'high_thai', 'low_thai', 'close_thai']]
        
        output_1m_path = os.path.join(DATA_DIR, 'thai_gold_1m_dataset.csv')
        final_df.to_csv(output_1m_path)
        print(f"\n✅ สร้าง Dataset 1M สำเร็จ! ไฟล์อยู่ที่: {output_1m_path}")
        print(f"📊 จำนวนข้อมูล 1 นาที ทั้งหมด: {len(final_df)} แท่งเทียน")

        # ---------------------------------------------------------
        # 4. แปลง Timeframe เป็น 1H และ 4H (Resampling)
        # ---------------------------------------------------------
        print("\n⏳ กำลังแปลง Timeframe เป็น 1 ชั่วโมง (1H) และ 4 ชั่วโมง (4H)...")
        
        # กำหนดวิธีตบยอดข้อมูล (Aggregation Rules) สำหรับการแปลง Timeframe
        ohlc_dict = {
            'gold_spot_usd': 'last', # ใช้ราคาปิดของชั่วโมง/4ชั่วโมง นั้นๆ
            'usd_thb_rate': 'last',
            'open_thai': 'first',    # ราคาเปิดแท่ง
            'high_thai': 'max',      # ราคาสูงสุดในรอบ
            'low_thai': 'min',       # ราคาต่ำสุดในรอบ
            'close_thai': 'last'     # ราคาปิดแท่ง
        }

        # สร้าง DataFrame 1H (1 ชั่วโมง)
        df_1h = final_df.resample('1h').agg(ohlc_dict).dropna()
        output_1h_path = os.path.join(DATA_DIR, 'thai_gold_1h_dataset.csv')
        df_1h.to_csv(output_1h_path)
        print(f"✅ สร้าง Dataset 1H สำเร็จ! จำนวน: {len(df_1h)} แท่งเทียน")

        # สร้าง DataFrame 4H (4 ชั่วโมง)
        df_4h = final_df.resample('4h').agg(ohlc_dict).dropna()
        output_4h_path = os.path.join(DATA_DIR, 'thai_gold_4h_dataset.csv')
        df_4h.to_csv(output_4h_path)
        print(f"✅ สร้าง Dataset 4H สำเร็จ! จำนวน: {len(df_4h)} แท่งเทียน")
        
    else:
        print("❌ ยกเลิกการประมวลผล")

if __name__ == "__main__":
    main()