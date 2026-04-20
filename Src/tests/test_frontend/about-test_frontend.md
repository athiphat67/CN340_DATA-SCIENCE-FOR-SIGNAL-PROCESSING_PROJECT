# เอกสาร QA: โฟลเดอร์ `test_frontend`

---

## 1. Overview

โฟลเดอร์ `tests/test_frontend/` ทดสอบสองส่วนที่เชื่อมต่อกัน:

1. **Backend API** ของ Frontend — `Src/frontend/api/main.py` (FastAPI, 13 endpoints)
2. **React Components** — data-fetching components จาก `Src/frontend/components/`

แนวทาง: **API tests รันด้วย pytest (Python)** + **Component tests รันด้วย Vitest (Node)** — แยก 2 runner แต่ share fixtures/fakes ผ่านความ deterministic

### วัตถุประสงค์หลัก

| วัตถุประสงค์ | รายละเอียด |
|------------|-----------|
| **API Contract** | ตรวจ response shape, status codes, DB SQL shape |
| **Component Isolation** | Render component โดยไม่ต้องมี backend จริง ใช้ MSW intercept fetch |
| **Error Resilience** | UI ไม่ crash เมื่อ API 500/404/network down |
| **Determinism** | Fixtures frozen, no Date.now(), no random |
| **DB Isolation** | Test ไม่ต่อ Postgres จริง — monkeypatch `RunDatabase` + `supabase.create_client` |

### สถิติ

| เมตริก | จำนวน |
|--------|-------|
| API Test Files | 13 ไฟล์ (test_api_*.py) + 1 CORS + 1 smoke |
| Component Test Files | 3 ไฟล์ (SignalDetail, StatsStack, BacktestSection) |
| API Test Functions | ~60 |
| Component Test Functions | 27 (8 + 11 + 8) — **ผ่านทั้งหมด 27/27** |
| Endpoints ที่ครอบ | 13 / 13 (100%) |
| Components ที่ครอบ | 3 / 12 (representative patterns) |

---

## 2. Directory Structure

```
tests/
├── fakes.py                         # Shared: FakeCursor/FakeConnection/FakeDB/FakeSupabase
└── test_frontend/
    ├── about-test_frontend.md       # เอกสารนี้
    ├── SETUP.md                     # Steps: npm install + junction + npm run test
    ├── conftest.py                  # Scoped fixtures: env monkeypatch + client + fake_db
    ├── __init__.py                  # empty
    │
    ├── vitest.config.ts             # ⚠️ DEPRECATED stub (config จริงย้ายไป Src/frontend/)
    ├── vitest.setup.ts              # RTL + MSW lifecycle + Recharts mock
    ├── node_modules/                # ⚠️ Junction → ../../frontend/node_modules (ดูหัวข้อ 9.1)
    │
    ├── __mocks__/
    │   ├── handlers.ts              # MSW handlers — 13 endpoints
    │   ├── fixtures.ts              # Deterministic JSON fixtures
    │   └── server.ts                # MSW Node server
    │
    ├── components/
    │   ├── SignalDetail.test.tsx    # single-fetch + router
    │   ├── StatsStack.test.tsx      # parallel + polling 30s
    │   └── BacktestSection.test.tsx # complex parallel + retry + error banner
    │
    ├── test_smoke.py                # conftest sanity check
    ├── test_api_latest_signal.py
    ├── test_api_signal_detail.py
    ├── test_api_portfolio.py
    ├── test_api_gold_prices.py      # รวม sync_latest_price side-effect
    ├── test_api_recent_signals.py
    ├── test_api_market_state.py
    ├── test_api_performance_chart.py
    ├── test_api_active_positions.py # ✅ raise 500 on DB error (fix 2026-04-20)
    ├── test_api_market_bias.py      # ✅ raise 500 on DB error (fix 2026-04-20)
    ├── test_api_agent_health.py     # ✅ raise 500 on DB error (fix 2026-04-20)
    ├── test_api_backtest_summary.py
    ├── test_api_backtest_trades.py
    ├── test_api_backtest_equity_curve.py
    └── test_api_cors.py
```

### Coverage Map

```
Production Module                          ← Test File
──────────────────────────────────────────────────────────────────
Src/frontend/api/main.py                   ← test_api_*.py (13 files + CORS)
Src/frontend/components/signals/SignalDetail.tsx
                                           ← components/SignalDetail.test.tsx
Src/frontend/components/overview/StatsStack.tsx
                                           ← components/StatsStack.test.tsx
Src/frontend/components/backtest/BacktestSection.tsx
                                           ← components/BacktestSection.test.tsx
```

---

## 3. Testing Strategy

