# 🚀 newsfetcher.py Improvements — Summary

**Date**: April 29, 2025 (Phase 2.3 Enhancement)

## 📋 Overview

Implemented **5 high-priority improvements** to `Src/data_engine/newsfetcher.py` to increase reliability, stability, and observability of the news fetching & sentiment analysis pipeline.

---

## ✅ Improvements Implemented

### 1️⃣ **Exponential Backoff Retry Logic** 🔄

**Problem**: Fixed 3 retries immediately (back-to-back) → triggers rate limiting, wastes resources

**Solution**: 
- Added `_get_backoff_seconds(attempt, base, max_seconds)` helper
- Exponential backoff: 1s, 2s, 4s, 8s... (max configurable)
- Applied to both `_score_finbert_api_one()` (sync) and `score_sentiment_batch_async()` (async)

**Code Example**:
```python
backoff = _get_backoff_seconds(attempt, base=2.0, max_seconds=30.0)
# attempt=0 → 2.0s, attempt=1 → 4.0s, attempt=2 → 8.0s
time.sleep(backoff)
```

**Impact**: 
- ✅ Prevents API rate limit violations
- ✅ Reduces unnecessary retries
- ✅ Better integration with rate limit headers (Retry-After)

---

### 2️⃣ **Sentiment Score Validation** 📊

**Problem**: No validation that sentiment scores stay within [-1.0, 1.0] → NaN/Inf/outliers crash weighted averaging

**Solution**:
- Added `_validate_sentiment_score(score)` helper
- Validates score is float in range [-1.0, 1.0]
- Clamps out-of-range values to valid bounds
- Returns 0.0 for NaN/Inf/invalid types
- Logs warnings for anomalies

**Code Example**:
```python
# Before
final = _DEBERTA_WEIGHT * deberta_score + _FINBERT_WEIGHT * finbert_score

# After
final = _validate_sentiment_score(
    _DEBERTA_WEIGHT * deberta_score + _FINBERT_WEIGHT * finbert_score
)
```

**Impact**:
- ✅ Prevents NaN/Inf propagation through weighted average
- ✅ Ensures sentiment always in valid range
- ✅ Easier debugging of score anomalies

---

### 3️⃣ **Configurable Timeout & Concurrency** ⏱️

**Problem**: Hardcoded values (timeout=10s/25s, concurrency=5) → can't adapt to network conditions

**Solution**:
- Added 3 new parameters to `GoldNewsFetcher.__init__()`:
  - `timeout_seconds: float = 15.0` (RSS/yfinance requests)
  - `max_concurrent_requests: int = 5` (Semaphore limit in async sentiment)
  - `sentiment_retries: int = 3` (retry count for FinBERT)
- All HTTP calls now use `self.timeout_seconds`
- Used in: RSS fetches, yfinance requests, httpx clients, sentiment API calls

**Code Example**:
```python
fetcher = GoldNewsFetcher(
    timeout_seconds=20.0,      # Longer for slow networks
    max_concurrent_requests=10,  # More parallelism
    sentiment_retries=5,        # More resilient
)
```

**Impact**:
- ✅ Adapts to different network speeds
- ✅ Prevents unnecessary timeouts or hanging
- ✅ Better resource utilization

---

### 4️⃣ **Circuit Breaker Pattern for HF API** 🔴🟡🟢

**Problem**: If HF API is down, keep retrying → wastes time, overloads API, cascading failures

**Solution**:
- Added `APICircuitBreaker` class with 3 states:
  - 🟢 **CLOSED**: Normal operation, process requests
  - 🔴 **OPEN**: API failed ≥5 times, skip requests (return 0.0)
  - 🟡 **HALF-OPEN**: After 120s, try recovery (one request)
- Integrated into `_score_finbert_api_one()` with `record_success()` / `record_failure()`

**Code Example**:
```python
# In _score_finbert_api_one
if not _hf_circuit_breaker.can_attempt():
    logger.warning("⛔ Circuit Breaker OPEN: skip FinBERT API")
    return 0.0

# ... try request ...

if success:
    _hf_circuit_breaker.record_success()  # Reset counter
else:
    _hf_circuit_breaker.record_failure()  # Increment counter
```

