import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 开发代理：/api 请求转发到后端 8000 端口，解决跨域 + 统一路径
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 代码分割：将大型依赖拆成独立 chunk
        manualChunks: {
          'element-plus': ['element-plus'],
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
        },
      },
    },
    // 提升 chunk 大小警告阈值
    chunkSizeWarningLimit: 800,
  },
})
