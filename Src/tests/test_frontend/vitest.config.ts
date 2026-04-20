/**
 * ⚠️ DEPRECATED — ใช้ Src/frontend/vitest.config.ts แทน
 *
 * เหตุผล: Vitest resolve `vitest/config` จาก `node_modules` ของ parent ของ config file
 *         ถ้า config อยู่ที่ Src/tests/test_frontend/ จะหา node_modules ไม่เจอ
 *         (เพราะ npm install ไป Src/frontend/node_modules/)
 *
 * config จริงย้ายไปที่ Src/frontend/vitest.config.ts เรียบร้อยแล้ว
 * package.json ก็อัปเดตให้ใช้ default path (ไม่ต้องส่ง --config)
 *
 * ลบไฟล์นี้ทิ้งได้เลย — เก็บไว้แค่เป็น marker
 */
export { };
