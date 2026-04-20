/**
 * Global Vitest setup — โหลดทุกครั้งก่อนแต่ละ test file
 *
 *  1. @testing-library/jest-dom — เพิ่ม custom matchers (toBeInTheDocument, ฯลฯ)
 *  2. MSW server — intercept fetch() จาก component
 *  3. import.meta.env.VITE_API_URL — mock ให้ handlers catch ได้
 */

import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { server } from './__mocks__/server';
import { cleanup } from '@testing-library/react';

// ── Mock recharts ResponsiveContainer — jsdom ไม่มี layout ────────────────
// Recharts's ResponsiveContainer จะ warn "width(-1) and height(-1)"
// เพราะวัดขนาดจาก DOM ไม่ได้ → mock ให้คืน children ที่ h/w ตายตัว
vi.mock('recharts', async (importOriginal) => {
  const actual: any = await importOriginal();
  return {
    ...actual,
    ResponsiveContainer: ({ children, width, height }: any) =>
      React.createElement(
        'div',
        {
          style: {
            width: typeof width === 'number' ? width : 800,
            height: typeof height === 'number' ? height : 400,
          },
        },
        React.cloneElement(children, { width: 800, height: 400 })
      ),
  };
});

// Mock VITE_API_URL ที่ component ใช้ — MSW จะดัก '*/api/...'
// ไม่ว่า base URL จะเป็นอะไร (localhost:8000 หรือ env)
// @ts-ignore
import.meta.env.VITE_API_URL = 'http://localhost:8000';

// ── MSW lifecycle ─────────────────────────────────────────────────
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

// ── Fake timers utility ── (test ที่ต้องการ opt-in) ────────────────
// ใน test: vi.useFakeTimers(); vi.advanceTimersByTime(30_000);
