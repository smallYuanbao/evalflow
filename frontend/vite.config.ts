import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // 开发端口固定在 5173,并且**端口被占时直接报错退出**。
  //
  // 这两项原先只写在命令行里(`vite --port 5173 --strictPort`,见实际启动的进程),
  // 那样只有"记得加参数"的人才受保护 —— 换个终端、换个人拉起就退回默认行为。
  // 写进配置才是默认行为。
  //
  // 为什么 strictPort 不能省:Vite 默认是 false,5173 被占时会**默默顺延**到
  // 5174、5175…… 后果是「我打开 localhost:5173」这句话本身就不可信:
  // 你可能正在看另一个项目的页面,也可能自己的服务被挤走了却毫无察觉。
  server: {
    port: 5173,
    strictPort: true,
  },
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
