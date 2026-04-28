"""
evaluate_sentiment.py
เปรียบเทียบ DeBERTa vs FinBERT vs Ensemble
บนข้อมูลข่าวจริงของโปรเจกต์ + ราคาทองไทยจริง

วิธีใช้:
    cd Src
    python evaluate_sentiment.py

Logic:
    - สำหรับแต่ละข่าว → หาราคาทองในช่วง 1h และ 4h หลังข่าว
    - ถ้าราคาขึ้น > THRESHOLD → True Label = Bullish
    - ถ้าราคาลง > THRESHOLD → True Label = Bearish
    - เปรียบ sentiment score ของแต่ละโมเดลกับ True Label
    - คิด Accuracy / Precision / Recall / F1
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import timedelta
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

# ── Config ────────────────────────────────────────────────────────────────────
GDELT_PATH = "backtest/data/MarketState_data/gdelt_news_master_2025-01-01_2026-04-16_final.csv"
GOLD_PATH  = "backtest/data/MarketState_data/GLD965_5m_20250101_to_20260416.csv"

PRICE_THRESHOLD = 0.0020   # 0.20% ตรงกับ TARGET_MOVE_PCT ของโปรเจกต์
HORIZON_1H  = 12           # 5min × 12 = 1 ชั่วโมง
HORIZON_4H  = 48           # 5min × 48 = 4 ชั่วโมง
SAMPLE_SIZE = 300          # จำนวนข่าวที่ใช้เทส (ลดเวลา DeBERTa)
SENTIMENT_THRESHOLD = 0.1  # |score| > นี้ถึงนับว่า directional


def load_data():
    print("📂 โหลดข้อมูล...")
    news = pd.read_csv(GDELT_PATH, parse_dates=["date_th"])
    gold = pd.read_csv(GOLD_PATH,  parse_dates=["datetime"])
    gold = gold.sort_values("datetime").reset_index(drop=True)
    print(f"   ข่าว: {len(news):,} rows | ราคาทอง: {len(gold):,} rows")
    return news, gold


def get_price_change(gold: pd.DataFrame, news_time, horizon_bars: int) -> float | None:
    """หา % เปลี่ยนแปลงของราคาในช่วง horizon หลังจากเวลาข่าว"""
    future_rows = gold[gold["datetime"] > news_time].head(horizon_bars)
    if len(future_rows) < horizon_bars:
        return None
    price_now    = gold[gold["datetime"] <= news_time]["close"].iloc[-1] if len(gold[gold["datetime"] <= news_time]) > 0 else None
    price_future = future_rows["close"].iloc[-1]
    if price_now is None or price_now == 0:
        return None
    return (price_future - price_now) / price_now


def to_label(score: float, threshold: float = SENTIMENT_THRESHOLD) -> str:
    if score >  threshold: return "Bullish"
    if score < -threshold: return "Bearish"
    return "Neutral"


def evaluate(y_true: list, y_pred: list, name: str):
    """คำนวณและแสดง metrics"""
    # กรอง Neutral ออก (เทสเฉพาะ directional)
    pairs = [(t, p) for t, p in zip(y_true, y_pred) if t != "Neutral"]
    if not pairs:
        print(f"  ⚠️  {name}: ไม่มีข้อมูล directional")
        return {}

    yt = [p[0] for p in pairs]
    yp = [p[1] for p in pairs]

    acc = accuracy_score(yt, yp)
    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")
    print(f"  Directional samples : {len(yt):,}")
    print(f"  Accuracy            : {acc:.1%}")
    print(classification_report(yt, yp, labels=["Bullish","Bearish"], zero_division=0))

    cm = confusion_matrix(yt, yp, labels=["Bullish","Bearish"])
    print(f"  Confusion Matrix (Bullish/Bearish):")
    print(f"              Pred Bull  Pred Bear")
    print(f"  True Bull      {cm[0][0]:4d}       {cm[0][1]:4d}")
    print(f"  True Bear      {cm[1][0]:4d}       {cm[1][1]:4d}")
    return {"name": name, "accuracy": acc, "samples": len(yt)}


def main():
    news, gold = load_data()

    # ── Sample ข่าว ────────────────────────────────────────────────────────────
    # เน้น gold_news ก่อน เพราะเกี่ยวกับทองโดยตรง
    gold_news = news[news["primary_theme"] == "gold_news"]
    other_news = news[news["primary_theme"] != "gold_news"]

    n_gold  = min(len(gold_news), SAMPLE_SIZE // 2)
    n_other = min(len(other_news), SAMPLE_SIZE - n_gold)

    sample = pd.concat([
        gold_news.sample(n_gold, random_state=42),
        other_news.sample(n_other, random_state=42),
    ]).reset_index(drop=True)

    print(f"\n📰 Sample ข่าว: {len(sample)} rows "
          f"(gold_news={n_gold}, other={n_other})")

    # ── คำนวณ True Label จากราคาทองจริง ────────────────────────────────────────
    print("\n📈 คำนวณ True Label จากราคาทอง (4h horizon)...")
    true_labels = []
    valid_idx   = []

    for i, row in sample.iterrows():
        change = get_price_change(gold, row["date_th"], HORIZON_4H)
        if change is None:
            continue
        if   change >  PRICE_THRESHOLD: label = "Bullish"
        elif change < -PRICE_THRESHOLD: label = "Bearish"
        else:                            label = "Neutral"
        true_labels.append(label)
        valid_idx.append(i)

    valid_sample = sample.loc[valid_idx].copy()
    valid_sample["true_label"] = true_labels

    print(f"   ข่าวที่ match กับราคา: {len(valid_sample)}")
    print(f"   True Label distribution: {pd.Series(true_labels).value_counts().to_dict()}")

    # ── FinBERT Score (มีอยู่แล้วในไฟล์) ───────────────────────────────────────
    print("\n🤖 FinBERT (จาก GDELT pre-scored)...")
    valid_sample["finbert_label"] = valid_sample["sentiment_score"].apply(to_label)

    # ── DeBERTa Score (รันใหม่) ────────────────────────────────────────────────
    print("\n🧠 DeBERTa-v3 (local model)...")
    from data_engine.newsfetcher import _get_deberta_pipe, _score_deberta_one

    _get_deberta_pipe()  # warm up

    deberta_scores = []
    total = len(valid_sample)
    for idx, (_, row) in enumerate(valid_sample.iterrows()):
        if idx % 50 == 0:
            print(f"   [{idx}/{total}] scoring...")
        score = _score_deberta_one(str(row["title"]))
        deberta_scores.append(score if score is not None else 0.0)

    valid_sample["deberta_score"] = deberta_scores
    valid_sample["deberta_label"] = valid_sample["deberta_score"].apply(to_label)

    # ── Ensemble Score ─────────────────────────────────────────────────────────
    valid_sample["ensemble_score"] = (
        valid_sample["deberta_score"]  * 0.6 +
        valid_sample["sentiment_score"] * 0.4
    )
    valid_sample["ensemble_label"] = valid_sample["ensemble_score"].apply(to_label)

    # ── Evaluate ───────────────────────────────────────────────────────────────
    print("\n\n📊 ผลการเปรียบเทียบ (เทียบกับทิศทางราคาทองจริงในช่วง 4h)")

    results = []
    for model_col, name in [
        ("finbert_label",  "FinBERT (เดิม)"),
        ("deberta_label",  "DeBERTa-v3 (ใหม่)"),
        ("ensemble_label", "Ensemble DeBERTa×0.6 + FinBERT×0.4"),
    ]:
        r = evaluate(
            y_true=valid_sample["true_label"].tolist(),
            y_pred=valid_sample[model_col].tolist(),
            name=name,
        )
        if r:
            results.append(r)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("  สรุปเปรียบเทียบ Accuracy")
    print(f"{'='*55}")
    for r in sorted(results, key=lambda x: x["accuracy"], reverse=True):
        bar = "█" * int(r["accuracy"] * 30)
        print(f"  {r['name']:<40} {r['accuracy']:.1%}  {bar}")

    best = max(results, key=lambda x: x["accuracy"])
    print(f"\n  🏆 ดีที่สุด: {best['name']} ({best['accuracy']:.1%})")

    # ── Export ─────────────────────────────────────────────────────────────────
    out_path = "sentiment_eval_result.csv"
    valid_sample[[
        "date_th", "title", "primary_theme",
        "true_label",
        "sentiment_score", "finbert_label",
        "deberta_score", "deberta_label",
        "ensemble_score", "ensemble_label",
    ]].to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n  💾 บันทึกผลละเอียดที่: Src/{out_path}")


if __name__ == "__main__":
    main()
