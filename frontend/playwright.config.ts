import { defineConfig } from '@playwright/test'

// Ch14 e2e:自动拉起后端(E2E_MOCK=1,不走 celery/LLM)+ 前端 dev server,再跑浏览器用例。
// 端口用专用值(后端 8001 / 前端 5174)且 reuseExistingServer=false:
//   - 避开 docker compose 映射到宿主机的前端 5173 / 后端 8000,避免误复用 33h 前的旧容器;
//   - 每次都用本仓库最新代码起服务,CI 与本地行为一致。
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false, // 单条主流程,串行避免共享库数据互相干扰
  use: {
    baseURL: 'http://localhost:5174',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      // 后端:仓库根下用 .venv 的 uvicorn 起服务;E2E_MOCK 同步执行 + 假 pipeline,不依赖 redis/LLM
      command: 'DATABASE_URL=sqlite:///data/e2e.db E2E_MOCK=1 .venv/bin/uvicorn backend.main:app --port 8001',
      cwd: '..',
      url: 'http://localhost:8001/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // 前端 dev server:VITE_API_BASE 直连上面的 8001 后端
      command: 'VITE_API_BASE=http://localhost:8001 npm run dev -- --port 5174 --strictPort',
      url: 'http://localhost:5174',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
