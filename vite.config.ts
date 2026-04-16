import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      // บอก Vite ว่าไม่ต้องไปสแกนหรือเฝ้าดูการเปลี่ยนแปลงในโฟลเดอร์ venv
      ignored: ['**/venv/**'] 
    }
  },
  optimizeDeps: {
    // ป้องกันไม่ให้ Vite เข้าไปหา Dependencies ในฝั่ง Python
    entries: ['index.html', 'Src/**/*.{ts,tsx}']
  }
})