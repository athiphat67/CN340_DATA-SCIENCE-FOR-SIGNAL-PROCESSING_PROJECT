#!/usr/bin/env python3
"""
update_newsfetcher_with_finetuned.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Integration guide: Update newsfetcher.py to use fine-tuned DeBERTa model

After fine-tuning completes, run this script to:
1. Verify fine-tuned model can load
2. Test on sample texts
3. Compare accuracy with base model
4. Provide integration code

วิธีใช้:
  cd /Users/sitthipong.kam/CN240
  python Src/update_newsfetcher_with_finetuned.py
"""

import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForSequenceClassification

FINETUNED_PATH = "Src/models/finetuned_sentiment/deberta/best_model"
BASE_MODEL = "nickmuchi/deberta-v3-base-finetuned-finance-text-classification"

print("\n" + "="*70)
print("🔍 Fine-tuned DeBERTa Integration Check")
print("="*70)

# Check if fine-tuned model exists
model_path = Path(FINETUNED_PATH)
if not model_path.exists():
    print(f"\n⚠️  Fine-tuned model not found at: {FINETUNED_PATH}")
    print("Please run: python Src/finetune_sentiment_simple.py")
    exit(1)

print(f"\n✓ Fine-tuned model found at: {FINETUNED_PATH}")

# Load fine-tuned model
print("\n📥 Loading fine-tuned model...")
try:
    tokenizer = AutoTokenizer.from_pretrained(FINETUNED_PATH)
    model = AutoModelForSequenceClassification.from_pretrained(FINETUNED_PATH)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    model = model.to(device)
    print(f"✓ Model loaded on {device}")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    exit(1)

# Test on sample texts
print("\n🧪 Testing fine-tuned model on sample news headlines...")
test_texts = [
    "Gold prices surge amid geopolitical tensions and risk-off sentiment",
    "Fed signals potential interest rate cuts ahead of inflation data",
    "Dollar strengthens as economic data beats expectations",
    "Stock market tumbles on recession fears and earnings misses",
    "Gold mining stocks rally as bullion prices recover from losses",
]

label_map = {0: "Neutral", 1: "Bullish", 2: "Bearish"}

model.eval()
with torch.no_grad():
    for text in test_texts:
        encoding = tokenizer(
            text,
            max_length=128,
            truncation=True,
            padding="max_length",
            return_tensors="pt"
        )
        input_ids = encoding["input_ids"].to(device)
        attention_mask = encoding["attention_mask"].to(device)
        
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=1)
        pred_label = torch.argmax(logits, dim=1).item()
        confidence = probs[0, pred_label].item()
        
        label_text = label_map[pred_label]
        emoji = "📈" if pred_label == 1 else "📉" if pred_label == 2 else "➡️"
        
        print(f"\n  {emoji} {label_text:8} ({confidence:.1%})")
        print(f"     {text[:60]}...")

# Provide integration code
print("\n" + "="*70)
print("📝 Integration Code")
print("="*70)

integration_code = '''
# Add this to Src/data_engine/newsfetcher.py

# === FINE-TUNED DEBERTA SETUP ===
_finetuned_deberta_pipe = None

def _get_finetuned_deberta_pipe():
    """Load fine-tuned DeBERTa model (lazy-load once)"""
    global _finetuned_deberta_pipe
    if _finetuned_deberta_pipe is None:
        from transformers import pipeline
        try:
            _finetuned_deberta_pipe = pipeline(
                "sentiment-analysis",
                model="Src/models/finetuned_sentiment/deberta/best_model",
                device=0 if torch.cuda.is_available() else -1
            )
            logger.info("✓ Fine-tuned DeBERTa loaded")
        except Exception as e:
            logger.warning(f"Failed to load fine-tuned DeBERTa, falling back to base: {e}")
            return _get_deberta_pipe()
    return _finetuned_deberta_pipe

def _score_deberta_finetuned_one(text: str) -> float:
    """Score single text with fine-tuned DeBERTa"""
    if not text or not isinstance(text, str):
        return 0.0
    
    text = text[:512]  # Truncate
    pipe = _get_finetuned_deberta_pipe()
    
    try:
        result = pipe(text)[0]
        label = result["label"]  # "LABEL_0", "LABEL_1", "LABEL_2"
        score = result["score"]
        
        # Map labels: 0=Neutral, 1=Bullish, 2=Bearish
        label_idx = int(label.split("_")[1])
        
        if label_idx == 1:  # Bullish
            return score
        elif label_idx == 2:  # Bearish
            return -score
        else:  # Neutral
            return 0.0
    except Exception as e:
        logger.warning(f"Fine-tuned DeBERTa scoring error: {e}")
        return 0.0

# === UPDATED ENSEMBLE WEIGHTS ===
# If using fine-tuned DeBERTa, increase its weight:
_DEBERTA_WEIGHT = 0.7  # Increased from 0.6
_FINBERT_WEIGHT = 0.3  # Decreased from 0.4

# === UPDATE score_sentiment_one() ===
def score_sentiment_one(text: str) -> float:
    """Ensemble with fine-tuned DeBERTa"""
    if not text or not isinstance(text, str):
        return 0.0
    
    deberta_score = _score_deberta_finetuned_one(text)
    
    # Optional: Add FinBERT if API available
    try:
        finbert_score = _score_finbert_one(text)
    except:
        finbert_score = 0.0
    
    ensemble_score = (_DEBERTA_WEIGHT * deberta_score + 
                     _FINBERT_WEIGHT * finbert_score)
    
    return _validate_sentiment_score(ensemble_score)
'''

print(integration_code)

print("\n" + "="*70)
print("✅ Integration Ready")
print("="*70)
print("\nSteps to integrate:")
print("1. Copy the code above")
print("2. Paste into Src/data_engine/newsfetcher.py")
print("3. Test with: python Src/test_sentiment.py")
print("4. Monitor logs for fine-tuned model loading")