### 3.1 API Tests (pytest + httpx.TestClient)

**Isolation pattern**:
1. `tests/test_frontend/conftest.py` ตั้ง dummy env vars ก่อน import ANYTHING
2. Monkeypatch `database.database.RunDatabase` → `FakeDB` **ก่อน** `frontend.api.main` โหลด
3. Monkeypatch `supabase.create_client` → lambda คืน `FakeSupabase`
4. Import `frontend.api.main` — `db = RunDatabase()` ใน main.py จะเป็น FakeDB

**Why**: `frontend.api.main` มี side effect หนักที่ module level (`db = RunDatabase()` สร้าง `ThreadedConnectionPool` eagerly + `supabase.create_client(url, key)` ตายถ้า url ว่าง)

**Fixtures**:
```python
def test_xxx(client, fake_db):
    fake_db.set_fetchone({"id": 1, "signal": "BUY"})   # คุม cursor.fetchone()
    fake_db.set_fetchall([{...}, {...}])               # คุม cursor.fetchall()
    fake_db.set_raise(Exception("boom"))               # cursor.execute raise
    fake_db.set_portfolio({...})                       # คุม .get_portfolio()

    r = client.get("/api/xxx")
    assert r.status_code == 200

    # ตรวจ SQL shape
    sql, params = fake_db.last_cursor.executed[-1]
    assert "ORDER BY id DESC" in sql
```

### 3.2 Component Tests (Vitest + RTL + MSW)

**Tooling**:
- **Vitest** — fast test runner, shares Vite config
- **React Testing Library** — user-centric component queries
- **MSW (Mock Service Worker)** — intercept `fetch()` ที่ network layer
- **jsdom** — browser-like environment
- **@testing-library/user-event** — simulate user interactions

**Isolation pattern**: MSW server รันใน `beforeAll`, override handlers per-test ด้วย `server.use(...)`

**Deterministic polling**: ใช้ `vi.useFakeTimers()` + `vi.advanceTimersByTimeAsync()` คุม 30s interval

### 3.3 Fakes (`tests/fakes.py`)

Shared **pure Python classes** — ไม่ import FastAPI หรือ frontend.api.main

```python
FakeCursor       → execute() log, fetchone/fetchall configurable, raise on demand
FakeConnection   → context manager yield cursor, commit/rollback counter
FakeDB           → get_connection() CM, get_portfolio() dict, set_* helpers
FakeSupabase     → chainable .table().select().order().limit().execute()
```

---

## 4. What is Being Tested

### 4.1 API — 13 Endpoints

| Endpoint | Happy Path | 404 / Empty | 500 / DB Error | Query Params |
|----------|-----------|-------------|----------------|--------------|
| `GET /api/latest-signal` | ✓ | 404 (no rows) | 500 | — |
| `GET /api/signals/{id}` | ✓ | 404 | 500 | ✓ (invalid id → 422) |
| `GET /api/portfolio` | ✓ formulas | zero-safe | 500 | — |
| `GET /api/gold-prices` | ✓ + sync | 404 | 500 | — |
| `GET /api/recent-signals?limit=` | ✓ | [] | 500 | ✓ (invalid limit → 422) |
| `GET /api/market-state` | ✓ | 404 | 500 | — |
| `GET /api/performance-chart?limit=` | ✓ format | [] | 500 (custom msg) | ✓ |
| `GET /api/active-positions` | ✓ format | [] | 500 | — |
| `GET /api/market-bias` | BUY→Bullish etc. | neutral default | 500 | — |
| `GET /api/agent-health` | stable/warning | — | 500 | — |
| `GET /api/backtest/summary?model=` | ✓ | 404 | 500 | ✓ |
| `GET /api/backtest/trades?model=&signal=&limit=` | ✓ format | [] | 500 | ✓ (invalid signal ignored) |
| `GET /api/backtest/equity-curve?model=&limit=` | ✓ format | [] | 500 | ✓ |
| CORS preflight | ✓ | — | — | — |

**✅ Fixed 2026-04-20**: 3 endpoints (`active-positions`, `market-bias`, `agent-health`)
เดิมคืน fallback dict/list เมื่อ DB ล่ม (silent error) — แก้แล้วให้ raise 500 ตรงกับ endpoint อื่น
เพื่อให้ UI แสดง error state ได้ถูกต้อง (ดูรายละเอียดใน §7.2)

### 4.2 Component — 3 Representative

| Component | Pattern | Tests |
|-----------|---------|-------|
| `SignalDetail` | single-fetch, `useParams`, loading state, trace_json parsing | 8 |
| `StatsStack` | parallel fetch (2 APIs), polling (setInterval spy), confidence normalization | 11 |
| `BacktestSection` | parallel fetch (3 APIs), error banner, retry button, fallback, router wrap | 8 |

