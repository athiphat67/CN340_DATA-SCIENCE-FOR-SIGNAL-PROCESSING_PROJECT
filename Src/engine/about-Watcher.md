# WatcherEngine — คู่มือแบบละเอียด

`WatcherEngine` ใน `Src/engine/engine.py` คือคอมโพเนนต์สำหรับเฝ้าตลาดแบบ live ที่ทำงานอยู่เบื้องหลังตลอดเวลา คอยติดตามสภาวะตลาดอย่างต่อเนื่อง ใช้กฎง่าย ๆ เพื่อเช็ค trigger จัดการการป้องกันความเสี่ยงแบบ real-time และปลุก AI analysis pipeline เฉพาะตอนที่เงื่อนไขเหมาะสมเท่านั้น

## 1. WatcherEngine รับผิดชอบอะไรบ้าง

`WatcherEngine` ไม่ใช่ตัวเดียวกับ backtest engine ใน `Src/backtest/run_main_backtest.py`

หน้าที่ของมันคือช่วยให้ระบบทำงานในโหมด live หรือ dashboard-driven ได้ โดยทำสิ่งต่อไปนี้:

- ดึง `market_state` ล่าสุดจาก data layer
- เช็คว่าสภาวะตลาดตอนนี้ควรปลุก AI หรือยัง
- กันการ trigger ถี่เกินไปด้วย cooldown และ minimum price movement
- บังคับใช้กฎป้องกันความเสี่ยงแบบ real-time ด้วย trailing stop และ hard stop
- ส่งงานวิเคราะห์เชิงลึกต่อให้ `AnalysisService`
- ทำ log เพื่อให้ UI นำไปแสดงผลได้
- เตรียม hook ไว้สำหรับการเชื่อม broker execution ในอนาคต

สรุปสั้น ๆ คือ watcher ทำตัวเหมือนผู้เฝ้าระวังและตัว dispatch แบบ real-time:

```text
Market snapshot -> Trigger check -> Risk guard -> AI analysis -> Downstream action
```

## 2. สถาปัตยกรรมระดับสูง

ไฟล์หลักที่ทำงานร่วมกันมีดังนี้:

- `Src/engine/engine.py`
  - ประกาศ `WatcherConfig`, `TriggerState` และ `WatcherEngine`

- `Src/data_engine/orchestrator.py`
  - สร้าง `market_state` ที่ watcher ใช้งาน
  - ดึงราคา, indicators, ข่าว และประกอบเป็น payload เดียว

- `Src/ui/core/services.py`
  - มี `AnalysisService`
  - ดูแล analysis workflow เชิงลึก, persistence และ notifications

- `Src/database/database.py`
  - เก็บและ restore สถานะ portfolio
  - รองรับการบันทึก emergency sell แบบ atomic

- `Src/ui/dashboard.py`
  - สร้างและ start `WatcherEngine` เป็น background thread ใน dashboard
  - แสดง watcher logs บน UI

- `Src/main.py`
  - มีโค้ด integration แบบคอมเมนต์ไว้ เพื่อแสดงแนวทางว่าระบบ watcher สามารถถูก start จาก CLI/main runtime ได้เช่นกัน

## 3. องค์ประกอบหลักภายใน `engine.py`

### 3.1 `GOLD_BAHT_TO_GRAM`

constant ระดับ module ตัวนี้ใช้สำหรับแปลงราคาทองไทยให้เป็นราคาต่อกรัม:

```python
GOLD_BAHT_TO_GRAM: float = 15.244
```

โค้ดใช้ constant ตัวนี้ใน `_extract_price()` แทนการกระจาย magic number ไว้หลายจุดใน engine

### 3.2 `WatcherConfig`

`WatcherConfig` คือ Pydantic model ที่ใช้ validate runtime configuration ตั้งแต่ต้น

field สำคัญได้แก่:

- `provider`
- `period`
- `interval`
- `cooldown_minutes`
- `min_price_step`
- `rsi_oversold`
- `rsi_overbought`
- `trailing_stop_profit_trigger`
- `trailing_stop_lock_in`
- `hard_stop_loss_per_gram`
- `loop_sleep_seconds`

เหตุผลที่ส่วนนี้สำคัญ:

- ถ้า config ขาดหรือ type ไม่ถูกต้อง watcher จะ fail ทันที
- ช่วยป้องกันไม่ให้ background thread เริ่มทำงานทั้งที่ config เสีย