**Impact**:
- ✅ Prevents cascading failures when API is down
- ✅ Reduces unnecessary load on failing API
- ✅ Graceful degradation (use DeBERTa local model only)
- ✅ Auto-recovery after timeout

---

### 5️⃣ **Improved Error Handling & Logging** 📝

**Problem**: Generic error messages, unclear what failed and why → hard to troubleshoot

**Solution**:
- Added specific error tracking:
  - Timeout vs ConnectionError vs generic exception
  - Capture last error message for final failure log
  - Add error context (attempt #, timeout value, etc.)
- Better fallback logic:
  - If HF API fails but DeBERTa available → use DeBERTa only
  - If both fail → use score 0.0 (neutral sentiment)
- Clearer logging hierarchy:
  - 🔴 ERROR: Final failure after all retries
  - ⚠️ WARNING: Transient failures with retry attempt info
  - 🔵 INFO: Expected delays (rate limit, model loading)
  - 🟢 DEBUG: Per-request success logs

**Code Example**:
```python
logger.error(
    f"FinBERT API ล้มเหลวหลังจาก {retries} ครั้ง — "
    f"ใช้ fallback 0.0 [สาเหตุสุดท้าย: {last_error}]"
)
```

**Impact**:
- ✅ Easier to diagnose API issues
- ✅ Better monitoring and alerting
- ✅ Clear understanding of fallback behavior

---

## 🔧 Configuration Examples

### Default (backward compatible):
```python
fetcher = GoldNewsFetcher()
# timeout_seconds=15.0
# max_concurrent_requests=5
# sentiment_retries=3
```

### High-latency network (slow connection):
```python
fetcher = GoldNewsFetcher(
    timeout_seconds=30.0,       # Wait longer for RSS
    max_concurrent_requests=3,  # Less parallelism
    sentiment_retries=5,        # More patient retries
)
```

### High-speed network (fast connection):
```python
fetcher = GoldNewsFetcher(
    timeout_seconds=8.0,        # Quick timeout
    max_concurrent_requests=15, # More parallelism
    sentiment_retries=2,        # Quick fail-fast
)
```

---

## 🧪 Testing

Run test suite to verify improvements:

```bash
cd /Users/sitthipong.kam/CN240
python test_newsfetcher_improvements.py
```

Tests cover:
1. Sentiment score validation (clamp, NaN/Inf handling)
2. Exponential backoff calculation
3. GoldNewsFetcher configuration
4. Sentiment batch scoring (with timeout)
5. Async sentiment scoring

---

## 📊 Impact Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Retry Strategy** | Fixed 3x, no delay | Exponential backoff (1s, 2s, 4s...) |
| **Score Validation** | None | ✅ Clamp to [-1.0, 1.0] |
| **Timeout** | Hardcoded 10/25s | Configurable (default 15s) |
| **Concurrency** | Hardcoded 5 | Configurable (default 5) |
| **Error Recovery** | Fail loud | Circuit breaker + graceful fallback |
| **Error Logging** | Generic | Detailed with context |
| **API Failure Mode** | Cascading | Graceful degradation |

---

## 🎯 Next Steps (Medium Priority)

From the original recommendations, these are still pending:

1. **Duplicate Detection Enhancement** — Add fuzzy title matching
2. **Token Budget Enforcement** — Cut titles instead of skipping articles
3. **Cache Invalidation** — Add TTL + force-refresh option
4. **Sentiment Distribution Monitoring** — Log bullish/bearish/neutral histogram
5. **RSS Keywords Matching** — Upgrade from simple `in` check to NLP-based

---

## 📚 Files Modified

- `Src/data_engine/newsfetcher.py` — Core improvements
- `test_newsfetcher_improvements.py` — Test suite (new)

---

**Status**: ✅ **COMPLETE** — All 5 high-priority improvements implemented and tested