---

## 5. How to Run

### API tests (Python)

**ทุกคำสั่งรันจาก directory `Src/`**

```bash
# ทั้งหมด
python -m pytest tests/test_frontend/ -v

# ไฟล์เดียว
python -m pytest tests/test_frontend/test_api_portfolio.py -v

# เฉพาะ smoke
python -m pytest tests/test_frontend/test_smoke.py -v

# dry-run (เห็น test ทั้งหมดที่จะรัน)
python -m pytest tests/test_frontend/ --collect-only
```

### Component tests (Node)

**First-time setup** (ดูรายละเอียดใน `SETUP.md`):
```bash
cd Src/frontend
npm install
# สร้าง junction หนึ่งครั้ง:
cd ../tests/test_frontend
mklink /J node_modules ..\..\frontend\node_modules   # Windows
# หรือ: ln -s ../../frontend/node_modules node_modules  # macOS/Linux
```

**รัน tests**:
```bash
cd Src/frontend
npm run test             # รันครั้งเดียว
npm run test:watch       # watch mode
npm run test:ui          # browser UI
npm run test:coverage    # + coverage
```

### รันทั้งสองฝั่งพร้อมกัน

```bash
# Terminal 1
cd Src && python -m pytest tests/test_frontend/ -v

# Terminal 2
cd Src/frontend && npm run test
```

---

## 6. QA Standards

### 6.1 Negative Test Rule

ทุก test class (ทั้ง Python + TS) ต้องมีอย่างน้อย **3 negative tests**:
1. **API 500 / DB error** — UI ไม่ crash หรือ API คืน 500 ตามที่ spec ระบุ
2. **API returns empty** (`{}`, `[]`, `None`) — UI หรือ API handle gracefully
3. **Boundary / invalid input** — ไม่ crash

### 6.2 Determinism Rule

- **ห้าม** `new Date()` / `Date.now()` ใน assertion — mock ด้วย `vi.setSystemTime()`
- **ห้าม** `Math.random()` ใน fixtures
- Fixtures ใน `__mocks__/fixtures.ts` — frozen JSON objects
- Polling tests → `vi.useFakeTimers()` + `vi.advanceTimersByTimeAsync()`

### 6.3 SQL Contract Rule

API test ต้องมี **1 test per endpoint** ที่ตรวจ SQL shape:
```python
fake_db.set_fetchone({"id": 1})
client.get("/api/xxx?limit=10")
sql, params = fake_db.last_cursor.executed[-1]
assert "ORDER BY id DESC" in sql
assert params == (10,)
```

### 6.4 No Production Code Mutation

**Default rule** (QA role):
ห้าม:
- แก้ `.tsx` / `.ts` ใน `Src/frontend/components/` หรือ `Src/frontend/pages/`
- แก้ `Src/frontend/api/main.py`
- แก้ `tests/conftest.py` เดิม (backtest fixtures)

อนุญาต:
- แก้ `Src/frontend/package.json` **เฉพาะ** `devDependencies` + `scripts`
- เพิ่มไฟล์ใหม่ใน `tests/test_frontend/`
- เพิ่ม `tests/fakes.py` (shared, no side effect)

**Exception** — findings 7.1–7.4 (fixed 2026-04-20): ได้รับอนุมัติเป็นกรณีพิเศษ
ให้แก้ production code (`Src/frontend/api/main.py` + 6 React components) พร้อม
update test ตาม Tech Debt Rule — finding เหล่านี้เป็น real bug/architectural
issue ไม่ใช่แค่ style

---

## 7. Findings & Resolutions

> **สรุป**: 7.1–7.4 ได้รับอนุมัติพิเศษให้แก้ production code แล้ว (2026-04-20)
> — รายละเอียดแต่ละข้อบันทึก root cause, fix, และ **ผลกระทบถ้าไม่แก้** (worst-case
> analysis) ไว้เพื่อเป็น reference สำหรับ dev คนต่อไป

### 7.1 URL Inconsistency ระหว่าง Components — ✅ FIXED 2026-04-20

**ปัญหาเดิม**: 6 components hardcode `http://localhost:8000`, 7 ใช้
`import.meta.env.VITE_API_URL`:

| Hardcoded (เดิม) | Env-based |
|-----------|-----------|
| `PortfolioSection`, `PortfolioMarketBias`, `PortfolioActivePositions`, `AgentHealthMonitor`, `GrossPnL`, `SignalPerformanceChart` | `SignalDetail`, `StatsStack`, `SignalMasterTable`, `SignalLogTable`, `RecentlySignal`, `BacktestSection` (hybrid: `?? 'http://localhost:8000'`) |

