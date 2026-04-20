/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import path from 'node:path';

/**
 * Vitest config — วางไว้ที่ Src/frontend/ เพื่อให้ Node resolve
 * `vitest/config` จาก `Src/frontend/node_modules/` ได้
 *
 * Test files จริงอยู่ที่ Src/tests/test_frontend/ (แยกจาก production code)
 *
 * รันจาก Src/frontend/:
 *   npm run test              # รันครั้งเดียว
 *   npm run test:watch        # watch mode
 *   npm run test:ui           # UI mode
 *   npm run test:coverage     # coverage report
 */

// glob patterns ต้องใช้ POSIX separator (/) แม้บน Windows
const toPosix = (p: string) => p.replace(/\\/g, '/');

const FRONTEND_ROOT = __dirname;
const TESTS_DIR = path.resolve(__dirname, '../tests/test_frontend');
const SRC_DIR = path.resolve(__dirname, '..'); // Src/

export default defineConfig({
  // Vite's file server must be allowed to access files in both
  //   Src/frontend/ (node_modules + components)
  //   Src/tests/test_frontend/ (setup, mocks, component tests)
  server: {
    fs: {
      allow: [SRC_DIR],
    },
  },
  test: {
    // ไม่ set `root` — ให้ใช้ cwd (Src/frontend/) เป็น default
    // ที่ซึ่ง node_modules อยู่จริง
    globals: true,
    environment: 'jsdom',
    setupFiles: [path.resolve(TESTS_DIR, 'vitest.setup.ts')],
    // ชี้ include ไปที่ test folder นอก frontend (absolute POSIX path — glob ต้องใช้ '/')
    include: [toPosix(path.resolve(TESTS_DIR, 'components/**/*.test.{ts,tsx}'))],
    css: false,
    coverage: {
      provider: 'v8',
      reportsDirectory: path.resolve(TESTS_DIR, 'coverage'),
      include: [toPosix(path.resolve(FRONTEND_ROOT, 'components/**'))],
      exclude: ['**/*.test.tsx', '**/__mocks__/**'],
    },
  },
  resolve: {
    alias: {
      '@frontend': FRONTEND_ROOT,
    },
  },
  esbuild: {
    jsxInject: `import React from 'react'`
  }
});
