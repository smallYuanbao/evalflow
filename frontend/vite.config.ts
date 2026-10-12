import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './vitest.setup.ts',
    // 单测只扫 src/:e2e/ 是 Playwright 用例,不被 vitest 拾取(否则 test() 双注册报错)
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // antd 组件渲染较重,并行跑多个文件时默认 5s 会偶发超时(单独跑都能过)
    testTimeout: 15_000,
  },
})