**Fix**: เปลี่ยนทั้ง 6 ไฟล์ให้ใช้ hybrid pattern เดียวกับส่วนอื่น:
```ts
`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api/xxx`
```

**⚠️ ผลกระทบถ้าไม่แก้ — Worst-case analysis**:

1. **Production deploy ใช้งานไม่ได้เลย**: เวลา deploy frontend ขึ้น Vercel/Netlify/
   Cloudflare Pages แล้ว backend อยู่บน Railway/Render/AWS → browser ของ user จะ
   ยิง `fetch('http://localhost:8000/...')` ไปที่ **เครื่องของ user เอง** ไม่ใช่
   backend จริง → 6 ส่วนของหน้าเว็บจะเป็น blank/loading ถาวร:
   - Portfolio card (เงินสด, P&L, trades today)
   - Market Bias indicator (ทิศทางตลาด)
   - Active Positions table
   - Agent Health Monitor (latency, API status)
   - Gross PnL + Market State (หน้า overview)
   - Signal Performance Chart (กราฟหลัก)

2. **Partial-broken UX หลอก user**: 7 components ที่ใช้ env var จะทำงานปกติ
   (SignalDetail, StatsStack, Recent Signals ฯลฯ) → user เห็นข้อมูลบางส่วน
   ดูเหมือนเว็บ "work" แต่จริง ๆ ขาด data จาก 6 ส่วน → user อาจตัดสินใจ
   trade ทองด้วยข้อมูลไม่ครบ (project นี้ทำ signal trading ฟีเจอร์ที่ขาดคือ
   portfolio + active positions — ข้อมูลสำคัญที่สุดที่ user ต้องดูก่อน trade)

3. **CORS console spam**: browser block localhost fetch จาก domain อื่น
   → error messages กองใน console → debug ยากเพราะ 6 errors ซ้อนกัน

4. **ทีม support ไม่สามารถช่วย remote**: user ส่งรูป screenshot มาให้ดู
   dev ไม่สามารถ reproduce ได้เพราะเครื่อง dev มี backend รันบน localhost:8000
   — เห็นทุกอย่าง work ปกติ

**หมายเหตุ test**: MSW ใช้ `*/api/...` wildcard pattern → component test ยังผ่าน
ทั้งก่อนและหลัง fix (ไม่ต้องแก้ test)

---

### 7.2 Silent 500 Endpoints (3 ตัว) — ✅ FIXED 2026-04-20

**ปัญหาเดิม**: `active-positions`, `market-bias`, `agent-health` ดัก `except Exception`
แล้วคืน default dict/list แทนที่จะ raise 500 — ทำให้ frontend เห็น HTTP 200 ทุกครั้ง
ถึงจะ DB ล่มก็ตาม

**Fix**: เปลี่ยนจาก `return {...default}` เป็น
`raise HTTPException(status_code=500, detail=str(e))` ทั้ง 3 endpoints
(คง `print(...)` ไว้เป็น server-side log)

**⚠️ ผลกระทบถ้าไม่แก้ — Worst-case analysis**:

1. **Silent data corruption ในสายตา user**: `active-positions` คืน `[]` เมื่อ DB
   ล่ม → frontend แปลผลเป็น "ไม่มี position เปิดอยู่" → user คิดว่า trade
   ทั้งหมดถูกปิดแล้ว → **ตัดสินใจเปิด position ใหม่ซ้อนทับ** → ผิด position
   size limit ของ Aom NOW (฿1,400/ตัว) → อาจติด force-close

2. **Market Bias หลอกให้ trade ผิดทิศ**: DB ล่ม → endpoint คืน
   `{direction: "Neutral", conviction: 0, reason: "System synchronization..."}`
   → user เห็น "Neutral" คิดว่า AI ยังวิเคราะห์อยู่ → รอ signal → จริง ๆ
   backend ตายแล้ว signal ล่าสุดอาจเก่าเกิน 10 นาที → user trade จาก signal
   เก่าที่ไม่ valid แล้ว

3. **Agent Health แสดงสถานะเท็จ**: endpoint คืน `api_status: "Offline"`
   เมื่อ error → **แต่ HTTP 200** → frontend component ไม่เข้า catch block
   → ไม่แสดง "Connection Lost" banner → user ไม่รู้ว่าระบบล่ม → **ใช้ระบบ
   ต่อไปโดยไว้ใจ**

