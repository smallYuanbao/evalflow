# EvalFlow Ch14 实施计划:数据层与交付硬化

## 背景(对应 spec)

两条主线:**数据层(本批)** 把 SQLite→PostgreSQL + alembic 落地;**交付(后半)** 补 CI/e2e/HTTPS·非 root。本计划先列数据层主线 Task,交付三线放「Ch14 后半」占位,实施时再拆 Task。

## 任务清单

### 数据层主线:PostgreSQL + alembic(本批)

#### Task 1:依赖与配置

- [x] `pyproject.toml` + `backend/Dockerfile` 加 `alembic>=1.14`、`psycopg[binary]>=3.2`。
- [x] `.env.example` 加 `DATABASE_URL=`(留空=SQLite)+ 注释示例;`config.py` 的 `database_url` 默认值不变。

#### Task 2:db.py 按方言分支

- [x] `connect_args` 只在 SQLite 时传 `check_same_thread=False`(PG 不认该参数)。
- [x] `PRAGMA` 事件只在 `engine.dialect.name == "sqlite"` 时注册。
- [x] 删掉手写 `_migrate`(三个 ALTER TABLE 列已进模型,由迁移统一建)。

#### Task 3:alembic 接管建表

- [x] 新增 `alembic.ini` + `migrations/env.py`(直读 `settings.database_url`)+ `migrations/script.py.mako`。
- [x] `migrations/versions/0001_initial.py`:建 6 张表,字段与模型一致(autogenerate 后人工核对 default/nullable)。
- [x] `init_db()` 改为跑 `alembic upgrade head`;存量库(有表无 `alembic_version`)先 `stamp head` 收养。

#### Task 4:docker-compose 可选 postgres

- [x] `postgres` 服务(profile `postgres`,含 `pg_isready` 健康检查 + 命名卷)。
- [x] backend/worker 透传 `DATABASE_URL`;backend 启动命令改 `alembic upgrade head && uvicorn ...`(migrate-then-serve)。

#### Task 5:测试与真机验证

- [x] 测试:全新 SQLite 跑 `init_db()` 建出 6 表 + `alembic_version`;存量库可 stamp 收养。
- [x] 现有 54 个后端测试全绿(SQLite 路径不变)。
- [x] 真机:`docker compose --profile postgres up -d postgres` 后 `alembic upgrade head` 对 PG 建表成功;backend 连 PG 能起。

### 交付三线:CI / e2e / 加固(后半)

#### Task 6:CI/CD 工作流(写好待 push)

- [x] `.github/workflows/ci.yml`:backend(`uv sync` + `pytest`)/ frontend(`npm ci` + `vitest` + `build` + `lint`)/ build(`docker compose build`)/ e2e(`playwright install --with-deps chromium` + `playwright test`)四 job。
- [x] 本地等价命令全绿:pytest 56 / vitest 12 / `npm run build` / `npx playwright test` / `docker compose build`。

#### Task 7:Playwright e2e 完整主流程

- [x] `backend/e2e_mock.py`:`mock_run_pipeline`(固定 output/retrieved/hits)+ `mock_judge`(`score=0.8`);`run_service.py` 在 `E2E_MOCK` 下替换 5 个 judge;`main.py` 的 `create_run` 同步执行(不走 celery)。
- [x] `frontend/playwright.config.ts` + `frontend/e2e/main-flow.spec.ts`:造集 → 加样本 → 发评测 → 看结果四步断言。
- [x] 端口隔离:后端 8001 / 前端 5174 + `reuseExistingServer:false`,避开 docker 映射的 8000/5173;`main.py` CORS 加 5174。

> **2026-10-16 补充**:这组 e2e 端口(`5174` / `8001`)**仍然有效,没动过**。
> 但"避开 docker 映射的 8000/5173"这句已不准确 —— `8000` 现在是 docker 里的 Chroma,
> `5173` 是本仓库的 dev 前端(不再是 docker 映射)。当前端口表见 `scripts/devguard.mjs`。
- [x] 修 e2e 暴露的两处真实 bug:空库隐藏「新建评测集」按钮(`DatasetsView` 空态提前 return)、antd Select placeholder 非 input 属性导致 `getByPlaceholder` 匹配不到。

#### Task 8:交付加固(非 root / 健康检查 / HTTPS)

- [x] `backend/Dockerfile`:`useradd --uid 1000 evalflow` + `USER evalflow`;CMD 改 `alembic upgrade head && uvicorn ...`。
- [x] `frontend/Dockerfile` + `nginx-gen-cert.sh` + `nginx.conf`:openssl 自签证书(证书缺失时)+ 同一 server 块 `listen 80` + `listen 443 ssl`。
- [x] `docker-compose.yml`:backend/frontend `healthcheck`、frontend `443:443`、`certs_data` 卷。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| alembic 对全新 SQLite 建 6 表 + schema 一致 | Task 3/5 |
| alembic 对真 PostgreSQL 建表 | Task 5 真机 |
| 现有 54 测试全绿 | Task 5 |
| 存量库 stamp 收养 | Task 3/5 |
| compose 无 profile 行为不变 / 可选 PG | Task 4 |
| CI 工作流与本地等价命令一致 | Task 6 |
| Playwright 主流程四步通过 | Task 7 |
| 非 root / 健康检查 / HTTPS 就绪 | Task 8 |
