import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // ตรวจสอบว่า root คือโฟลเดอร์ปัจจุบันที่มี index.html
  root: './', 
  server: {
    proxy: {
      // เมื่อเรียกใช้ /api ในเครื่องตัวเอง
      '/api': {
        target: 'http://127.0.0.1:8000', // ชี้ไปที่ Uvicorn ของคุณ
        changeOrigin: true,
        // ไม่ต้องตัด /api ออก เพราะ Backend ของคุณมีคำว่า /api อยู่ใน Path แล้ว
      },
    },
  },
  build: {
    outDir: 'dist',
    // บังคับให้ Vite รู้ว่าต้องเริ่มสแกนจาก index.html ตรงไหน
    rollupOptions: {
      input: 'index.html',
    },
  },
})