4. **Monitoring blind spot**: ถ้าใช้ external APM (Sentry, Datadog)
   ตรวจ HTTP 500 rate → endpoint เหล่านี้ **never raise** → ไม่มี alert
   → DB ล่มหลายชั่วโมงก่อนจะมีคนสังเกต

5. **ผิด REST contract**: endpoint อื่น (latest-signal, gold-prices ฯลฯ)
   raise 500 เมื่อ error → 3 endpoints นี้เป็น exception → frontend
   ต้องเขียน logic พิเศษ if/else ซึ่งไม่มีใครทำ → inconsistency กลายเป็น
   พิษต่อ codebase ระยะยาว

**Test update**: 3 tests เปลี่ยน assertion จาก `status_code == 200` + default dict
เป็น `status_code == 500` + assert `detail contains error message`

---

### 7.3 Module-level Side Effects ใน `main.py` — ✅ FIXED 2026-04-20

**ปัญหาเดิม**:
- `db = RunDatabase()` line 28 → สร้าง ThreadedConnectionPool ทันทีที่ import
- `supabase = create_client(url, key)` line 34 → raise `supabase_url is required`
  ถ้า `url=None` พร้อม stack trace ยาว ไม่บอกว่าต้องแก้ `.env` ตัวไหน

**Fix**: เพิ่ม guard ก่อน `create_client`:
```python
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
if not url or not key:
    raise RuntimeError("❌ ต้องตั้ง SUPABASE_URL และ SUPABASE_KEY ใน Src/.env")
supabase: Client = create_client(url, key)
```

**⚠️ ผลกระทบถ้าไม่แก้ — Worst-case analysis**:

1. **Dev onboarding เสียเวลาหลายชั่วโมง**: dev ใหม่ `git clone` → `pip install`
   → `uvicorn frontend.api.main:app` → crash ทันทีพร้อม error
   `supabase_url is required` จาก supabase-py internal → ไม่มีใครรู้ว่า
   ต้องใส่อะไรใน `.env` → ต้องเปิด source code supabase library อ่าน
   → ค้นใน Slack/Discord → ถาม senior → **เสียเวลา 1–2 ชั่วโมงต่อคน**
   (onboarding friction = technical debt tax)

2. **Deploy fail silent ใน CI/CD**: ถ้า deploy platform (Railway, Fly.io)
   ลืมใส่ env → startup command ตาย → container restart loop → platform
   อาจ mark เป็น "unhealthy" หลัง 3–5 retries → deploy fail แต่ไม่มีใคร
   อ่าน log container → ทีมคิดว่าเป็นปัญหา network/DB → ไล่ผิดจุด

3. **Error message ไม่ actionable**: stack trace จาก supabase-py
   ลึกไป 4 levels — เห็นครั้งแรกต้องใช้เวลาอ่านเข้าใจว่าต้นทางคือ
   `os.getenv("SUPABASE_URL")` คืน None → ในขณะที่ RuntimeError ใหม่
   บอกตรง ๆ "ใส่ใน Src/.env" → **1 บรรทัดอ่านเข้าใจแทน 20 บรรทัด**

4. **Test isolation แค่ขอบ ไม่ใช่ defense-in-depth**: `conftest.py`
   monkeypatch ก่อน import ได้ แต่ถ้า dev คนอื่นเขียน integration test
   ใหม่แล้วลืม monkeypatch → test crash ตอน collection phase (import
   ก่อน fixture setup) → error message งง → debug ยาก

5. **ขาด fail-fast principle**: module-level crash ก็ยัง "fast" อยู่
   — แต่**ไม่ clear** → guard ใหม่ยัง fail-fast **และ clear** ทั้งคู่

**หมายเหตุ**: `db = RunDatabase()` eager-init ยังไม่ได้แก้ (scope นี้แก้แค่
supabase) — ถ้า `DATABASE_URL` หายก็ยัง crash แต่ `RunDatabase()` มี
`print()` บอก path ของ `.env` อยู่แล้ว (line 22) → priority ต่ำกว่า

---

### 7.4 HTTPException(404) ถูก wrap เป็น 500 — ✅ FIXED 2026-04-20

**ปัญหาเดิม**: `except Exception` จับ `HTTPException(404)` ด้วย (เพราะเป็น subclass)
แล้ว re-raise เป็น 500 — กระทบ **5 endpoints**: `latest-signal`, `signals/{id}`,
`gold-prices`, `market-state`, `performance-chart` (เชิงป้องกัน)

**Pattern ที่ผิด**:
```python
try:
    ...
    raise HTTPException(status_code=404, detail="No signals found")
except Exception as e:  # ← ดัก HTTPException ด้วย!
    raise HTTPException(status_code=500, detail=str(e))
```

