import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/**
 * MSW Node server instance — ใช้ใน vitest.setup.ts
 * Test จะ override handlers ผ่าน `server.use(...)` ใน beforeEach
 */
export const server = setupServer(...handlers);
