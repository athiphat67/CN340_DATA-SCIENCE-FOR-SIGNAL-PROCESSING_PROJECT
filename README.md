# Gold Price Forecasting and Trading

> **Course:** CN240 Data Science for Signal Processing

> **Institution:** Department of Computer Engineering, Thammasat University

> **Lecturer:** Professor Dr. Charturong Tantibundhit

[![Phase](https://img.shields.io/badge/Phase-2%20In%20Progress-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Platform](https://img.shields.io/badge/Platform-Google%20Colab-orange)]()
[![License](https://img.shields.io/badge/License-Academic%20Use%20Only-lightgrey)]()

---

## Overview

Over the past few decades, gold has evolved far beyond a simple safe-haven asset — it has become a sophisticated instrument for generating returns in increasingly complex market conditions. The global economy over the past 5–10 years has been defined by persistent uncertainty, driven by shifting monetary policies, the COVID-19 pandemic, and intensifying geopolitical tensions such as U.S. tariff announcements and ongoing conflicts in the Middle East. These forces have pushed Thai gold price volatility to a level where investor intuition alone is no longer sufficient for sound decision-making.

This project applies knowledge from CN240 — Data Science for Signal Processing to address the challenge of predicting gold prices in a highly volatile market, particularly in 2026 where macroeconomic and geopolitical uncertainties continue to complicate historical data relationships.

The team focuses on a full **Data Science Pipeline** — from Exploratory Data Analysis (EDA) and Feature Engineering to Model Comparison — with the primary goal of developing a decision-support tool capable of distinguishing genuine investment signals from market noise. Beyond prediction accuracy, this project serves as a hands-on learning experience to build end-to-end Data Science know-how for every team member.

---

## Repository Structure
```
CN240_DATA-SCIENCE-FOR-SIGNAL-PROCESSING_PROJECT/
│
├── Data/
│   ├── Raw/                    # Original unmodified data files (*.csv)
│   ├── Process/                # Transformed data after ELT pipeline
│   └── Image/                  # Exported charts per phase (*.png)
│
├── Documentation/
│   ├── Papers/                 # Phase reports (.docx, .pdf)
│   └── Presentations/          # Slide decks (.pdf)
│
├── Src/                        # Project notebooks
│   └── Phase2_EDA.ipynb
│
├── .gitignore
└── README.md

```

---

## Project Phases

| Phase | Name | Description | Status | Links |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Discovery** | Define the problem scope, formulate hypotheses, assess data readiness and team resources | 🟢 Done | [Slides](https://www.canva.com/design/DAHC3xAWC5o/Sf5yEWD2VEMrooaBQ7mQYw/edit) · [Paper](Documentation/Papers/Phase1_Discovery_Report_Version1.pdf) |
| **2** | **Data Preparation** | Data ingestion, ETL/ELT pipeline, EDA, and feature engineering | 🟡 In Progress | — |
| **3** | **Model Planning** | Select and design appropriate ML models based on data characteristics | ⚪️ Todo | — |
| **4** | **Model Building** | Train, tune, and evaluate regression and classification models | ⚪️ Todo | — |
| **5** | **Communication of Results** | Present final results and evaluate against success criteria | ⚪️ Todo | — |
| **6** | **Operationalization** | Backtesting simulation and pilot study in a real-world environment | ⚪️ Todo | — |

**Workflow Status:**

| Badge | Meaning |
| :---: | :--- |
| ⚪️ | Todo |
| 🟡 | In Progress |
| 🟣 | In Review |
| 🟢 | Done |

---

## Project Tracking

The team manages and tracks progress using **GitHub Projects** in a Kanban-style board, organized by iteration to keep focus and maintain a clean backlog.

[View Project Board](https://github.com/users/athiphat67/projects/4)

---

## Team Members

| # | Student ID | Name |
| :---: | :---: | :--- | 
| 1 | 6710615292 | Athiphat Sunsit |
| 2 | 6710615185 | Purich Ampawa | 
| 3 | 6710685014 | Theepop Rattanasubsiri |
| 4 | 6710615060 | Chotiwit Daugstan | 
| 5 | 6710545010 | Napattira Loaklemhung | 
| 6 | 6710625028 | Benchaphon Pinakasa | 
| 7 | 6710615243 | Lalita Thatsananunchai | 
| 8 | 6710685055 | Phatcharaphon Malaisri | 
| 9 | 6710615284 | Sitthipong Kamngam | 
| 10 | 6710615144 | Panithan Tuntue | 

> All members actively contribute across every phase to build end-to-end Data Science experience.

---

> ⚠️ **Disclaimer:** This project is developed solely for academic purposes. Model outputs do not constitute financial or investment advice of any kind.

# Gold Price Forecasting and Trading

> **Course:** CN240 Data Science for Signal Processing

> **Institution:** Department of Computer Engineering, Thammasat University

> **Lecturer:** Professor Dr. Charturong Tantibundhit

[![Phase](https://img.shields.io/badge/Phase-2%20In%20Progress-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Platform](https://img.shields.io/badge/Platform-Google%20Colab-orange)]()
[![License](https://img.shields.io/badge/License-Academic%20Use%20Only-lightgrey)]()

---

## Overview


---

## Repository Structure
# 📈 Gold Trading AI Agent

ระบบ AI สำหรับวิเคราะห์และตัดสินใจเทรดทองคำ (Gold Trading) ด้วยสถาปัตยกรรม ReAct (Reasoning and Acting) โดยแบ่งการทำงานออกเป็น 2 ส่วนหลักคือ **Data Engine** (สำหรับดึงข้อมูลและคำนวณ Indicator) และ **Agent Core** (สำหรับให้ LLM วิเคราะห์และตัดสินใจ)

---

## 📂 Project Structure

โครงสร้างของโฟลเดอร์ในโปรเจกต์:

```text
CN240/
├── .venv/                      # Python Virtual Environment
├── Data/                       # โฟลเดอร์เก็บข้อมูลดิบหรือไฟล์ CSV ต่างๆ
├── Documentation/              # เอกสารอ้างอิงของโปรเจกต์
└── Src/                        # 🌟 โฟลเดอร์หลักของ Source Code
    │
    ├── agent_core/             # สมองของ AI (LLM & ReAct Loop)
    │   ├── config/             # ไฟล์ตั้งค่า Roles และ Skills ของ AI (.json)
    │   ├── core/               # ระบบหลัก: prompt.py (สร้าง Prompt) และ react.py (วงจร ReAct)
    │   ├── data/               # โฟลเดอร์รับข้อมูลที่ดึงมา (latest.json และ payload_*.json)
    │   ├── llm/                # ตัวจัดการเชื่อมต่อ API (Gemini, Groq, Mock)
    │   ├── tools/              # เครื่องมือ (Tools) ที่ AI สามารถเรียกใช้ได้
    │   ├── ARCHITECTURE_DESIGN.md
    │   └── IMPLEMENTATION_STEPS.md
    │
    ├── data_engine/            # ท่อส่งข้อมูล (Data Pipeline)
    │   ├── conJSON.py          # จัดการโครงสร้าง JSON
    │   ├── fetcher.py          # ดึงราคาทอง Spot, ทองไทย และค่าเงิน (Forex)
    │   ├── indicators.py       # คำนวณ Technical Indicators (RSI, MACD, Bollinger ฯลฯ)
    │   ├── newsfetcher.py      # ดึงข่าวสารการเงินตามหมวดหมู่ (yfinance)
    │   └── orchestrator.py     # ตัวคุมจังหวะ: รันไฟล์ด้านบนทั้งหมดแล้วเซฟเป็น latest.json
    │
    ├── execution/              # ระบบส่งคำสั่งซื้อขายจริง (สำหรับการพัฒนาในอนาคต)
    ├── tests/                  # โฟลเดอร์สำหรับ Unit Tests
    ├── ui/                     # User Interface (ถ้ามี)
    │
    ├── main.py                 # 🚀 ENTRY POINT: ไฟล์หลักสำหรับรันโปรแกรม
    ├── .gitignore              # ไฟล์กำหนดการละเว้นไฟล์ของ Git
    ├── README.md               # เอกสารอธิบายโปรเจกต์ (ไฟล์นี้)
    └── requirements.txt        # รายการ Library ที่ต้องใช้
```
---

# ⚙️ Prerequisites (การเตรียมความพร้อม)

## 1️⃣ เข้าสู่ Virtual Environment

**สำหรับ Mac/Linux:**
```bash
source .venv/bin/activate
```

**สำหรับ Windows:**
```bash
.venv\Scripts\activate
```

---

## 2️⃣ ติดตั้ง Library ที่จำเป็น

ย้ายไปที่โฟลเดอร์ `Src` ก่อน:
```bash
cd Src
```

จากนั้นติดตั้ง dependencies:
```bash
pip install -r requirements.txt
```

---

## 3️⃣ ตั้งค่า API Keys

#### ขั้นตอนที่ 1: สร้างไฟล์ `.env`

ไปที่โฟลเดอร์ `Src/` แล้วสร้างไฟล์ชื่อ `.env`:

**สำหรับ Mac/Linux (ใช้ Terminal):**
```bash
cd Src
nano .env
```

**สำหรับ Windows (ใช้ Text Editor):**
1. เปิด Notepad หรือ Visual Studio Code
2. สร้างไฟล์ใหม่
3. บันทึกชื่อ `.env` ในโฟลเดอร์ `Src/`

#### ขั้นตอนที่ 2: ใส่ API Keys ลงในไฟล์

ใส่เนื้อหาต่อไปนี้ลงในไฟล์ `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

#### ขั้นตอนที่ 3: บันทึกไฟล์

- **Mac/Linux (Nano):** กด `Ctrl + X` → `Y` → `Enter`
- **Windows (Notepad):** `Ctrl + S` และเลือก "All Files" แล้วบันทึกชื่อ `.env`

#### ขั้นตอนที่ 4: ตรวจสอบไฟล์
```bash
cat .env
```

ควรแสดงผล:
```
GEMINI_API_KEY=AIzaSyA1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r
GROQ_API_KEY=gsk_abcdef1234567890wxyz
```

---

## 🔐 ตรวจสอบการตั้งค่า

รันคำสั่งนี้เพื่อตรวจสอบว่า API Keys โหลดถูกต้อง:
```bash
python main.py --mock
```

หากไม่มีข้อผิดพลาด แสดงว่าตั้งค่าถูกต้องแล้ว! ✅

---

# 🚀 How to Run | วิธีใช้งาน

ไฟล์หลักที่ใช้ในการรันโปรแกรมคือ `main.py` ซึ่งอยู่ในโฟลเดอร์ `Src/`

## ⚠️ สำคัญ: ตรวจสอบตำแหน่ง Terminal

**ก่อนรันคำสั่ง ตรวจสอบให้แน่ใจว่า Terminal ของคุณอยู่ที่โฟลเดอร์ `Src`:**
```bash
cd Src
```

---

## 1️⃣ รันแบบครบวงจร (ดึงข้อมูลใหม่ + ให้ AI วิเคราะห์)

คำสั่งนี้จะไปเรียก `orchestrator` เพื่อดึงราคาทอง, คำนวณ Indicator, ดึงข่าวล่าสุด เซฟลงไฟล์ `latest.json` แล้วส่งให้ LLM วิเคราะห์

**ใช้ Gemini (Default):**
```bash
python main.py
```

**ระบุให้ใช้ Gemini แบบชัดเจน:**
```bash
python main.py --provider gemini
```

**ใช้ Groq:**
```bash
python main.py --provider groq
```

---

## 2️⃣ รัน AI โดยใช้ข้อมูลเดิม (ข้ามการดึงข้อมูลใหม่)

เหมาะสำหรับเวลาที่ต้องการ ทดสอบการปรับแต่ง Prompt หรือระบบ AI ซ้ำๆ โดยไม่อยากเสียเวลารอโหลดข่าวและราคาทองใหม่จากอินเทอร์เน็ต
```bash
python main.py --provider gemini --skip-fetch
```

หรือ:
```bash
python main.py --skip-fetch
```

---

## 3️⃣ รันโหมดจำลอง (Mock Mode)

สำหรับการทดสอบระบบ ReAct Loop ว่าทำงานถูกต้องหรือไม่ โดยไม่เสียโควต้า API (`LLMClient` จะใช้ผลลัพธ์จำลองแทนการเรียก API จริง)
```bash
python main.py --provider mock
```

หรือ:
```bash
python main.py --mock
```

---

## 📊 ตัวอย่างผลลัพธ์
```
🟡 GOLD ANALYSIS REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Current Price: 1,850.50 USD/oz
📈 Daily Change: +2.30%
🔍 Market Analysis: [AI Analysis Result]
💡 Recommendation: [AI Recommendation]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Team Members

| # | Student ID | Name |
| :---: | :---: | :--- | 
| 1 | 6710615292 | Athiphat Sunsit |
| 2 | 6710615185 | Purich Ampawa | 
| 3 | 6710685014 | Theepop Rattanasubsiri |
| 4 | 6710615060 | Chotiwit Daugstan | 
| 5 | 6710545010 | Napattira Loaklemhung | 
| 6 | 6710625028 | Benchaphon Pinakasa | 
| 7 | 6710615243 | Lalita Thatsananunchai | 
| 8 | 6710685055 | Phatcharaphon Malaisri | 
| 9 | 6710615284 | Sitthipong Kamngam | 
| 10 | 6710615144 | Panithan Tuntue | 

> All members actively contribute across every phase to build end-to-end Data Science experience.

---

> ⚠️ **Disclaimer:** This project is developed solely for academic purposes. Model outputs do not constitute financial or investment advice of any kind.