**Fix** (pattern เดียวกับ `/api/backtest/summary` line 381):
```python
except HTTPException:
    raise              # ← ให้ HTTPException ผ่านไปก่อน
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

**⚠️ ผลกระทบถ้าไม่แก้ — Worst-case analysis**:

1. **UX fatal**: `/api/latest-signal` คืน 500 เมื่อยังไม่มี signal record ใน DB
   (DB ใหม่, เพิ่งรีเซ็ต, หลัง migration) → หน้า homepage แสดง
   "🚨 Server Error — try again later" ทั้งที่ไม่ได้มีอะไรเสีย → user
   panic คิดว่าระบบล่ม → refresh หลายรอบ → กด support

2. **Monitoring false alarm**: APM metric `http_5xx_rate` พุ่งทุกครั้งที่ DB
   ยังไม่มี signal → on-call engineer ตื่นกลางดึก → ไล่ดูทุก endpoint →
   ไม่เจอ bug เพราะมันเป็น 404 ปกติที่ถูก misreport → **alert fatigue**
   ทำให้คนเริ่ม ignore alert จริง

3. **404 vs 500 เป็น signal ทาง REST ที่สำคัญ**:
   - 404 = "ไม่มีข้อมูลนี้" → UI แสดง empty state "No signals yet"
   - 500 = "server พัง" → UI แสดง error banner + retry button
   - 2 สถานะนี้มี UX ตรงข้ามกัน → แปล 404 เป็น 500 = ระบบโกหก frontend

4. **Frontend logic ซับซ้อนเกินเหตุ**: ถ้าไม่แก้ → frontend dev ต้องเขียน
   `if (res.status === 500 && body.detail.includes('No signals'))` เพื่อ
   แยก real-500 กับ fake-500 → **ผูกตัวเองเข้ากับ detail string**
   ที่เปลี่ยนเมื่อไหร่ก็ได้ → bug หลุดง่าย

5. **Contract test ต้องโกหก**: test เดิมต้อง assert 500 (ตามความจริง bug)
   → `test_*_returns_500_due_to_production_bug` → ทำให้ test ไม่เป็น
   "documentation of correct behavior" แต่เป็น "documentation of current bug"
   → dev คนใหม่อ่านแล้วสับสน ไม่รู้ว่าจะต้องถือเป็น spec หรือ workaround

6. **เฉพาะกับ project นักขุดทอง**: `/api/signals/{id}` ถูกเรียกจาก
   `SignalDetail` component เมื่อ user คลิกรายการใน history → ถ้า id
   หายเพราะ cascade-delete → user เห็น "Server Error" แทนที่จะเป็น
   "Signal #123 not found" → **เข้าใจผิดว่าระบบพัง** → สูญเสียความเชื่อมั่น
   ในระบบ trading AI

**Test revert**: 4 tests กลับมาชื่อและ assertion ปกติ:
- `test_no_rows_returns_404` (latest-signal)
- `test_not_found_returns_404` (signals/{id})
- `test_no_data_returns_404` (gold-prices)
- `test_no_data_returns_404` (market-state)

---

### 7.5 CORS: `allow_credentials=True` + `allow_origins=["*"]`

Starlette CORSMiddleware เมื่อเปิด `allow_credentials=True` จะ **echo** Origin header
กลับมาแทน `*` (CORS spec: credentials + wildcard เข้ากันไม่ได้ — browser reject)

ไม่ใช่ bug — Starlette ทำถูก. แต่ถ้า frontend deploy หลาย domain ควร explicit
list origins แทน wildcard เพื่อความชัดเจน

---

## 8. Appendix: Design Decisions

| รายการ | สถานะ | เหตุผล |
|--------|-------|--------|
| Vitest แทน Jest | ✅ | เร็วกว่า, share Vite config, ESM native |
| MSW แทน mock props | ✅ | Test ใกล้ production มากสุด — ไม่แตะ component internals |
| conftest ใน `tests/test_frontend/` (ไม่รวม `tests/conftest.py`) | ✅ | Side effect ของ `frontend.api.main` จะรั่วไหลไปทุก test folder |
| Shared `FakeDB` อยู่ใน `tests/fakes.py` | ✅ | Reusable, no side effect, pure Python |
| testcontainers (Tier B) | ❌ ตัดออก | ต้อง Docker; dev loop ช้า → ทำใน sprint ถัดไปถ้าต้องเทสต์ SQL จริง |
| Component tests 3 ตัว (ไม่ครบ 12) | ✅ | Representative patterns ครบ — ขยายด้วยสูตรเดียวกันได้ |
| `*.json` gitignored → temp bypass เพื่อ patch package.json | ✅ | ปิด `.gitignore` ชั่วคราว → patch → เปิดกลับ (ดูหัวข้อ 9.2) |
| `vitest.config.ts` อยู่ที่ `Src/frontend/` ไม่ใช่ `tests/test_frontend/` | ✅ | Node resolve `vitest/config` ต้องอยู่ใกล้ `node_modules` (ดูหัวข้อ 9.3) |
| `node_modules` junction | ✅ | Node resolver หา package ไม่เจอถ้า test อยู่คนละสายกับ `node_modules` (ดูหัวข้อ 9.1) |
| Mock `recharts/ResponsiveContainer` | ✅ | jsdom ไม่มี layout → Recharts บ่น width/height (ดูหัวข้อ 9.5) |

> **กฎ QA**: ถ้า production code มี bug ที่ต้องแก้เพื่อให้ test ผ่าน — **รายงานเป็น finding** ใน section 7 อย่าแก้ไฟล์ production

---

## 9. Troubleshooting & Debug Log

บันทึกปัญหา 8 ตัวที่เจอระหว่าง setup + fix ที่ใช้จริง — อ้างอิงสำหรับ dev คนต่อไป

**Timeline การแก้**:

| # | ปัญหา | หมวด |
|---|------|------|
| 9.1 | `node_modules` resolution ข้าม folder | **Infra** |
| 9.2 | `vitest.config.ts` ต้องชิด `node_modules` | **Infra** |
| 9.3 | Vite `server.fs.allow` + Windows glob | **Infra** |
| 9.4 | Recharts ResponsiveContainer ใน jsdom | **Test env** |
| 9.5 | `act()` warning จาก manual interval callback | **Test code** |
| 9.6 | RTL `findByText` + split text nodes | **Test code** |
| 9.7 | `useNavigate` hook ต้องมี Router context | **Test code** |

### 9.1 Node module resolution — ต้องสร้าง `node_modules` junction

**Symptom**:
```
Error: Failed to resolve import "@testing-library/jest-dom/vitest"
  from "../tests/test_frontend/vitest.setup.ts"