นอกจากนี้ยังมี validators สำหรับ field อย่าง `provider` และ `period` เพื่อ reject ค่าที่ไม่ถูกต้องตั้งแต่แรก

### 3.3 `TriggerState`

`TriggerState` เป็น state manager ขนาดเล็กที่ใช้ลดการ retrigger แบบรัวเกินจำเป็น

มันเก็บข้อมูลดังนี้:

- `last_trigger_time`
- `last_trigger_price`
- `threading.Lock` ภายใน

ก่อนจะปลุก AI ได้อีกครั้ง มันจะบังคับให้ผ่าน 2 เงื่อนไขก่อน:

- Cooldown ต้องหมดแล้ว
- ราคาต้องขยับอย่างน้อย `min_price_step` THB/gram จาก trigger ก่อนหน้า

ดังนั้น watcher จะไม่ปลุก AI ในทุก loop เพียงเพราะ RSI ยังอยู่ในโซนสุดโต่ง

### 3.4 `WatcherEngine`

`WatcherEngine` เป็นตัว orchestrator หลักของ live monitoring loop

มันถือ reference ไปยัง:

- `analysis_service`
- `data_orchestrator`
- `config` ที่ผ่านการ validate แล้ว
- `trigger_state`
- in-memory log buffer
- ค่า trailing stop ที่ restore มาจาก DB

หน้าที่หลักของมันคือ:

- start และ stop background loop
- ดึง market state
- อ่าน price ที่ใช้งานได้จริง
- จัดการ protective exits
- ตัดสินใจว่าจะ trigger AI analysis เมื่อไร
- ส่งต่อ AI decisions ไปยัง downstream

## 4. Lifecycle และ runtime flow

### 4.1 ช่วงเริ่มต้นของ engine

ตอนที่ engine ถูกสร้าง จะเกิดขั้นตอนดังนี้:

1. `WatcherConfig` ทำการ validate config ที่ส่งเข้ามา
2. `TriggerState` ถูกสร้างขึ้นพร้อมกฎ cooldown และ price-step
3. `_load_trailing_stop_from_portfolio()` พยายาม restore trailing stop ที่เคยบันทึกไว้จาก database

ขั้นตอน restore นี้สำคัญ เพราะช่วยป้องกันกรณี restart ระบบแล้วลืมระดับ trailing stop ที่เคยตั้งไว้

### 4.2 การ start watcher thread

`start()` จะสร้าง daemon thread แล้วชี้ไปที่ `_watcher_loop()`

เมื่อเริ่มทำงานแล้ว engine จะ loop ต่อเนื่องตราบใดที่ `self.is_running` ยังเป็น `True`

### 4.3 watcher loop หลัก

loop หลักจะทำงานตามลำดับดังนี้:

```text
1. Build market_state using data_orchestrator
2. Read current gold price safely
3. Apply trailing stop / hard stop logic
4. Check RSI trigger condition
5. Check cooldown and price-step readiness
6. If ready, trigger AI analysis
7. Sleep for loop_sleep_seconds
```

## 5. อธิบาย watcher loop แบบทีละขั้น

### Step 1: ดึง market state

watcher เรียก:

```python
self.data_orchestrator.run(history_days=1, interval=self.config.interval)
```

นั่นหมายความว่า watcher ไม่ได้ไปดึง raw exchange data เองโดยตรง แต่พึ่ง data engine ในการสร้าง market snapshot ที่ถูก normalize แล้ว

ใน `Src/data_engine/orchestrator.py` ตัว orchestrator ทำงานเช่น:

- เรียก `fetch_price`
- normalize timezone ให้เป็น `Asia/Bangkok`
- คำนวณ indicators ผ่าน `fetch_indicators`
- ดึงข่าวผ่าน `fetch_news`
- ประกอบเป็น `market_state` payload ที่ผ่านการ validate

watcher คาดหวังว่า payload นี้จะมีอย่างน้อย:

- market data
- technical indicators
- portfolio context

### Step 2: อ่านราคาแบบ defensive

`_extract_price()` จะอ่านค่าจาก:

```text
market_state["market_data"]["thai_gold_thb"]["sell_price_thb"]
```

จากนั้นแปลงค่าเป็น THB ต่อกรัม

พฤติกรรมสำคัญของส่วนนี้คือ:

- ถ้าราคาไม่มี จะคืน `None`
- ถ้า parse ไม่ได้ จะ log error แล้วคืน `None`
- loop จะ skip cycle นั้นไป แทนที่จะใช้ค่า default ปลอม ๆ แบบเงียบ ๆ

