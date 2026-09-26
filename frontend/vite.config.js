import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 默认只监听 localhost（手机等其它设备连不上）。
    // host: true = 监听 0.0.0.0，局域网内任何设备都能访问 http://<本机IP>:5173
    host: true,
    proxy: {
      // 页面发 /api/v1 相对路径 → Vite 转手转发给后端 8000（开发期跨域方案）
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
