# 🗺️ Implementation Plan — GoldTrader AI Frontend & API

> อ้างอิงจาก Code Review ใน `about_front.md`  
> แบ่งงานออกเป็น 4 เฟส จากสำคัญที่สุด → ดีไว้มีก็ดี

---

## Phase 1 — 🔴 Critical Bug Fixes
> **เป้าหมาย:** แก้ bug ที่ทำให้ระบบพังหรือทำงานผิดพลาดก่อน

| # | Task | ไฟล์ | รายละเอียด |
|---|---|---|---|
| 1.1 | แก้ `setInterval` shadow | `ChartTab.tsx` | rename state จาก `const [interval, setInterval]` → `const [selectedInterval, setSelectedInterval]` เพราะชื่อ `setInterval` ทับ `window.setInterval` ทำให้ timer แตก |
| 1.2 | เพิ่มไฟล์ `.env` | `frontend/.env` | สร้างไฟล์ `.env` ใส่ `VITE_API_URL=http://localhost:8000/api` แล้วแก้ `api.ts` ให้ใช้ `import.meta.env.VITE_API_URL` แทน hardcode |
| 1.3 | แก้ auto-run ใน AnalysisTab | `AnalysisTab.tsx` | เพิ่ม `runAnalysis()` ก่อน `setInterval` เพื่อ run ทันทีตอน toggle auto-run (ตอนนี้ต้องรอครบ interval ก่อนถึงจะเริ่ม) |

---

## Phase 2 — 🟡 Error Handling & UX
> **เป้าหมาย:** เปลี่ยน error/success notification จาก `alert()` เป็น UI ที่ดีกว่า และแก้ปัญหา UX ที่ทำให้ user สับสน

### 2.1 ติดตั้ง Toast Library
- ลง `react-hot-toast`:
  ```bash
  npm install react-hot-toast
  ```
- เพิ่ม `<Toaster />` ใน `App.tsx`

### 2.2 เปลี่ยน `alert()` ทุกจุด → Toast

| ไฟล์ | จุดที่ต้องแก้ |
|---|---|
| `AnalysisTab.tsx` | `alert('Analysis failed: ...')` บรรทัด 98 |
| `HistoryTab.tsx` | `alert('Not found: ...')` บรรทัด 119 |
| `PortfolioTab.tsx` | `alert('Portfolio saved successfully!')` และ `alert('Failed to save portfolio.')` บรรทัด 45–48 |

แทนที่ทุกตัวด้วย:
```ts
import toast from 'react-hot-toast';
toast.success('บันทึกสำเร็จ!');
toast.error(`เกิดข้อผิดพลาด: ${message}`);
```

### 2.3 แก้ UX Search ใน HistoryTab
- ปัญหา: Search ต้องกด Enter ถึงจะทำงาน แต่ถ้ากด Refresh โดยไม่กด Enter → ผลลัพธ์ไม่ update
- วิธีแก้: เพิ่ม Button "🔍 Search" ข้างช่อง input ให้ชัดเจน **หรือ** เพิ่ม debounced auto-search เมื่อพิมพ์หยุด

### 2.4 แก้ Progress Bar สี ใน HomeTab
- ไฟล์: `HomeTab.tsx` บรรทัด 38
- ปัญหา: ใช้ `color` แทน `backgroundColor` ทำให้แถบสีไม่แสดง
- แก้เป็น:
  ```tsx
  // เดิม
  style={{ width: `${bar}%`, color: c.color.replace('text-', '') }}
  // แก้เป็น
  className={`h-1.5 rounded-full bg-current transition-all ${c.color}`}
  style={{ width: `${bar}%` }}
  ```

---

## Phase 3 — 🔵 Code Quality & TypeScript
> **เป้าหมาย:** ทำให้โค้ดแข็งแกร่งขึ้น ลด `any` และรวม logic ที่ซ้ำซ้อน

### 3.1 Define TypeScript Interfaces สำหรับ API Response

สร้างไฟล์ใหม่ `src/types.ts`:
```ts
export interface IntervalResult {
  signal: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  weight?: number;
  trace?: TraceStep[];
}

export interface VotingBreakdown {
  count: number;
  avg_conf: number;
  total_weight: number;
  weighted_score: number;
  intervals: string[];
}

export interface VotingResult {
  final_signal: 'BUY' | 'SELL' | 'HOLD';
  weighted_confidence: number;
  voting_breakdown: Record<'BUY' | 'SELL' | 'HOLD', VotingBreakdown>;
  interval_details?: IntervalDetail[];
}

export interface AnalysisResult {
  voting_result: VotingResult;
  data: {
    interval_results: Record<string, IntervalResult>;
    market_state: object;
  };
}
```

แล้วนำ interface ไปแทน `any` ใน:
- `AnalysisTab.tsx` — `useState<any>` → `useState<AnalysisResult | null>`
- `HomeTab.tsx` — `useState<any>` → type ที่ถูกต้อง

### 3.2 รวม useEffect ซ้ำใน HistoryTab
- ไฟล์: `HistoryTab.tsx` บรรทัด 130–131
- แก้จาก:
  ```ts
  useEffect(() => { fetchHistory(); }, []);
  useEffect(() => { fetchHistory(); }, [signal, limit]);
  ```
- เป็น:
  ```ts
  useEffect(() => { fetchHistory(); }, [signal, limit]);
  ```

### 3.3 Rename ฟังก์ชันที่ทับ built-in
- `HomeTab.tsx`: `const fetch` → `const fetchHomeData`
- `ChartTab.tsx`: `const [interval, setInterval]` → ทำแล้วใน Phase 1