นี่เป็นการปรับปรุงด้านความปลอดภัยของ engine อย่างตั้งใจ

### Step 3: จัดการ trailing stop และ hard stop

`_manage_trailing_stop()` จะอ่าน portfolio ปัจจุบันผ่าน:

```python
self.analysis_service.persistence.get_portfolio()
```

โดยใช้ค่า:

- `gold_grams`
- `cost_basis_thb`

เพื่อประเมินว่าควรให้ risk protection ทำงานหรือยัง

#### พฤติกรรมของ trailing stop

ถ้ากำไรต่อกรัมมากกว่า `trailing_stop_profit_trigger`:

- engine จะคำนวณ stop level ใหม่เป็น:

```text
cost_basis + trailing_stop_lock_in
```

- ถ้า stop ใหม่นี้ดีกว่าค่าเดิม จะอัปเดต stop ใน memory
- จะ persist ค่า stop ลง DB ผ่าน `_persist_trailing_stop()`
- ถ้าราคาปัจจุบันย่อลงมาถึงหรือต่ำกว่า active stop ระบบจะ trigger emergency sell

#### พฤติกรรมของ hard stop

ถ้ากำไรต่อกรัมลดลงต่ำกว่า threshold ฝั่งลบ:

```text
profit_per_gram <= -hard_stop_loss_per_gram
```

engine จะ cut position ทันทีด้วย emergency sell

#### กรณีไม่มีทองในพอร์ต

ถ้า `gold_grams <= 0`:

- trailing stop state ใน memory จะถูก reset
- จะไม่มีการพยายามสั่งขาย

### Step 4: เช็ค RSI trigger

หลังจากจัดการ protective exits แล้ว watcher จะดู RSI จาก:

```text
market_state["technical_indicators"]["rsi"]["value"]
```

มันจะ trigger ขั้นต่อไปเฉพาะตอน RSI อยู่นอก band ที่ตั้งไว้:

- ต่ำกว่า `rsi_oversold` หรือ
- สูงกว่า `rsi_overbought`

ดังนั้น watcher ใช้กฎเชิงตัวเลขแบบง่ายเพื่อบอกว่าตลาดตอนนี้น่าสนใจพอที่จะปลุก AI หรือยัง

### Step 5: ใช้ `TriggerState` เพื่อลดสัญญาณรบกวน

แม้ RSI จะสุดโต่งแล้ว watcher ก็ยังต้องเช็คต่อว่า:

- cooldown หมดหรือยัง
- ราคาขยับมากพอจาก trigger ครั้งก่อนหรือยัง

ถ้ายังไม่พร้อม มันจะ log สาเหตุว่าทำไม trigger ถูกบล็อก

ตัวอย่างเหตุผลที่พบได้ เช่น:

- cooldown ยังไม่หมด
- ราคาขยับน้อยเกินไป

สิ่งนี้ช่วยลดการเรียก AI ซ้ำ ๆ ตอนตลาดแกว่งแคบหรือแทบไม่เปลี่ยนแปลง

### Step 6: Trigger AI analysis

ถ้าทุกเงื่อนไขผ่าน watcher จะ log ข้อความ wake-up แล้วเรียก `_trigger_analysis()`

`_trigger_analysis()` จะส่งงานหนักต่อไปให้ `AnalysisService.run_analysis()` โดยใช้:

- `provider=self.config.provider`
- `period=self.config.period`
- `intervals=[self.config.interval]`
- `bypass_session_gate=False`

นี่เป็นจุดออกแบบที่สำคัญ:

- `WatcherEngine` ทำหน้าที่เฝ้าและ dispatch
- `AnalysisService` ทำหน้าที่เป็น analysis pipeline ตัวจริง

### Step 7: จัดการผลลัพธ์ AI ที่ส่งกลับมา

ถ้า analysis สำเร็จ watcher จะดึง:

- `final_signal`
- `weighted_confidence`
- `run_id`

แล้วนำไป log

หลังจากนั้นจึงเรียก `_on_ai_decision()`

ปัจจุบัน `_on_ai_decision()` ยังเป็นเพียง hook ที่เอาไว้ log decision เท่านั้น และเป็นจุดต่อขยายสำหรับ broker execution ในอนาคต

## 6. Flow ของ emergency sell

