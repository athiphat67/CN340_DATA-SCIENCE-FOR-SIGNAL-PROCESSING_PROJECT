#!/usr/bin/env python3
"""
finetune_sentiment_model.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fine-tune DeBERTa-v3 + FinBERT ให้ตรงกับข้อมูลข่าวและราคาทองจริง

Pipeline:
  1. โหลดข้อมูล: GDELT news + Gold prices
  2. สร้าง labels: Bullish/Bearish/Neutral (จากการเคลื่อนไหวราคา)
  3. Split data: train / validation
  4. Fine-tune: DeBERTa + FinBERT
  5. Evaluate: เปรียบเทียบความแม่นยำ

วิธีใช้:
  cd /Users/sitthipong.kam/CN240
  python Src/finetune_sentiment_model.py

Requirements:
  - torch, transformers, datasets, scikit-learn, pandas

Author: Gold Trading Agent
Date: 2026-04-30
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
import warnings

import torch
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    Trainer, TrainingArguments, EarlyStoppingCallback,
)
from datasets import Dataset
from sklearn.metrics import classification_report, accuracy_score, f1_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

GDELT_PATH = "Src/backtest/data/MarketState_data/gdelt_news_master_2025-01-01_2026-04-16_final.csv"
GOLD_PATH  = "Src/backtest/data/MarketState_data/GLD965_5m_20250101_to_20260416.csv"

PRICE_THRESHOLD = 0.0020  # 0.20% movement threshold
HORIZON_4H = 48  # 5min × 48 = 4 hours (default horizon)

# Model configs
DEBERTA_MODEL = "nickmuchi/deberta-v3-base-finetuned-finance-text-classification"
FINBERT_MODEL = "ProsusAI/finbert"

# Training params
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
EPOCHS = 3
VALIDATION_SPLIT = 0.2
EARLY_STOPPING_PATIENCE = 2
MAX_LENGTH = 128

OUTPUT_DIR = "Src/models/finetuned_sentiment"
LOG_DIR = "Src/logs/finetuning"

# Device
DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

print(f"🔧 Device: {DEVICE}")
print(f"📊 Batch Size: {BATCH_SIZE}, LR: {LEARNING_RATE}, Epochs: {EPOCHS}")

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING & LABELING
# ─────────────────────────────────────────────────────────────────────────────

def load_data():
    """โหลดข้อมูล GDELT news และ Gold prices"""
    print("\n📂 Loading data...")
    
    # Load news
    news_df = pd.read_csv(GDELT_PATH, parse_dates=["date_th"])
    print(f"   ✓ GDELT News: {len(news_df):,} articles")
    
    # Load gold prices
    gold_df = pd.read_csv(GOLD_PATH, parse_dates=["datetime"])
    gold_df = gold_df.sort_values("datetime").reset_index(drop=True)
    print(f"   ✓ Gold Prices: {len(gold_df):,} 5-min candles")
    
    return news_df, gold_df

def get_price_change(gold_df: pd.DataFrame, news_time, horizon_bars: int) -> float | None:
    """หา % เปลี่ยนแปลงของราคาในช่วง horizon หลังจากเวลาข่าว"""
    future_rows = gold_df[gold_df["datetime"] > news_time].head(horizon_bars)
    
    if len(future_rows) < horizon_bars:
        return None
    
    # หาราคาปัจจุบัน
    past_rows = gold_df[gold_df["datetime"] <= news_time]
    if len(past_rows) == 0:
        return None
    
    price_now = past_rows["close"].iloc[-1]
    price_future = future_rows["close"].iloc[-1]
    
    if price_now == 0:
        return None
    
    return (price_future - price_now) / price_now

def create_labels(news_df: pd.DataFrame, gold_df: pd.DataFrame, threshold: float = PRICE_THRESHOLD) -> pd.DataFrame:
    """
    สร้าง labels: Bullish (1) / Neutral (0) / Bearish (-1)
    โดยใช้การเปลี่ยนแปลงของราคาทองในช่วง 4 ชั่วโมง
    """
    print("\n🏷️  Creating labels from price movements...")
    
    labels = []
    valid_indices = []
    
    for idx, row in news_df.iterrows():
        news_time = row["date_th"]
        title = row["title"]
        
        # หาราคาเปลี่ยนแปลงในช่วง 4 ชั่วโมง
        price_change = get_price_change(gold_df, news_time, HORIZON_4H)
        
        if price_change is None:
            continue
        
        # ตัดสินใจ label
        if price_change > threshold:
            label = 1  # Bullish
            label_name = "BULLISH"
        elif price_change < -threshold:
            label = -1  # Bearish
            label_name = "BEARISH"
        else:
            label = 0  # Neutral
            label_name = "NEUTRAL"
        
        labels.append({
            "text": title,
            "label": label,
            "label_name": label_name,
            "price_change": round(price_change * 100, 3),
            "news_time": news_time,
        })
        valid_indices.append(idx)
    
    labeled_df = pd.DataFrame(labels)
    
    print(f"   ✓ Total labeled samples: {len(labeled_df):,}")
    print("\n   Label distribution:")
    for label_name in ["BULLISH", "NEUTRAL", "BEARISH"]:
        count = (labeled_df["label_name"] == label_name).sum()
        pct = 100 * count / len(labeled_df)
        print(f"     {label_name:8}: {count:4} ({pct:5.1f}%)")
    
    return labeled_df

# ─────────────────────────────────────────────────────────────────────────────
# DATASET PREPARATION
# ─────────────────────────────────────────────────────────────────────────────

def prepare_dataset(labeled_df: pd.DataFrame, tokenizer, test_size: float = VALIDATION_SPLIT):
    """
    แปลง DataFrame เป็น HF Dataset พร้อม tokenization
    """
    print("\n⚙️  Preparing datasets...")
    
    # สร้าง HF Dataset
    dataset = Dataset.from_pandas(labeled_df[["text", "label"]])
    
    # Remove label -1 (Bearish) temporarily - convert to 1 for binary classification
    # Actually, let's keep it ternary: 0=Neutral, 1=Bullish, 2=Bearish
    def normalize_label(example):
        if example["label"] == -1:
            example["label"] = 2  # Bearish -> 2
        return example
    
    dataset = dataset.map(normalize_label)
    
    # Tokenize
    def tokenize_fn(batch):
        return tokenizer(
            batch["text"],
            max_length=MAX_LENGTH,
            truncation=True,
            padding="max_length",
        )
    
    dataset = dataset.map(tokenize_fn, batched=True, remove_columns=["text"])
    dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])
    
    # Split
    split_dataset = dataset.train_test_split(test_size=test_size, seed=42)
    
    print(f"   ✓ Train: {len(split_dataset['train']):,}")
    print(f"   ✓ Val:   {len(split_dataset['test']):,}")
    
    return split_dataset

# ─────────────────────────────────────────────────────────────────────────────
# EVALUATION METRICS
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(eval_preds):
    """Compute accuracy, F1, classification report"""
    predictions, labels = eval_preds
    predictions = np.argmax(predictions, axis=1)
    
    accuracy = accuracy_score(labels, predictions)
    f1 = f1_score(labels, predictions, average='weighted')
    
    return {
        "accuracy": accuracy,
        "f1": f1,
    }

# ─────────────────────────────────────────────────────────────────────────────
# FINE-TUNING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def finetune_deberta(train_dataset, val_dataset, tokenizer):
    """Fine-tune DeBERTa model"""
    print("\n" + "="*70)
    print("🎯 Fine-tuning DeBERTa-v3...")
    print("="*70)
    
    model = AutoModelForSequenceClassification.from_pretrained(
        DEBERTA_MODEL,
        num_labels=3,
        trust_remote_code=True,
    ).to(DEVICE)
    
    output_dir = Path(OUTPUT_DIR) / "deberta"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=LEARNING_RATE,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        warmup_steps=100,
        weight_decay=0.01,
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        save_total_limit=2,
        push_to_hub=False,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=EARLY_STOPPING_PATIENCE,
                early_stopping_threshold=0.001,
            )
        ],
    )
    
    print("⏳ Training DeBERTa...")
    trainer.train()
    
    print("\n✅ DeBERTa training complete!")
    return model, trainer

def finetune_finbert(train_dataset, val_dataset, tokenizer):
    """Fine-tune FinBERT model"""
    print("\n" + "="*70)
    print("🎯 Fine-tuning FinBERT...")
    print("="*70)
    
    model = AutoModelForSequenceClassification.from_pretrained(
        FINBERT_MODEL,
        num_labels=3,
        trust_remote_code=True,
    ).to(DEVICE)
    
    output_dir = Path(OUTPUT_DIR) / "finbert"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=LEARNING_RATE * 1.5,  # FinBERT may need different LR
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        warmup_steps=100,
        weight_decay=0.01,
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        save_total_limit=2,
        push_to_hub=False,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=EARLY_STOPPING_PATIENCE,
                early_stopping_threshold=0.001,
            )
        ],
    )
    
    print("⏳ Training FinBERT...")
    trainer.train()
    
    print("\n✅ FinBERT training complete!")
    return model, trainer

# ─────────────────────────────────────────────────────────────────────────────
# EVALUATION & COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_model(model, tokenizer, val_dataset, model_name: str):
    """Evaluate a single model"""
    print(f"\n📊 Evaluating {model_name}...")
    
    model.eval()
    all_preds = []
    all_labels = []
    
    for batch in torch.utils.data.DataLoader(val_dataset, batch_size=BATCH_SIZE):
        with torch.no_grad():
            inputs = {k: v.to(DEVICE) for k, v in batch.items() if k != "label"}
            labels = batch["label"].to(DEVICE)
            
            outputs = model(**inputs)
            logits = outputs.logits
            preds = torch.argmax(logits, dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
    
    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    
    accuracy = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average='weighted')
    
    print(f"\n  {model_name} Results:")
    print(f"  Accuracy: {accuracy:.3f}")
    print(f"  F1 Score: {f1:.3f}")
    
    label_names = ["Neutral", "Bullish", "Bearish"]
    print("\n  Classification Report:")
    print(classification_report(all_labels, all_preds, target_names=label_names, digits=3))
    
    return {"accuracy": accuracy, "f1": f1, "preds": all_preds, "labels": all_labels}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*70)
    print("🚀 DeBERTa + FinBERT Fine-tuning Pipeline")
    print("="*70)
    
    # 1. Load data
    news_df, gold_df = load_data()
    
    # 2. Create labels
    labeled_df = create_labels(news_df, gold_df)
    
    if len(labeled_df) < 100:
        print(f"\n⚠️  Warning: Only {len(labeled_df)} labeled samples. Consider adjusting PRICE_THRESHOLD.")
    
    # 3. Prepare datasets
    tokenizer_deberta = AutoTokenizer.from_pretrained(DEBERTA_MODEL)
    dataset_dict = prepare_dataset(labeled_df, tokenizer_deberta)
    
    train_dataset = dataset_dict["train"]
    val_dataset = dataset_dict["test"]
    
    # 4. Fine-tune DeBERTa
    deberta_model, deberta_trainer = finetune_deberta(train_dataset, val_dataset, tokenizer_deberta)
    
    # 5. Fine-tune FinBERT
    tokenizer_finbert = AutoTokenizer.from_pretrained(FINBERT_MODEL)
    finbert_model, finbert_trainer = finetune_finbert(train_dataset, val_dataset, tokenizer_finbert)
    
    # 6. Evaluate both models
    print("\n" + "="*70)
    print("📈 Evaluation Results")
    print("="*70)
    
    deberta_results = evaluate_model(deberta_model, tokenizer_deberta, val_dataset, "DeBERTa")
    finbert_results = evaluate_model(finbert_model, tokenizer_finbert, val_dataset, "FinBERT")
    
    # 7. Save best models
    print("\n" + "="*70)
    print("💾 Saving Models...")
    print("="*70)
    
    deberta_model.save_pretrained(f"{OUTPUT_DIR}/deberta/best_model")
    tokenizer_deberta.save_pretrained(f"{OUTPUT_DIR}/deberta/best_model")
    
    finbert_model.save_pretrained(f"{OUTPUT_DIR}/finbert/best_model")
    tokenizer_finbert.save_pretrained(f"{OUTPUT_DIR}/finbert/best_model")
    
    print(f"✅ Models saved to: {OUTPUT_DIR}")
    
    # 8. Summary
    print("\n" + "="*70)
    print("📊 Summary")
    print("="*70)
    print(f"Training samples: {len(train_dataset):,}")
    print(f"Validation samples: {len(val_dataset):,}")
    print(f"\nDeBERTa Accuracy: {deberta_results['accuracy']:.3f} | F1: {deberta_results['f1']:.3f}")
    print(f"FinBERT Accuracy: {finbert_results['accuracy']:.3f} | F1: {finbert_results['f1']:.3f}")
    
    better = "DeBERTa" if deberta_results['accuracy'] > finbert_results['accuracy'] else "FinBERT"
    print(f"\n🏆 Better Model: {better}")
    
    print("\n✨ Fine-tuning complete!")
    print(f"📁 Models location: {OUTPUT_DIR}")
    print("📝 Next: Update newsfetcher.py to use fine-tuned models")

if __name__ == "__main__":
    main()
