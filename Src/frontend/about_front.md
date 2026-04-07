# 📋 Code Review — GoldTrader AI Frontend & API

> **วันที่ Review:** 7 เมษายน 2026  
> **ผู้ Review:** Antigravity AI  
> **Scope:** `Src/frontend/` และ `Src/api/main.py`

---

## 🗂️ โครงสร้างโปรเจกต์ภาพรวม

```
Src/
├── api/
│   └── main.py              ← FastAPI backend (REST API)
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx           ← Root layout + sidebar navigation
        ├── api.ts            ← Axios instance
        └── components/
            ├── HomeTab.tsx       ← หน้า Overview
            ├── AnalysisTab.tsx   ← หน้า Live Analysis (ใหญ่ที่สุด)
            ├── ChartTab.tsx      ← หน้า TradingView chart
            ├── HistoryTab.tsx    ← หน้า Run History
            └── PortfolioTab.tsx  ← หน้า Portfolio
```

**Tech Stack:**
- **Frontend:** React 19 + TypeScript + Vite + TailwindCSS v4
- **Backend:** FastAPI (Python) + Pydantic + Uvicorn
- **HTTP:** Axios (`api.ts` → `http://localhost:8000/api`)

---

## 🔌 `Src/api/main.py` — FastAPI Backend

### ✅ สิ่งที่ดี

| ข้อดี | รายละเอียด |
|---|---|
| **โครงสร้างชัดเจน** | แบ่ง section เป็น Global Init / Models / Endpoints อ่านง่ายมาก |
| **Pydantic Models** | `RunAnalysisRequest`, `SavePortfolioRequest` — typed request body ป้องกัน bad input ได้ดี |
| **Error Handling** | ทุก endpoint มี `try/except` และ log ผ่าน `sys_logger` ก่อน raise `HTTPException` |
| **Query Params** | `/api/history` รับ `limit`, `signal`, `search` — flexible มาก |
| **Service Layer** | ไม่ยัด logic ไว้ใน endpoint โดยตรง แต่ delegate ไปที่ `services[...]` — ดีมากสำหรับ maintainability |

### ⚠️ จุดที่ควรระวัง / แนะนำปรับปรุง

#### 1. `allow_origins=["*"]` — Security Risk 🔴
```python
# บรรทัด 58 — ตอนนี้
allow_origins=["*"],

# ✅ ควรเปลี่ยนเป็น (เวลา deploy จริง)
allow_origins=["http://localhost:5173", "https://your-production-domain.com"],
```
ตอนนี้ใช้ `*` ซึ่ง OK สำหรับ dev แต่ถ้า deploy จริงต้องล็อค origin ไว้ด้วย

#### 2. Win Rate คำนวณผิด Logic เล็กน้อย 🟡
```python
# บรรทัด 98 — นับเฉพาะ BUY เป็น "win"
win_rate = sum(1 for r in runs if r.get("signal") == "BUY") / total_runs

# 🤔 ควรคิดว่า "win" = อะไร? ถ้า SELL แล้วราคาลง = win ด้วย
# ถ้าแค่แสดง BUY ratio ควรเปลี่ยนชื่อเป็น buy_rate จะสื่อความหมายตรงกว่า
```

#### 3. ไม่มี Input Validation ใน Query Params บางตัว 🟡
```python
# บรรทัด 134–138
# limit มี ge=1, le=500 ✅
# แต่ signal ไม่มี Enum validation — ถ้าส่ง signal=INVALID เข้ามาก็ผ่านได้
# ควรเพิ่ม:
signal: Optional[Literal["BUY", "SELL", "HOLD", "ALL"]] = None
```

#### 4. Global State (Orchestrator) จะ fail ทั้ง app ถ้า import error 🟡
```python
# บรรทัดที่ 44–49 — สร้าง object เหล่านี้ตอน module load
orchestrator = GoldTradingOrchestrator()
db = RunDatabase()
services = init_services(...)
```
ถ้า service ใด init ไม่ได้ → app boot ไม่ขึ้น ควรทำ lazy init หรือ health check endpoint แยกไว้

#### 5. ไม่มี `/api/health` endpoint 🟡
ควรเพิ่ม:
```python
@app.get("/api/health")
def health(): return {"status": "ok"}
```
ใช้ตรวจสอบว่า server ขึ้นแล้วจาก frontend ได้ง่ายขึ้น

---

## ⚛️ Frontend Components

### `api.ts` — Axios Instance
```ts
const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' }
});
```
**✅ ดี:** centralize baseURL ไว้ที่เดียว  
**⚠️ แนะนำ:** ควรใช้ environment variable แทน hardcode:
```ts
baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'
```
แล้วสร้างไฟล์ `.env` → `VITE_API_URL=http://localhost:8000/api`