หนึ่งในหน้าที่ที่สำคัญที่สุดของ watcher คือการบังคับออกจาก position แบบ real-time

เมื่อ `_execute_emergency_sell()` ถูกเรียก มันจะทำสิ่งต่อไปนี้:

1. log เหตุการณ์ emergency sell
2. คง placeholder comment ไว้สำหรับ broker integration ในอนาคต
3. เรียก `self.analysis_service.persistence.record_emergency_sell_atomic(...)`
4. ล้าง trailing stop ใน memory หลังขายสำเร็จ

ฝั่ง database ถูก implement ไว้ใน `Src/database/database.py`

`record_emergency_sell_atomic()` จะทำสองอย่างนี้ใน transaction เดียว:

- insert รายการ `SELL` ลง `trade_log`
- update ตาราง `portfolio`

สิ่งนี้ช่วยป้องกัน state ที่ไม่สอดคล้องกัน เช่น บันทึกการขายแล้วแต่ยอดในพอร์ตยังไม่เปลี่ยน หรือกลับกัน

## 7. พฤติกรรมของ logging

watcher จะเก็บ rolling in-memory log buffer ของตัวเอง

คุณสมบัติของกลไกนี้คือ:

- thread-safe ผ่าน `self.lock`
- เก็บเฉพาะ log ล่าสุด
- อ่านออกมาได้ผ่าน `get_logs()`
- เหมาะสำหรับให้ UI poll ไปแสดงผล

นี่คือเหตุผลที่ dashboard สามารถแสดง watcher activity ได้โดยไม่ต้องอ่านจาก terminal output โดยตรง

## 8. การเชื่อมกับ dashboard

ใน `Src/ui/dashboard.py` watcher ถูกสร้างและ start เป็น background thread พร้อม config ประมาณนี้:

- `provider="gemini"`
- `period="1d"`
- `interval="5m"`

dashboard ยังมี tab สำหรับ poll และแสดง watcher logs ด้วย

นั่นหมายความว่า dashboard คือ runtime entry point ที่ชัดที่สุดของ `WatcherEngine` ในสถานะปัจจุบัน

## 9. ความสัมพันธ์กับ `AnalysisService`

`WatcherEngine` พึ่ง `AnalysisService` จาก `Src/ui/core/services.py` อย่างมาก

`AnalysisService` รับผิดชอบเรื่องต่าง ๆ เช่น:

- validate input ของ analysis
- normalize ชื่อ provider
- รัน AI analysis flow
- ประสานงาน persistence
- ส่ง Discord notifications
- ส่ง Telegram notifications

ดังนั้นตอน watcher ปลุก AI มันไม่ได้เป็นคนตัดสินใจเทรดทั้งหมดด้วยตัวเอง แต่ส่งต่อให้ service layer ที่รู้จักระบบส่วนอื่นอยู่แล้ว

## 10. ความสัมพันธ์กับ data orchestrator

`WatcherEngine` ยังพึ่ง `GoldTradingOrchestrator` ใน `Src/data_engine/orchestrator.py`

orchestrator ตัวนี้รับผิดชอบสร้าง market snapshot ที่ watcher และ analysis service ใช้งาน

รายละเอียดสำคัญของ orchestrator ได้แก่:

- ดึงราคาตลาด
- คำนวณ indicators เช่น RSI
- ดึงข่าว
- normalize timezone ให้เป็น `Asia/Bangkok`
- ประกอบเป็น payload โครงสร้างเดียวสำหรับ downstream

เพราะเหตุนี้ watcher จึงถูกทำให้ lean โดยตั้งใจ มันไม่ต้อง reimplement ตรรกะด้าน market-data ซ้ำ

## 11. ความสัมพันธ์กับ persistence และสถานะ portfolio

watcher อ่านและเขียนสถานะ portfolio ผ่าน `analysis_service.persistence`

เมธอดที่เกี่ยวข้องมากที่สุดคือ:

- `get_portfolio()`
- `save_portfolio()`
- `record_emergency_sell_atomic()`

สิ่งนี้ทำให้ watcher สามารถ:

- restore trailing stop หลัง restart
- ประเมินความเสี่ยงของ position ที่เปิดอยู่แบบ real-time
- persist การเปลี่ยนแปลงด้าน protection
- บันทึก forced exits อย่างปลอดภัย

## 12. อะไรที่ implement แล้ว และอะไรที่ยังเป็น stub

ส่วนที่ implement แล้ว:

