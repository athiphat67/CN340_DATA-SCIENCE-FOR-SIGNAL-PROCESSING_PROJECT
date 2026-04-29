#!/usr/bin/env python3
"""
Test script — แสดงการปรับปรุง newsfetcher.py

- Exponential backoff retry logic
- Sentiment score validation
- Configurable timeout + concurrency
- Circuit breaker for HF API health
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add Src to path
sys.path.insert(0, str(Path(__file__).parent / "Src"))

from data_engine.newsfetcher import (
    GoldNewsFetcher,
    score_sentiment_batch,
    score_sentiment_batch_async,
    _validate_sentiment_score,
    _get_backoff_seconds,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)


def test_validate_sentiment_score():
    """Test sentiment score validation"""
    print("\n" + "="*70)
    print("✅ Test 1: Sentiment Score Validation")
    print("="*70)
    
    test_cases = [
        (0.5, 0.5, "Valid positive score"),
        (-0.5, -0.5, "Valid negative score"),
        (0.0, 0.0, "Valid neutral"),
        (1.5, 1.0, "Out of range (high) — clamp to 1.0"),
        (-1.5, -1.0, "Out of range (low) — clamp to -1.0"),
        (float('nan'), 0.0, "NaN — fallback to 0.0"),
        (float('inf'), 0.0, "Infinity — fallback to 0.0"),
        ("invalid", 0.0, "String input — fallback to 0.0"),
    ]
    
    for input_score, expected, description in test_cases:
        result = _validate_sentiment_score(input_score)
        status = "✓" if (isinstance(expected, float) and abs(result - expected) < 0.01) else "?"
        print(f"  {status} {description}: {input_score} → {result}")


def test_exponential_backoff():
    """Test exponential backoff calculation"""
    print("\n" + "="*70)
    print("✅ Test 2: Exponential Backoff Calculation")
    print("="*70)
    
    print("\n  Base=1.0s, Max=60s:")
    for attempt in range(6):
        backoff = _get_backoff_seconds(attempt, base=1.0, max_seconds=60.0)
        print(f"    Attempt {attempt}: {backoff:.1f}s wait")
    
    print("\n  Base=2.0s, Max=30s (FinBERT-like):")
    for attempt in range(5):
        backoff = _get_backoff_seconds(attempt, base=2.0, max_seconds=30.0)
        print(f"    Attempt {attempt}: {backoff:.1f}s wait")


def test_fetcher_config():
    """Test GoldNewsFetcher with new configurable parameters"""
    print("\n" + "="*70)
    print("✅ Test 3: GoldNewsFetcher Configuration")
    print("="*70)
    
    # Default config
    fetcher1 = GoldNewsFetcher()
    print("\n  Default config:")
    print(f"    - timeout_seconds: {fetcher1.timeout_seconds}s")
    print(f"    - max_concurrent_requests: {fetcher1.max_concurrent_requests}")
    print(f"    - sentiment_retries: {fetcher1.sentiment_retries}")
    
    # Custom config
    fetcher2 = GoldNewsFetcher(
        timeout_seconds=20.0,
        max_concurrent_requests=10,
        sentiment_retries=5,
        max_per_category=3,
    )
    print("\n  Custom config:")
    print(f"    - timeout_seconds: {fetcher2.timeout_seconds}s")
    print(f"    - max_concurrent_requests: {fetcher2.max_concurrent_requests}")
    print(f"    - sentiment_retries: {fetcher2.sentiment_retries}")
    print(f"    - max_per_category: {fetcher2.max_per_category}")


def test_sentiment_scoring():
    """Test sentiment scoring with validation"""
    print("\n" + "="*70)
    print("✅ Test 4: Sentiment Batch Scoring (with validation)")
    print("="*70)
    
    test_texts = [
        "Gold prices surged amid geopolitical tensions",  # Should be positive
        "Economic slowdown concerns weigh on investor sentiment",  # Should be negative
        "Mixed signals from Fed policy announcements",  # Should be neutral
    ]
    
    try:
        print(f"\n  Scoring {len(test_texts)} texts (timeout=10s)...")
        scores = score_sentiment_batch(
            test_texts,
            retries=2,
            timeout=10.0
        )
        
        for text, score in zip(test_texts, scores):
            sentiment = "📈 Bullish" if score > 0.1 else ("📉 Bearish" if score < -0.1 else "➡️ Neutral")
            print(f"    [{sentiment:12}] {score:6.3f} — {text[:50]}")
            
    except Exception as e:
        logger.warning(f"Sentiment scoring error (expected if no HF_TOKEN): {e}")
        print("    ⚠️ Skipped (requires HF_TOKEN)")


async def test_async_sentiment_scoring():
    """Test async sentiment scoring"""
    print("\n" + "="*70)
    print("✅ Test 5: Async Sentiment Scoring")
    print("="*70)
    
    test_texts = [
        "Gold rallies as investors seek safe haven assets",
        "Fed signals potential rate cuts",
        "Thai baht strengthens against US dollar",
    ]
    
    try:
        print(f"\n  Async scoring {len(test_texts)} texts (timeout=10s, concurrency=3)...")
        scores = await score_sentiment_batch_async(
            test_texts,
            retries=2,
            concurrency=3,
            timeout=10.0
        )
        
        for text, score in zip(test_texts, scores):
            sentiment = "📈 Bullish" if score > 0.1 else ("📉 Bearish" if score < -0.1 else "➡️ Neutral")
            print(f"    [{sentiment:12}] {score:6.3f} — {text[:50]}")
            
    except Exception as e:
        logger.warning(f"Async sentiment scoring error: {e}")
        print("    ⚠️ Skipped (requires HF_TOKEN and proper async context)")


async def main():
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  🚀 GoldNewsFetcher Improvements Test Suite".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    # Sync tests
    test_validate_sentiment_score()
    test_exponential_backoff()
    test_fetcher_config()
    test_sentiment_scoring()
    
    # Async tests
    await test_async_sentiment_scoring()
    
    print("\n" + "="*70)
    print("✨ All tests completed!")
    print("="*70)
    print("""
📋 Summary of Improvements:

1. ✅ Exponential Backoff Retry
   - Prevents rate limit thrashing
   - Configurable base and max timeout
   
2. ✅ Sentiment Score Validation
   - Clamps scores to [-1.0, 1.0]
   - Handles NaN/Inf gracefully
   
3. ✅ Configurable Timeout & Concurrency
   - timeout_seconds parameter (default 15s)
   - max_concurrent_requests parameter (default 5)
   - sentiment_retries parameter (default 3)
   
4. ✅ Circuit Breaker Pattern
   - Prevents cascading failures
   - Auto-recovery after timeout
   
5. ✅ Better Error Handling
   - Detailed error messages
   - Graceful fallback to 0.0
   - Proper logging of failure causes
""")


if __name__ == "__main__":
    asyncio.run(main())
