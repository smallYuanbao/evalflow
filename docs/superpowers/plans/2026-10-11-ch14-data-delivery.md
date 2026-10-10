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

### Ch14 后半(占位,实施时拆 Task)

- [ ] CI/CD:GitHub Actions 工作流(pytest + vitest + build),本地跑等价命令。
- [ ] Playwright e2e:完整主流程(造集→发评测→看结果),后端 E2E mock 开关。
- [ ] 交付加固:非 root 用户 / 健康检查 / HTTPS 终结。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| alembic 对全新 SQLite 建 6 表 + schema 一致 | Task 3/5 |
| alembic 对真 PostgreSQL 建表 | Task 5 真机 |
| 现有 54 测试全绿 | Task 5 |
| 存量库 stamp 收养 | Task 3/5 |
| compose 无 profile 行为不变 / 可选 PG | Task 4 |