- background thread loop
- config validation
- cooldown และ price-step gating
- RSI-based wake-up logic
- market-state polling
- defensive price extraction
- trailing stop logic
- hard stop logic
- emergency sell DB transaction
- watcher log buffer
- dashboard startup path

ส่วนที่ยัง implement ไม่ครบหรือยังเป็น stub:

- actual broker execution calls
- full auto-order placement ใน `_on_ai_decision()`

พูดอีกแบบคือ watcher ตอนนี้เป็น monitoring และ protection component ที่แข็งแรงพอสมควรแล้ว แต่ยังไม่ใช่ broker-connected execution engine แบบสมบูรณ์

## 13. Caveats และข้อสังเกตสำคัญ

### 13.1 Watcher เป็นฝั่ง live ไม่ใช่ backtest

อย่าสับสน `WatcherEngine` กับ backtesting pipeline

- watcher = ตัว monitor แบบ live/background
- backtest engine = ตัวรัน historical simulation

### 13.2 ข้อความใน UI อาจไม่ตรงกับค่า loop sleep จริง

ใน `Src/ui/dashboard.py` ข้อความบน watcher tab บอกว่าระบบเช็คทุก 3 วินาที

แต่ใน `engine.py` ค่า default config คือ:

```python
loop_sleep_seconds = 30
```

และในโค้ดที่ start watcher จาก dashboard ก็ไม่ได้ override ค่า `loop_sleep_seconds` อย่างชัดเจน

ดังนั้นจากที่เห็นในโค้ด ระยะ loop จริงอาจเป็น 30 วินาที เว้นแต่จะถูกตั้งค่าจากที่อื่น

### 13.3 Watcher พึ่งพา `market_state` ที่มีโครงสร้างถูกต้อง

ถ้า data orchestrator หยุดส่ง field อย่าง:

- `market_data.thai_gold_thb.sell_price_thb`
- `technical_indicators.rsi.value`

watcher จะเริ่ม skip cycle หรือสูญเสียความสามารถในการ trigger

### 13.4 Risk protection ทำงานได้โดยไม่ต้องรอ AI trigger ใหม่

Trailing stop และ hard stop ถูกเช็คก่อนตัดสินใจว่าจะปลุก AI หรือไม่

นี่เป็นการออกแบบโดยตั้งใจ เพราะ portfolio protection ไม่ควรต้องรอ AI decision รอบใหม่ก่อนเสมอไป

## 14. Mental model แบบสั้น ๆ

วิธีคิดง่าย ๆ เกี่ยวกับ watcher คือ:

- `data_orchestrator` บอกว่าตลาดตอนนี้เป็นอย่างไร
- `TriggerState` ตัดสินว่า AI ได้เวลาตื่นอีกหรือยัง
- `WatcherEngine` ปกป้อง position และ dispatch งานวิเคราะห์
- `AnalysisService` ทำ decision pipeline ตัวจริง
- `database` เก็บ state และบันทึก forced exits
- `dashboard` แสดง watcher logs ให้ผู้ใช้เห็น

## 15. สรุป end-to-end flow

```text
Dashboard starts WatcherEngine
    -> Watcher thread loops
    -> data_orchestrator builds market_state
    -> Watcher extracts current price
    -> Watcher checks trailing stop / hard stop
    -> Watcher checks RSI trigger
    -> TriggerState enforces cooldown and min price step
    -> AnalysisService.run_analysis() is called
    -> Analysis result is logged
    -> Notifications happen inside service layer
    -> Broker hook remains available for future execution
```

## 16. ทำไมไฟล์นี้ถึงสำคัญในโปรเจค

`WatcherEngine` เป็นหนึ่งในสะพานสำคัญที่เชื่อมระหว่าง passive analysis กับ active live behavior

มันทำให้ระบบดูเป็นระบบปฏิบัติการจริงมากกว่าระบบวิเคราะห์อย่างเดียว เพราะมัน:

- รันอยู่เบื้องหลังตลอดเวลา
- ตอบสนองต่อสภาวะตลาด
- ปกป้อง position ที่ถืออยู่
- เรียก AI เฉพาะตอนมี trigger
- เตรียมสถาปัตยกรรมไว้สำหรับ broker execution ในอนาคต

ถ้าคุณอยากเข้าใจว่าระบบเดินจากคำว่า "monitoring" ไปสู่ "live action" อย่างไร `engine.py` คือหนึ่งในไฟล์ที่สำคัญที่สุดที่ควรอ่าน