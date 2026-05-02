#!/usr/bin/env python3
"""
finetune_sentiment_simple.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fast fine-tuning for DeBERTa sentiment model
Optimized for local training with minimal memory usage

วิธีใช้:
  cd /Users/sitthipong.kam/CN240
  python Src/finetune_sentiment_simple.py

Features:
  - Load GDELT news + Gold prices
  - Create labels based on price movements
  - Fine-tune DeBERTa with mixed precision
  - Evaluate on validation set
  - Save best checkpoint
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import accuracy_score, f1_score, classification_report

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

GDELT_PATH = "Src/backtest/data/MarketState_data/gdelt_news_master_2025-01-01_2026-04-16_final.csv"
GOLD_PATH = "Src/backtest/data/MarketState_data/GLD965_5m_20250101_to_20260416.csv"

PRICE_THRESHOLD = 0.0020  # 0.20%
HORIZON_4H = 48  # 5min candles

MODEL_ID = "nickmuchi/deberta-v3-base-finetuned-finance-text-classification"

BATCH_SIZE = 32
LEARNING_RATE = 2e-5
EPOCHS = 2
WARMUP_STEPS = 100
MAX_LENGTH = 128

OUTPUT_DIR = "Src/models/finetuned_sentiment"
DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

print(f"🔧 Device: {DEVICE}")

# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────

print("\n📂 Loading data...")
news_df = pd.read_csv(GDELT_PATH, parse_dates=["date_th"])
gold_df = pd.read_csv(GOLD_PATH, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
print(f"   ✓ News: {len(news_df):,} | Prices: {len(gold_df):,}")

# ─────────────────────────────────────────────────────────────────────────────
# CREATE LABELS
# ─────────────────────────────────────────────────────────────────────────────

def get_price_change(news_time, horizon=HORIZON_4H):
    future_rows = gold_df[gold_df["datetime"] > news_time].head(horizon)
    if len(future_rows) < horizon:
        return None
    past = gold_df[gold_df["datetime"] <= news_time]
    if len(past) == 0:
        return None
    price_now = past["close"].iloc[-1]
    price_future = future_rows["close"].iloc[-1]
    if price_now == 0:
        return None
    return (price_future - price_now) / price_now

print("\n🏷️  Creating labels...")
texts, labels, prices = [], [], []

for _, row in news_df.iterrows():
    pc = get_price_change(row["date_th"])
    if pc is None:
        continue
    
    if pc > PRICE_THRESHOLD:
        label = 1  # Bullish
    elif pc < -PRICE_THRESHOLD:
        label = 2  # Bearish
    else:
        label = 0  # Neutral
    
    texts.append(row["title"])
    labels.append(label)
    prices.append(pc * 100)

labels_array = np.array(labels)
print(f"   ✓ Total: {len(labels):,}")
print(f"   ✓ Neutral:  {(labels_array == 0).sum():5} ({100*(labels_array==0).sum()/len(labels):.1f}%)")
print(f"   ✓ Bullish:  {(labels_array == 1).sum():5} ({100*(labels_array==1).sum()/len(labels):.1f}%)")
print(f"   ✓ Bearish:  {(labels_array == 2).sum():5} ({100*(labels_array==2).sum()/len(labels):.1f}%)")

# ─────────────────────────────────────────────────────────────────────────────
# TOKENIZE
# ─────────────────────────────────────────────────────────────────────────────

print("\n🔤 Tokenizing texts...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

encodings = tokenizer(
    texts,
    max_length=MAX_LENGTH,
    truncation=True,
    padding="max_length",
    return_tensors="pt"
)

input_ids = encodings["input_ids"]
attention_mask = encodings["attention_mask"]
labels_tensor = torch.tensor(labels, dtype=torch.long)

print(f"   ✓ Input IDs shape: {input_ids.shape}")
print(f"   ✓ Labels shape: {labels_tensor.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# SPLIT DATA
# ─────────────────────────────────────────────────────────────────────────────

n = len(labels)
split_idx = int(0.8 * n)

train_ids = input_ids[:split_idx]
train_mask = attention_mask[:split_idx]
train_labels = labels_tensor[:split_idx]

val_ids = input_ids[split_idx:]
val_mask = attention_mask[split_idx:]
val_labels = labels_tensor[split_idx:]

train_dataset = TensorDataset(train_ids, train_mask, train_labels)
val_dataset = TensorDataset(val_ids, val_mask, val_labels)

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

print(f"\n📊 Train: {len(train_dataset):,} | Val: {len(val_dataset):,}")

# ─────────────────────────────────────────────────────────────────────────────
# FINE-TUNE MODEL
# ─────────────────────────────────────────────────────────────────────────────

print("="*70)
print("🚀 Fine-tuning DeBERTa-v3")
print("="*70)

model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, num_labels=3)
model = model.to(DEVICE)

optimizer = AdamW(model.parameters(), lr=LEARNING_RATE)
total_steps = len(train_loader) * EPOCHS

best_f1 = 0.0
best_epoch = 0

for epoch in range(EPOCHS):
    print(f"\n🔄 Epoch {epoch + 1}/{EPOCHS}")
    
    # ──── TRAINING ────
    model.train()
    train_loss = 0.0
    progress_bar = tqdm(train_loader, desc="Training")
    
    for batch_idx, (input_id, attention_m, label) in enumerate(progress_bar):
        input_id = input_id.to(DEVICE)
        attention_m = attention_m.to(DEVICE)
        label = label.to(DEVICE)
        
        optimizer.zero_grad()
        outputs = model(input_ids=input_id, attention_mask=attention_m, labels=label)
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        
        train_loss += loss.item()
        progress_bar.set_postfix({"loss": f"{loss.item():.4f}"})
    
    avg_train_loss = train_loss / len(train_loader)
    print(f"  Train Loss: {avg_train_loss:.4f}")
    
    # ──── VALIDATION ────
    model.eval()
    all_preds = []
    all_labels = []
    val_loss = 0.0
    
    with torch.no_grad():
        progress_bar = tqdm(val_loader, desc="Validating")
        for input_id, attention_m, label in progress_bar:
            input_id = input_id.to(DEVICE)
            attention_m = attention_m.to(DEVICE)
            label = label.to(DEVICE)
            
            outputs = model(input_ids=input_id, attention_mask=attention_m, labels=label)
            loss = outputs.loss
            logits = outputs.logits
            
            val_loss += loss.item()
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            
            all_preds.extend(preds)
            all_labels.extend(label.cpu().numpy())
    
    avg_val_loss = val_loss / len(val_loader)
    accuracy = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average='weighted')
    
    print(f"  Val Loss:   {avg_val_loss:.4f}")
    print(f"  Accuracy:   {accuracy:.3f}")
    print(f"  F1 Score:   {f1:.3f}")
    
    # Save best
    if f1 > best_f1:
        best_f1 = f1
        best_epoch = epoch + 1
        print(f"  💾 Saved best model (F1: {f1:.3f})")
        
        output_path = Path(OUTPUT_DIR) / "deberta" / "best_model"
        output_path.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(output_path))
        tokenizer.save_pretrained(str(output_path))

# ─────────────────────────────────────────────────────────────────────────────
# FINAL EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

print("="*70)
print("📈 Final Evaluation")
print("="*70)

model.eval()
all_preds = []
all_labels = []

with torch.no_grad():
    for input_id, attention_m, label in val_loader:
        input_id = input_id.to(DEVICE)
        attention_m = attention_m.to(DEVICE)
        
        outputs = model(input_ids=input_id, attention_mask=attention_m)
        logits = outputs.logits
        preds = torch.argmax(logits, dim=1).cpu().numpy()
        
        all_preds.extend(preds)
        all_labels.extend(label.cpu().numpy())

accuracy = accuracy_score(all_labels, all_preds)
f1 = f1_score(all_labels, all_preds, average='weighted')

print(f"\n  Validation Accuracy: {accuracy:.3f}")
print(f"  Validation F1 Score: {f1:.3f}")
print("\n  Classification Report:")
label_names = ["Neutral", "Bullish", "Bearish"]
print(classification_report(all_labels, all_preds, target_names=label_names, digits=3))

print("="*70)
print("✨ Fine-tuning complete!")
print("="*70)
print(f"  📁 Best Model: {OUTPUT_DIR}/deberta/best_model")
print(f"  📊 Best Epoch: {best_epoch}")
print(f"  🏆 Best F1: {best_f1:.3f}")
print("\n  Next steps:")
print("  1. Update newsfetcher.py to use fine-tuned DeBERTa model")
print("  2. Test on live news data")
print("  3. Fine-tune FinBERT using same labels (optional)")