### 3.4 แก้ไขชื่อ hardcode ใน App.tsx
- บรรทัด 84: เปลี่ยน `'Aom NOW'` เป็นชื่อโปรเจกต์จริง หรือย้ายไปเป็น constant

### 3.5 Fix CSV Export ใน HistoryTab
- ไฟล์: `HistoryTab.tsx` บรรทัด 123–127
- เพิ่ม double-quotes รอบทุก field เพื่อ escape ค่าที่มี comma:
  ```ts
  const rows = runs.map(r =>
    `${r.id},"${r.signal}","${(r.confidence*100).toFixed(0)}%","${r.provider}","${r.run_at}","${r.gold_price ?? ''}"`
  );
  ```

### 3.6 ย้าย CSS scrollbar ออกจาก `<style>` inline ใน App.tsx
- ย้ายไปไว้ใน `src/index.css` แทน

---

## Phase 4 — 🟢 Backend & Nice-to-Have
> **เป้าหมาย:** เสริมความแข็งแกร่งฝั่ง Backend และเพิ่ม feature เสริมที่ดีถ้ามีเวลา

### 4.1 เพิ่ม `/api/health` endpoint ใน FastAPI
- ไฟล์: `api/main.py`
- เพิ่ม:
  ```python
  @app.get("/api/health")
  def health():
      return {"status": "ok", "version": "3.4"}
  ```
- แล้วแก้ `App.tsx` ให้เช็ค health จริงๆ แทนที่จะแสดง "API Connected" เสมอ

### 4.2 แก้ CORS สำหรับ Production
- ไฟล์: `api/main.py` บรรทัด 58
- ตอนนี้: `allow_origins=["*"]`
- เปลี่ยนเป็น:
  ```python
  import os
  ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
  allow_origins=ALLOWED_ORIGINS
  ```

### 4.3 แก้ชื่อ `win_rate` → `buy_rate` ใน Backend
- ไฟล์: `api/main.py` บรรทัด 98–99 และ 117
- เปลี่ยนชื่อเพื่อให้ semantic ตรงกับความจริง:
  ```python
  buy_rate = sum(1 for r in runs if r.get("signal") == "BUY") / total_runs if total_runs else 0
  ```

### 4.4 เพิ่ม Error Boundary ใน App.tsx
- ติดตั้ง: `npm install react-error-boundary`
- ครอบ main content ด้วย `ErrorBoundary` เผื่อ component พัง:
  ```tsx
  import { ErrorBoundary } from 'react-error-boundary';
  
  <ErrorBoundary fallback={<div className="text-red-400 p-8">⚠️ เกิดข้อผิดพลาด กรุณารีเฟรชหน้า</div>}>
    {activeTab === 'analysis' && <AnalysisTab config={config} />}
    {/* ... */}
  </ErrorBoundary>
  ```

### 4.5 แก้ผ่าน PortfolioTab ให้ส่ง pnl/trades ครบ
- ปัญหา: form ส่งแค่ 4 field แต่ API รับ 6 field → `pnl` เป็น 0 เสมอ
- เพิ่ม field `pnl` และ `trades` ลงใน form ด้วย

### 4.6 เพิ่ม Signal Validation ใน FastAPI Query Params
- ไฟล์: `api/main.py` บรรทัด 136
- เพิ่ม `Literal` type ให้ `signal` parameter:
  ```python
  from typing import Literal
  signal: Optional[Literal["BUY", "SELL", "HOLD", "ALL"]] = Query(None)
  ```

---

## 📋 สรุป Checklist ทั้งหมด

### Phase 1 — Critical 🔴
- [ ] 1.1 แก้ `setInterval` shadow ใน `ChartTab.tsx`
- [ ] 1.2 สร้าง `.env` + แก้ `api.ts` ให้ใช้ env variable
- [ ] 1.3 แก้ auto-run ให้ run ทันทีตอน toggle on ใน `AnalysisTab.tsx`

### Phase 2 — Error Handling 🟡
- [ ] 2.1 ติดตั้งและตั้งค่า `react-hot-toast`
- [ ] 2.2 เปลี่ยน `alert()` → toast ใน AnalysisTab, HistoryTab, PortfolioTab
- [ ] 2.3 แก้ UX Search ใน `HistoryTab.tsx`
- [ ] 2.4 แก้ Progress bar สี ใน `HomeTab.tsx`

### Phase 3 — Code Quality 🔵
- [ ] 3.1 สร้าง `src/types.ts` และ define TypeScript interfaces
- [ ] 3.2 รวม `useEffect` ซ้ำใน `HistoryTab.tsx`
- [ ] 3.3 Rename `fetch` → `fetchHomeData` ใน `HomeTab.tsx`
- [ ] 3.4 แก้ชื่อ hardcode `'Aom NOW'` ใน `App.tsx`
- [ ] 3.5 Fix CSV export ให้ escape comma
- [ ] 3.6 ย้าย scrollbar CSS ไป `index.css`

### Phase 4 — Backend & Nice-to-Have 🟢
- [ ] 4.1 เพิ่ม `/api/health` endpoint
- [ ] 4.2 แก้ CORS ให้ configurable ผ่าน env
- [ ] 4.3 เปลี่ยนชื่อ `win_rate` → `buy_rate`
- [ ] 4.4 เพิ่ม `ErrorBoundary` ใน `App.tsx`
- [ ] 4.5 เพิ่ม field `pnl`/`trades` ใน `PortfolioTab` form
- [ ] 4.6 เพิ่ม Signal validation ใน FastAPI query params