---

### `App.tsx` — Root Layout
**✅ ดี:**
- Layout sidebar + main content แบ่งชัด (`aside` + `main`)
- Fetch `/api/config` ครั้งเดียวตอน mount แล้ว pass เป็น prop ลง — ไม่ fetch ซ้ำ ดีมาก
- Background gradient decoration เท่ (visual polish)
- CSS custom scrollbar ใน `<style>` tag inline — ทำงานได้แต่ควรย้ายไป `index.css`

**⚠️ แนะนำ:**
```tsx
// บรรทัด 84 — มีชื่อ "Aom NOW" hardcode ใน subtitle
{activeTab === 'portfolio' && 'Manage your Aom NOW simulated portfolio state.'}
// ควรเปลี่ยนเป็นชื่อ project จริง หรือ config ไว้ใน constant
```

**⚠️ ไม่มี Error Boundary** — ถ้า component ตัวใดตัวหนึ่งพังจะพัง app ทั้งหมด ควรเพิ่ม:
```tsx
import { ErrorBoundary } from 'react-error-boundary';
<ErrorBoundary fallback={<div>Something went wrong</div>}>
  {activeTab === 'analysis' && <AnalysisTab config={config} />}
</ErrorBoundary>
```

**⚠️ Status indicator ใช้ `bg-emerald-500 animate-pulse` แต่ไม่ได้เช็ค API จริงๆ** — แค่บอกว่า "API Connected" เสมอ ควรเช็คจาก state จริง

---

### `HomeTab.tsx` — Overview Page

**โครงสร้าง:** แบ่ง sub-components ย่อยออกมาดีมาก — `KpiCard`, `SignalCard`, `GoldPriceCard`, `PortfolioCard`, `RecentRunsCard`

**✅ ดี:**
- Auto-refresh ทุก 60 วินาที + Refresh button
- Market open/closed status บอก user ชัดเจน
- `SignalCard` มี confidence bar animation สวย
- `GoldPriceCard` มี fallback state เมื่อ fetch ไม่สำเร็จ

**⚠️ แนะนำ:**

```tsx
// บรรทัด 140 — ชื่อฟังก์ชันชนกับ built-in Web API
const fetch = async () => { ... }
// ✅ ควรเปลี่ยนชื่อ
const fetchHomeData = async () => { ... }
```

```tsx
// บรรทัด 38 — การ set style สี progress bar แบบนี้ไม่ทำงานใน React
<div style={{ width: `${bar}%`, color: c.color.replace('text-', '') }} />
// Tailwind class และ inline style ผสมกันแบบนี้ color จะไม่ถูกใช้เป็น background
// ✅ ควรใช้ className ตรงๆ หรือ style={{ backgroundColor: '#...' }}
```

```tsx
// บรรทัด 154 — useEffect dependency array ว่าง แต่ใช้ fetch ข้างใน
useEffect(() => {
  fetch();
  const t = setInterval(fetch, 60_000);
  return () => clearInterval(t);
}, []); // ← eslint จะ warn ว่า fetch ไม่อยู่ใน deps
// ✅ แก้โดย wrap fetch ด้วย useCallback
```

---

### `AnalysisTab.tsx` — Live Analysis (ไฟล์ใหญ่ที่สุด: 351 บรรทัด)

**✅ ดี:**
- แยก UI เป็น 3 column: Model Settings / Execution / Controls — intuitive มาก
- `useCallback` ใน `runAnalysis` + dependency ใน auto-run `useEffect` ถูกต้อง
- `LlmTrace` sub-component แสดง token usage + prompt/response แบบ collapsible `<details>` — ดีมากสำหรับ debugging
- Vote Tally card แยก BUY/SELL/HOLD พร้อม weighted score — ครบมาก
- Final Decision panel โดดเด่น ขนาด text ใหญ่ อ่านง่าย

**⚠️ แนะนำ:**

```tsx
// บรรทัด 98 — error handling ใช้ alert() ซึ่ง block UI
alert(`Analysis failed: ${e?.response?.data?.detail ?? e.message}`);
// ✅ ควรใช้ toast notification หรือ error state ใน UI แทน
const [error, setError] = useState<string | null>(null);
// แล้ว render <div className="error-banner">{error}</div>
```

```tsx
// บรรทัด 79 — useState<any> ควรหลีกเลี่ยง
const [result, setResult] = useState<any>(null);
// ✅ ควร define interface สำหรับ AnalysisResult
interface AnalysisResult {
  voting_result: VotingResult;
  data: { interval_results: Record<string, IntervalResult>; market_state: any };
}
```