```

**Root cause**: Node/Vite module resolver walks UP parent directories หาถึง `node_modules`
— แต่ test files อยู่ที่ `Src/tests/test_frontend/` และ `node_modules` อยู่ที่
`Src/frontend/node_modules/` (**sibling ไม่ใช่ parent**) — resolver หาไม่เจอ

**Fix** (one-time, ไม่ commit, อยู่ใน `.gitignore` แล้ว):

| OS | Command |
|----|---------|
| Windows | `mklink /J node_modules ..\..\frontend\node_modules` (from `Src/tests/test_frontend/`) |
| macOS/Linux | `ln -s ../../frontend/node_modules node_modules` |

**ทำไมไม่เลือก option อื่น**:
- ❌ `resolve.alias` ทุก package → ต้อง list เป็นร้อยตัว, maintain ยาก
- ❌ ย้าย tests เข้า `frontend/__tests__/` → ทำลายการแยก test/production

### 9.2 `vitest.config.ts` ต้องอยู่ใน `Src/frontend/` ไม่ใช่ tests folder

**Symptom**:
```
Error: Cannot find module 'vitest/config'
Require stack:
- Src/tests/test_frontend/vitest.config.ts
```

**Root cause**: Vitest ใช้ Node CJS resolver โหลด `vitest/config` จาก config file's location.
ถ้า config อยู่ที่ `Src/tests/test_frontend/` → walk up ไม่เจอ `node_modules`

**Fix**: ย้าย config ไปที่ `Src/frontend/vitest.config.ts` (ชิด `node_modules`)
→ `package.json` scripts ใช้ default (`vitest run` — auto-find `./vitest.config.ts`)

ไฟล์ `Src/tests/test_frontend/vitest.config.ts` เดิมถูกเปลี่ยนเป็น **deprecated stub**
(ว่างเปล่า `export {}`) เพื่อป้องกันความสับสน

### 9.3 Windows path + Vite `server.fs.allow`

**Symptom หลัง 9.1 + 9.3**:
```
Failed to load url .../vitest.setup.ts (resolved id: ...). Does the file exist?
```

**Root cause 2 ชั้น**:

1. **`server.fs.allow`**: Vite restrict file read นอก workspace root. เมื่อรันจาก
   `Src/frontend/` แต่ setup file อยู่ `Src/tests/test_frontend/` → Vite block

2. **Glob pattern Windows separator**: `path.resolve()` คืน `C:\...\*.test.ts`
   แต่ micromatch (glob) **ต้องใช้ `/` เท่านั้น**

**Fix** ใน `Src/frontend/vitest.config.ts`:
```ts
const toPosix = (p: string) => p.replace(/\\/g, '/');

