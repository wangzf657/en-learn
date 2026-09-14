import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import mockApiPlugin from './mockApiPlugin.js'

const useMock = process.env.MOCK === '1' || process.env.MOCK === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), useMock && mockApiPlugin()].filter(Boolean),
  server: {
    proxy: useMock
      ? undefined
      : {
          '/api': {
            target: 'http://127.0.0.1:8420',
            changeOrigin: true,
          },
        },
  },
  build: {
    outDir: 'dist',
  },
})