```tsx
// บรรทัด 107 — อ่านยากเล็กน้อย
const sec = (config?.auto_run_intervals[autoInterval] ?? 900) * 1000;
// ✅ ควร comment อธิบาย unit ว่า API return seconds, แปลงเป็น ms
```

**🔴 Bug ที่อาจเกิด:**
```tsx
// บรรทัด 108 — auto-run timer เริ่มทำงานทันทีหลัง toggle autoRun
// แต่จะไม่ run ครั้งแรกทันที ต้องรอครบ interval ก่อน
// ผู้ใช้อาจสับสน ควรเรียก runAnalysis() ทันทีเมื่อ toggle on
useEffect(() => {
  if (!autoRun) return;
  runAnalysis(); // ← เรียกครั้งแรกทันที
  const sec = (config?.auto_run_intervals[autoInterval] ?? 900) * 1000;
  const t = setInterval(runAnalysis, sec);
  return () => clearInterval(t);
}, [autoRun, autoInterval, config, runAnalysis]);
```

---

### `HistoryTab.tsx` — Run History

**✅ ดี:**
- Filter by signal + search + limit — ครบ
- Export CSV function ทำงานได้จริง, เรียบง่าย
- `RunDetail` แสดง field technical ครบ (RSI, MACD, trend, etc.)
- ใช้ `Promise.all` เพื่อ fetch detail + llm-logs พร้อมกัน — efficient

**⚠️ แนะนำ:**

```tsx
// บรรทัด 130–131 — useEffect 2 ตัวที่ fetch ข้อมูลชนกัน
useEffect(() => { fetchHistory(); }, []);
useEffect(() => { fetchHistory(); }, [signal, limit]);
// จะ fetch 2 ครั้งตอน mount (ครั้งแรก + เพราะ signal/limit เปลี่ยนจาก default)
// ✅ รวมเป็น useEffect เดียว
useEffect(() => { fetchHistory(); }, [signal, limit]);
```

```tsx
// บรรทัด 123–127 — exportCsv ไม่ escape ค่าที่มี comma
const rows = runs.map(r => `${r.id},${r.signal},...`);
// ถ้า provider มี comma ใน name จะทำให้ CSV เสีย
// ✅ ควร wrap ด้วย quotes: `"${r.provider}"`
```

```tsx
// บรรทัด 119 — error handling ใช้ alert() เหมือนกัน → ควรเปลี่ยนเป็น UI state
```

**🟡 UX:** Search ต้อง กด Enter ถึงจะ fetch — ถ้า user กด Refresh โดยไม่ได้กด Enter ผล search จะไม่ update ควรเพิ่ม debounced auto-search หรือบอก user ชัดเจนว่าต้องกด Enter

---

### `ChartTab.tsx` — TradingView Chart

**✅ ดี:**
- `TV_MAP` แปลง interval string → TradingView interval value — สะอาด
- Fetch price + providers พร้อมกัน (`Promise.all`) 
- Auto-refresh ทุก 60 วินาที consistent กับ HomeTab

**⚠️ แนะนำ:**

