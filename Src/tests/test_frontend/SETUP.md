# SETUP — Frontend Component Testing

`Src/frontend/package.json` ถูก patch เรียบร้อยแล้ว + `vitest.config.ts` อยู่ที่
`Src/frontend/vitest.config.ts` (อยู่ชิด `node_modules` เพื่อ resolve `vitest/config` ได้) —
เหลือแค่ติดตั้ง deps + รัน test

> ไฟล์ `Src/tests/test_frontend/vitest.config.ts` ตัวเก่าเป็น deprecated stub — ลบได้ถ้าต้องการ
> Test files ทั้งหมดยังอยู่ที่ `Src/tests/test_frontend/components/` เหมือนเดิม

---

## 1. ติดตั้ง dependencies

```bash
cd Src/frontend
npm install
```

สิ่งที่ถูกเพิ่มใน `devDependencies`:

| Package | ใช้ทำอะไร |
|---|---|
| `vitest`, `@vitest/ui`, `@vitest/coverage-v8` | Test runner + UI + coverage |
| `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event` | Component test + user event simulation |
| `msw` | Mock Service Worker — intercept fetch() |
| `jsdom` | Browser-like DOM สำหรับ Node |

**Security**: ทุกตัวเป็น devDependencies → ไม่ bundle ใน production build

---

## 2. สร้าง `node_modules` junction (ครั้งเดียว)

Test files อยู่ที่ `Src/tests/test_frontend/` แต่ `node_modules` อยู่ที่ `Src/frontend/node_modules/`
— Vite/Node module resolver หาไม่เจอเพราะเป็น sibling ไม่ใช่ parent

Fix: สร้าง directory junction (Windows, ไม่ต้อง admin):

```cmd
cd Src\tests\test_frontend
mklink /J node_modules ..\..\frontend\node_modules
```

**Expected output**:
```
Junction created for node_modules <<===>> ..\..\frontend\node_modules
```

> Linux/macOS ใช้ `ln -s ../../frontend/node_modules node_modules` แทน
>
> Junction ไม่ถูก track (node_modules/ อยู่ใน .gitignore แล้ว)

---

## 3. รัน test

```bash
# รันครั้งเดียว
npm run test

# Watch mode
npm run test:watch

# UI mode (browser-based inspector)
npm run test:ui

# Coverage report
npm run test:coverage
```

---

## 3. Troubleshooting

### 3.1 Peer dep warning (React 19 + RTL 16)
ถ้าเจอ `ERESOLVE unable to resolve peer dependency`:
```bash
npm install --legacy-peer-deps
```

### 3.2 MSW warning "unhandled request"
Component ไปดึง endpoint ที่ `handlers.ts` ไม่ครอบ — เติมใน
`tests/test_frontend/__mocks__/handlers.ts`

### 3.3 `Cannot use JSX runtime`
ตรวจใน `Src/frontend/tsconfig.json` ให้มี:
```json
"compilerOptions": { "jsx": "react-jsx" }
```

### 3.4 Tailwind CSS error
CSS ถูกปิด (`css: false` ใน `vitest.config.ts`) — component render ได้
แต่ class เป็น raw string (ไม่มีผลต่อ assertion)

### 3.5 `Module not found: @vitest/coverage-v8`
Coverage เป็น optional peer — ติดตั้งเพิ่มถ้าจำเป็น:
```bash
npm install --save-dev @vitest/coverage-v8
```

---

## 4. ถ้าต้อง revert package.json

ลบ keys เหล่านี้ใน `scripts`:
- `test`, `test:watch`, `test:ui`, `test:coverage`

ลบ keys เหล่านี้ใน `devDependencies`:
- `@testing-library/jest-dom`, `@testing-library/react`, `@testing-library/user-event`
- `@vitest/coverage-v8`, `@vitest/ui`
- `jsdom`, `msw`, `vitest`

แล้ว `npm install` ใหม่
