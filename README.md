# นักขุดทอง
# Gold Trading AI Agent

> **Course:** CN240 Data Science for Signal Processing

> **Institution:** Department of Computer Engineering, Thammasat University

> **Lecturer:** Professor Dr. Charturong Tantibundhit

[![Phase](https://img.shields.io/badge/Phase-2%20In%20Progress-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Platform](https://img.shields.io/badge/Platform-Google%20Colab-orange)]()
[![License](https://img.shields.io/badge/License-Academic%20Use%20Only-lightgrey)]()

---
# Overview
ระบบ AI วิเคราะห์และตัดสินใจเทรดทองคำ ผสานการอ่านข้อมูลตัวเลข (Technical Indicators) กับการวิเคราะห์ข่าวสาร (News Sentiment) ด้วย LLM

> **CN240 Data Science for Signal Processing** — Dept. of Computer Engineering, Thammasat University

---

---

## 🏗️ โครงสร้างโปรเจกต์

```
Src/
│
├── agent_core/                          ← AI Agent Core 
├── core/                                ← Business Logic Layer 
├── ui/                                  ← UI Layer 
├── data_engine/                         ← Market Data Collection 
├── backtest/                            ← Backtest Module
├── backtest_main_pipeline.py            Backtest class (MainPipelineBacktest)
├── run_main_backtest.py                 Entry point + CLI args สำหรับ backtest
├── logs/
├── database.py                          RunDatabase (PostgreSQL ORM)
├── main.py                              CLI entry point (production)
├── logger_setup.py                      THTimeFormatter + log_method decorator
└── requirements.txt
```

---

## 🧠 ระบบทำงานอย่างไร

```
ราคาทอง + ข่าว  →  Math Engine (RSI, MACD)  →  LLM Agent  →  คำสั่งเทรด
```

1. **Data Engine** ดึงราคาทอง Spot, อัตราแลกเปลี่ยน, และข่าวสาร
2. **Math Engine** คำนวณ Technical Indicators ด้วย Python (LLM ห้ามคำนวณเอง)
3. **LLM Agent** รับข้อมูลทั้งหมด → วิเคราะห์ → ตัดสินใจ (BUY / SELL / HOLD)
4. **Execution** ตรวจสอบความปลอดภัย เช่น ขนาดไม้ต้องไม่เกิน 10% ของพอร์ต

---

## 👥 ทีมงาน

| ชื่อ | Student ID |
|---|---|
| Athiphat Sunsit | 6710615292 |
| Purich Ampawa | 6710615185 |
| Theepop Rattanasubsiri | 6710685014 |
| Chotiwit Daugstan | 6710615060 |
| Napattira Loaklemhung | 6710545010 |
| Benchaphon Pinakasa | 6710625028 |
| Lalita Thatsananunchai | 6710615243 |
| Phatcharaphon Malaisri | 6710685055 |
| Sitthipong Kamngam | 6710615284 |
| Panithan Tuntue | 6710615144 |

---

