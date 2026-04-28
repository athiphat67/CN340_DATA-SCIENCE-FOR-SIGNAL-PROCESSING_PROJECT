# Sentiment Model — DeBERTa + FinBERT Ensemble

> **ส่วนที่รับผิดชอบ:** News Sentiment Model  
> **ไฟล์ที่แก้:** `Src/data_engine/newsfetcher.py`

---

## ภาพรวม

ระบบ Sentiment เดิมใช้ **FinBERT** เพียงตัวเดียว ผ่าน HuggingFace Inference API  
ปัญหาคือ FinBERT accuracy อยู่ที่ ~80% และมีความเสี่ยงจาก API fail / rate limit

แนวทางแก้คือเพิ่ม **DeBERTa-v3** ที่รันแบบ local (ไม่พึ่ง API) และรวมเป็น **Ensemble**

```
ก่อน:  FinBERT HF API  →  sentiment_score
หลัง:  DeBERTa (local) × 0.6
     + FinBERT API    × 0.4
     ──────────────────────
       sentiment_score  (robust มากขึ้น)
```

---

## โมเดลที่ใช้

### 1. DeBERTa-v3 (Primary — Local)
| | |
|---|---|
| **Model ID** | `nickmuchi/deberta-v3-base-finetuned-finance-text-classification` |
| **Architecture** | DeBERTa-v3-base fine-tuned บน Financial PhraseBank |
| **Accuracy** | ~98% บน Financial PhraseBank dataset |
| **Labels** | `Bullish` / `Bearish` / `Neutral` |
| **ขนาด** | 738 MB |
| **รันที่** | Local (CPU) — ไม่ต้องใช้ API |

### 2. FinBERT (Secondary — HF API)
| | |
|---|---|
| **Model ID** | `ProsusAI/finbert` |
| **Architecture** | BERT fine-tuned บน financial corpus |
| **Accuracy** | ~80% บน Financial PhraseBank dataset |
| **Labels** | `positive` / `negative` / `neutral` |
| **รันที่** | HuggingFace Inference API (ต้องใช้ `HF_TOKEN`) |

---

## สูตร Ensemble

```
sentiment_score = (DeBERTa_score × 0.6) + (FinBERT_score × 0.4)
```

ทั้งสองโมเดล map ผลลัพธ์เป็น float ในช่วง `[-1.0, +1.0]`

| ช่วง | ความหมาย |
|---|---|
| > +0.1 | Bullish |
| -0.1 ถึง +0.1 | Neutral |
| < -0.1 | Bearish |

---

## Fallback Logic

ระบบออกแบบให้ทำงานได้แม้ขาด component ใดไป

```
DeBERTa ✅ + FinBERT ✅  →  Ensemble (ดีที่สุด)
DeBERTa ✅ + FinBERT ❌  →  DeBERTa อย่างเดียว (ไม่มี HF_TOKEN)
DeBERTa ❌ + FinBERT ✅  →  FinBERT อย่างเดียว (เหมือนเดิม)
DeBERTa ❌ + FinBERT ❌  →  คืน 0.0 (Neutral)
```

---

## การตั้งค่า

**ต้องมีใน `Src/.env`:**
```
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxx
```

ขอ token ได้ฟรีที่ [huggingface.co](https://huggingface.co) → Settings → Access Tokens → New token (Role: Read)

**ติดตั้ง dependencies:**
```bash
pip install transformers torch
```

DeBERTa จะดาวน์โหลด (~738 MB) อัตโนมัติจาก HuggingFace ตอนรันครั้งแรก  
ครั้งต่อไปจะ load จาก cache ทันที

---

## การใช้งานใน Pipeline

ไม่ต้องแก้โค้ดที่เรียก `newsfetcher` เพราะ interface เหมือนเดิมทุกอย่าง

```python
from data_engine.newsfetcher import GoldNewsFetcher

fetcher = GoldNewsFetcher()

# Sync
data = fetcher.to_dict()

# Async (แนะนำ)
data = await fetcher.to_dict_async()

# ดึง sentiment score
sentiment_score = data["overall_sentiment"]        # float [-1, +1]
market_bias     = data["by_category"]["market_bias"]  # "Bullish" / "Bearish" / "Neutral"
```

---

## ทดสอบ

สร้างไฟล์ `Src/test_sentiment.py` แล้วรัน:

```bash
cd Src
python test_sentiment.py
```

ผลที่คาดหวัง:
```
Ready: True
TEST: Score ข่าว
  Bullish  (+0.9371)  Gold price surges amid Fed rate cut hopes
  Bearish  (-0.9285)  Gold tumbles as dollar strengthens sharply
  Bearish  (-0.9266)  Gold trades flat in quiet Asian session

TEST: Ensemble (DeBERTa + FinBERT API)
  Bullish  (+0.2980)  Gold price surges amid Fed rate cut hopes
  Bearish  (-0.8633)  Gold tumbles as dollar strengthens sharply
  Bearish  (-0.9280)  Gold trades flat in quiet Asian session
```

> **หมายเหตุ:** `UNEXPECTED: deberta.embeddings.position_ids` ที่ขึ้นตอนโหลดโมเดล  
> เป็น warning ปกติ ไม่กระทบการทำงาน สามารถ ignore ได้

---

## ไฟล์ที่เปลี่ยน

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `Src/data_engine/newsfetcher.py` | เพิ่ม DeBERTa local scorer + ensemble logic |

ไม่มีไฟล์อื่นที่ถูกแก้ ทุก layer ที่เรียกใช้ `newsfetcher` ทำงานได้เหมือนเดิมโดยไม่ต้องแก้อะไรเพิ่ม

---

## เปรียบเทียบ ก่อน/หลัง

| | ก่อน | หลัง |
|---|---|---|
| โมเดล | FinBERT เดียว | DeBERTa + FinBERT Ensemble |
| Accuracy | ~80% | ~98% (DeBERTa) |
| Dependency | HF API เท่านั้น | Local + API |
| API fail | sentiment = 0.0 | fallback ไป DeBERTa local |
| Speed | ช้า (API roundtrip ทุกข่าว) | เร็วขึ้น (DeBERTa local) |
| Offline mode | ไม่รองรับ | รองรับ (DeBERTa only) |