```tsx
// บรรทัด 23 — dangerouslySetInnerHTML
return <div dangerouslySetInnerHTML={{ __html: html }} />;
// ทาง security ok เพราะ src มาจาก tradingview.com ซึ่ง trusted
// แต่ควรใช้ <iframe> โดยตรงแทนจะดีกว่า (ไม่ต้อง dangerouslySetHTML):
return (
  <iframe
    src={`https://s.tradingview.com/widgetembed/?symbol=OANDA%3AXAUUSD&interval=${TV_MAP[interval] ?? '60'}&theme=dark&...`}
    style={{ width: '100%', height: 420, border: 'none' }}
    allowFullScreen
  />
);
```

```tsx
// บรรทัด 86–109 — ชื่อ state variable ชนกับ built-in
const [interval, setInterval] = useState('1h');
// setInterval ชนกับ window.setInterval! อาจทำให้ bug แปลกๆ
// ✅ แก้โดย rename:
const [selectedInterval, setSelectedInterval] = useState('1h');
```

**🔴 Bug สำคัญ: `setInterval` shadow บรรทัด 109**
```tsx
// บรรทัด 109
const t = setInterval(fetchPrice, 60_000);
// ตรงนี้ไม่ได้ใช้ window.setInterval แต่ใช้ setSelectedInterval ที่ destructure มา!
// จะ throw error: TypeError: setInterval is not a function
// ✅ แก้ให้ rename state setter ให้ไม่ชนกับ global
```

---

### `PortfolioTab.tsx` — Portfolio Manager

**✅ ดี:**
- Layout 2 คอลัมน์ View + Edit ชัดเจน
- Form validation ด้วย `type="number"` + `step`
- แสดง Total Equity = cash + current_value คำนวณ live

**⚠️ แนะนำ:**

```tsx
// บรรทัด 44–51 — savePortfolio ใช้ alert()
alert('Portfolio saved successfully!');
alert('Failed to save portfolio.');
// ✅ ควรเปลี่ยนเป็น toast หรือ inline success/error message
```

```tsx
// บรรทัด 6–13 — hardcode initial state
const [data, setData] = useState({
  cash: 1500,  // ← hardcode ฿1500
  gold: 0, cost: 0, cur_val: 0, pnl: 0, trades: 0,
});
// ดีที่มี fetchPortfolio ใน useEffect ซึ่งจะ overwrite ค่าพวกนี้
// แต่ถ้า fetch fail ค่า default 1500 จะยังอยู่ → user อาจสับสน
// ✅ ควร default ทุกค่าเป็น 0 หรือ null
```

```tsx
// PortfolioTab ไม่ได้ส่ง pnl, trades ใน form — user กรอกได้แค่ 4 field
// แต่ API รับ 6 field (cash, gold, cost, cur_val, pnl, trades)
// pnl ส่งค่า 0 เสมอ → ข้อมูลไม่ถูกต้อง ควรเพิ่ม field หรือคำนวณ auto
```

---

## 📊 สรุปคะแนน Code Quality

| ด้าน | คะแนน | หมายเหตุ |
|---|---|---|
| **โครงสร้างโปรเจกต์** | ⭐⭐⭐⭐⭐ | แบ่ง component ชัด, Service Layer ดี |
| **TypeScript Types** | ⭐⭐⭐☆☆ | มี `any` หลายจุด ควร type ให้ชัดขึ้น |
| **Error Handling** | ⭐⭐⭐☆☆ | มี try/catch แต่ใช้ `alert()` — ควรเปลี่ยนเป็น UI state |
| **Security** | ⭐⭐⭐☆☆ | CORS `*` ต้องแก้ตอน deploy |
| **Performance** | ⭐⭐⭐⭐☆ | `useCallback`, `Promise.all` — ดี มี bug `setInterval` shadow |
| **UI/UX** | ⭐⭐⭐⭐⭐ | Dark mode, glassmorphism, responsive สวยมาก |
| **ความสามารถขยาย** | ⭐⭐⭐⭐☆ | Service pattern ดี, แต่ขาด Type ทำให้ refactor ยาก |

---

## 🚀 สิ่งที่ควรทำต่อ (Priority Order)

### 🔴 Critical (ควรแก้ก่อน)
1. **แก้ `setInterval` shadow ใน `ChartTab.tsx`** → rename `interval` state เป็น `selectedInterval`
2. **เพิ่ม `.env` file** สำหรับ `VITE_API_URL` แทน hardcode

### 🟡 Important (ควรทำในเร็วๆ นี้)
3. **เปลี่ยน `alert()` ทุกจุด** → เป็น toast notification (เช่น `react-hot-toast`)
4. **เพิ่ม TypeScript interface** สำหรับ API response (แทน `any`)
5. **แก้ `win_rate` → `buy_rate`** ใน `main.py` เพื่อความถูกต้องของ semantic
6. **CORS origin** ต้องล็อคก่อน deploy production
7. **รวม 2 `useEffect`** ใน `HistoryTab` เป็นตัวเดียว

### 🟢 Nice to Have
8. **Error Boundary** ครอบ components หลัก
9. **`/api/health` endpoint** ใน FastAPI
10. **Auto-run ใน AnalysisTab** ควร run ทันทีตอน toggle on
11. **CSV export** ควร escape ค่าที่มี comma
12. **`fetch` → `fetchHomeData`** ใน `HomeTab.tsx` เพื่อหลีกเลี่ยง shadowing

---

## 💡 Overall Assessment

โปรเจกต์นี้มี **vision ชัดเจนมาก** — เป็น AI Trading Dashboard ที่ครบทั้ง Real-time analysis, Chart, History, Portfolio UI/UX สวยมาก (dark mode + glassmorphism) และ Service architecture ฝั่ง backend ออกแบบมาดี  

**จุดแข็ง:** ความสวยงาม, component แยกชัด, API design สมเหตุสมผล  
**จุดอ่อน:** TypeScript ยังไม่ strict พอ, Error UX (alert), bug `setInterval` shadow ใน ChartTab  

โดยรวมเป็น codebase ที่ **Production-ready ใกล้มาก** เหลือแค่ polish เพิ่มอีกนิดเดียว 🎯