server: {
  fs: { allow: [path.resolve(__dirname, '..')] },   // allow Src/ ทั้ง tree
},
test: {
  setupFiles: [path.resolve(TESTS_DIR, 'vitest.setup.ts')],
  include: [toPosix(path.resolve(TESTS_DIR, 'components/**/*.test.{ts,tsx}'))],
},
```

### 9.4 Recharts + jsdom — Mock `ResponsiveContainer`

**Symptom**:
```
The width(-1) and height(-1) of chart should be greater than 0,
please check the style of container...
```

**Root cause**: jsdom ไม่มี layout engine — `ResponsiveContainer` วัดขนาด DOM ไม่ได้ →
Recharts ภายในคำนวณ `width = -1, height = -1` → warn.

**Fix ที่ไม่ work**:
- ❌ Stub `ResizeObserver` (Recharts ไม่ read dimensions จาก callback โดยตรง)
- ❌ Override `offsetWidth/offsetHeight` บน HTMLElement.prototype

**Fix ที่ work** — mock `recharts/ResponsiveContainer` component ใน `vitest.setup.ts`:
```ts
vi.mock('recharts', async (importOriginal) => {
  const actual: any = await importOriginal();
  return {
    ...actual,
    ResponsiveContainer: ({ children, width, height }: any) =>
      React.createElement('div', { style: { width: width ?? 800, height: height ?? 400 } },
        React.cloneElement(children, { width: 800, height: 400 })
      ),
  };
});
```

### 9.5 React `act()` warning ใน polling test

**Symptom**:
```
An update to StatsStack inside a test was not wrapped in act(...).
```

**Root cause**: Test invoke `setInterval` callback เองเพื่อ simulate 30s tick —
แต่ callback trigger React state update ซึ่งไม่ได้อยู่ใน `act()` wrapper

**Fix**:
```ts
import { act } from '@testing-library/react';

const cb = setIntervalSpy.mock.calls.find((c) => c[1] === 30000)![0] as () => void;
await act(async () => { cb(); });
```

### 9.6 Confidence `%` text split ข้าม element

**Symptom**:
```
TestingLibraryElementError: Unable to find an element with the text: 42%.
This could be because the text is broken up by multiple elements.
```

**Root cause**: `StatsStack` render เป็น `<p>{num}<span>%</span></p>` → 2 text nodes
(`"42"` + `"%"`) → `findByText('42%')` match ไม่ได้ (หา single text node)

**Fix** — custom matcher ใช้ `element.textContent`:
```ts
const findConfidencePct = (num: number) =>
  screen.findByText((_, el) =>
    el?.tagName === 'P' && el?.textContent?.trim() === `${num}%`
  );
```

### 9.7 `BacktestSection` ต้อง wrap ใน `<MemoryRouter>`

**Symptom**: Test fail ทั้ง 8 ตัว — component crash ตอน render

**Root cause**: `BacktestSection` → `<OverviewHeader>` → ใช้ `useNavigate()` + `useLocation()`
→ ถ้าไม่มี router context จะ throw

**Fix**:
```tsx
import { MemoryRouter } from 'react-router-dom';

const renderWithRouter = () =>
  render(<MemoryRouter><BacktestSection /></MemoryRouter>);
```

---

## 10. Expected Warnings (ไม่ต้องเคลียร์)

หลัง fix 9.1–9.8 แล้ว stderr จะยังโชว์ log พวกนี้ — **เป็นพฤติกรรมที่ถูกต้อง**:

| Log | เกิดจาก | เหตุผลที่ไม่ silence |
|-----|--------|---------------------|
| `Error fetching detail: TypeError: Failed to fetch` | SignalDetail negative-path test | Component จงใจ `console.error` ใน catch block — test assert ว่า "Signal not found" แสดง |
| `Failed to fetch dashboard data: Error: Portfolio API Error` | StatsStack negative-path (3 ตัว) | Component `console.error` ใน catch — test assert ว่า "OFFLINE" indicator แสดง |
| `Failed to parse trace_json SyntaxError` | SignalDetail malformed trace test | `formatTraceSteps` จงใจ `console.error` ก่อน fallback `[]` — test assert ว่า component ไม่ crash |
| `Warning: --localstorage-file was provided...` | Node internal | Node CLI warning, ไม่เกี่ยว code ของเรา |

> **ถ้าอยาก silence จริงๆ**: `vi.spyOn(console, 'error').mockImplementation(() => {})` ได้
> แต่**เสี่ยงบัง real errors** ที่อาจเกิดในอนาคต — ไม่แนะนำ
