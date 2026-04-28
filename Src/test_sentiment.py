import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_engine.newsfetcher import _get_deberta_pipe, _score_deberta_one

print("TEST: โหลด DeBERTa")
pipe = _get_deberta_pipe()
print("Ready:", pipe is not None)

print("\nTEST: Score ข่าว")
headlines = [
    "Gold price surges amid Fed rate cut hopes",
    "Gold tumbles as dollar strengthens sharply",
    "Gold trades flat in quiet Asian session",
]
for h in headlines:
    score = _score_deberta_one(h)
    label = "Bullish" if score > 0.1 else ("Bearish" if score < -0.1 else "Neutral")
    print(f"  {label:8} ({score:+.4f})  {h}")

print("\nTEST: Ensemble (DeBERTa + FinBERT API)")
from data_engine.newsfetcher import score_sentiment_batch
scores = score_sentiment_batch(headlines)
for h, s in zip(headlines, scores):
    label = "Bullish" if s > 0.1 else ("Bearish" if s < -0.1 else "Neutral")
    print(f"  {label:8} ({s:+.4f})  {h[:50]}")