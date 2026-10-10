# EvalFlow Ch14 设计:数据层与交付硬化

## 定位

Ch09–Ch13 把「评测能力」做完整了,但**交付底座**还是 demo 级:SQLite 单文件 + 手写 ALTER TABLE 迁移 + 无 CI + 无 e2e + 容器跑 root。

这一章把「上线才需要的硬骨头」补上,分两条主线:

1. **数据层主线(本批实施)**:SQLite → PostgreSQL 可切换 + alembic 迁移替代 `init_db` 手写迁移。
2. **交付主线(Ch14 后半)**:CI/CD(写好工作流待 push)+ Playwright e2e + HTTPS/健康检查/非 root。

> 本章按「先数据层、后交付」分两批推进:数据层是面试最常问、改动最独立的硬骨头,先做透;交付三条线体量更大且互相独立,随后补。

## 现状(代码位置)

| 问题 | 位置 |
|---|---|
| SQLite 硬编码默认 + 无 PG 驱动 | [config.py:5](../backend/config.py) `database_url = "sqlite:///data/eval.db"` |
| SQLite 专属 PRAGMA / connect_args 无条件执行 | [db.py:22-35](../backend/db.py) `check_same_thread=False` + `PRAGMA journal_mode=WAL` 事件 |
| 手写迁移(ALTER TABLE 补列) | [db.py:46-58](../backend/db.py) `_migrate` |
| `init_db` = `create_all` + `_migrate` | [db.py:41-43](../backend/db.py),被 [main.py:23](../backend/main.py) lifespan 与 [seed.py:7](../backend/seed.py) 调用 |
| 无 postgres 服务 / 无 CI / 无 e2e / 容器 root | [docker-compose.yml](../docker-compose.yml)、无 `.github/`、无 Playwright、Dockerfile 无 USER |

## 数据层主线:决策

### 决策 1:PostgreSQL 驱动用 psycopg3(而非 psycopg2)

SQLAlchemy 2.x 同时支持两者。选 `psycopg[binary]`:
- 是官方新一代驱动,自带二进制轮子(装完即用,不依赖系统 libpq)。
- URL 形如 `postgresql+psycopg://user:pass@host:5432/db`。

**放弃**:psycopg2(老牌但需编译/系统依赖)、asyncpg(异步驱动,本项目全同步,用不上)。

### 决策 2:默认仍是 SQLite,PG 走 `DATABASE_URL` 环境变量

`database_url` 默认值**保持** `sqlite:///data/eval.db` —— 本地开发、测试、`docker compose up`(无 profile)零改动。生产/真机验证设 `DATABASE_URL=postgresql+psycopg://...`。

**理由**:roadmap 明确「可配置,默认仍可 SQLite 本地跑」。测试 54 个全跑 SQLite,不该为 PG 重写。

### 决策 3:`db.py` 按方言分支,不污染 PG

当前两处 SQLite 专属代码必须条件化,否则 PG 直接报错:
- `connect_args={"check_same_thread": False}` —— 只给 SQLite(psycopg 不认识这个参数)。
- `@event.listens_for(engine, "connect")` 里的 `PRAGMA` —— PG 没有 PRAGMA,整段只在 `engine.dialect.name == "sqlite"` 时注册。

**写法**:用 `if engine.dialect.name == "sqlite":` 包住事件注册;connect_args 用三元/条件 dict 构造。

### 决策 4:alembic 接管建表,`init_db()` 变薄封装

`init_db()` 从 `create_all + _migrate` 改为「跑 `alembic upgrade head`」,`_migrate` 删除(它的三个 ALTER TABLE 列——updated_at / retrieval_hits / progress——已在模型里,由初始迁移一并创建)。

调用方(main lifespan、seed.py、conftest)**签名不变**,底层从「手写 SQL」换成「版本化迁移」。

**关键兼容**:现有 `data/eval.db` 是 `create_all` 建的,有表但没有 `alembic_version`。`init_db()` 要识别这种情况,用 `alembic stamp head`「收养」现有库(标记当前 schema 已是最新),否则 `upgrade head` 会因「表已存在」报错。这是把存量库纳入 alembic 的标准动作,单独记坑。

**tradeoff**:业界「正确」做法是 migrate 与 serve 分离(部署时先跑一次迁移,再起服务,避免多实例并发迁移)。本项目 demo 量级,保留「启动时自动 migrate」的便利;Docker 侧把 backend/worker 的启动命令改成 `alembic upgrade head && uvicorn ...`(migrate-then-serve),既正确又不失简单。两个入口都幂等,重复跑无害。

### 决策 5:alembic 目录结构 + env.py 直读 settings

- `alembic.ini`:`script_location = migrations`。
- `migrations/env.py`:把仓库根加进 `sys.path`,然后 `from backend.config import settings`、`from backend.models import Base`;`target_metadata = Base.metadata`;在线/离线两路都把 URL 设为 `settings.database_url`(**不**依赖 ini 里的 `sqlalchemy.url`,这样 `.env` 的 DATABASE_URL 直接生效)。
- `migrations/versions/0001_initial.py`:初始迁移,建 6 张表(datasets / dataset_items / runs / traces / generations / scores),字段与 [models.py](../backend/models.py) 一一对应。

**初始迁移来源**:用 `alembic revision --autogenerate` 对空库生成后再人工核对(补上 default / nullable 等 autogenerate 常漏的细节),既学真实工具流,又保证正确。

### 决策 6:docker-compose 用 profile 挂 postgres,默认不动

新增 `postgres` 服务,放在 `profiles: ["postgres"]` 下:
- `docker compose up`(默认)→ 还是 SQLite,行为不变。
- `docker compose --profile postgres up` → 多起一个 postgres,backend/worker 经 `DATABASE_URL` 连它。

`.env.example` 加 `DATABASE_URL=`(留空 = SQLite)并注释示例。这样「默认 SQLite / 可选 PG」在 compose 层也是显式的。

### 决策 7:模型不改(够 PG 兼容)

现有模型全用 `String/Text/Integer/Float` + Python 端 `default`,无 SQLite 专属类型,PG 下 SQLAlchemy 自动映射(VARCHAR/TEXT/INTEGER/FLOAT),**不需要改模型**。`created_at` 存 ISO 字符串而非 DateTime,PG 下同样能存,不属本章范围(改成 DateTime 会是另一条迁移,避免 scope creep)。

## 数据层主线:验收

- [ ] `alembic upgrade head` 对**全新 SQLite** 建出 6 张表 + `alembic_version`,且 schema 与模型一致。
- [ ] `alembic upgrade head` 对**真 PostgreSQL**(docker)建出同样 schema。
- [ ] 现有 54 个后端测试全绿(默认 SQLite 路径不受影响)。
- [ ] 存量 `data/eval.db` 能被 `init_db()` 平滑收养(stamp),不再报「表已存在」。
- [ ] `docker compose up`(无 profile)仍可起,行为不变。

## 交付主线(Ch14 后半,本节只记决策,实施时再细化)

### CI/CD(GitHub Actions,仓库现无 remote → 写好待 push)

- 一个 workflow,三 job:backend(uv 装依赖 + `pytest`)、frontend(`npm ci` + `vitest run` + `tsc -b`)、image(build 两个镜像)。
- 本地等价命令先跑绿:pytest / vitest / `docker compose build`。
- 用 uv(pyproject + uv.lock 已就绪),不重复造 requirements.txt。

### Playwright e2e(完整主流程)

- 覆盖「建评测集 → 发评测 → 看结果」。
- 后端加 **E2E mock 开关**(如 `E2E_MOCK_LLM=1`):替换 `run_pipeline` 为确定性假实现,不烧钱、不依赖 Ollama/DeepSeek。
- 本地可跑;CI 里是否跑完整栈(起 postgres+backend+frontend)单独评估。

### 交付加固

- **非 root**:两个 Dockerfile 加非 root 用户(`useradd` + `USER`),减少容器逃逸面。
- **健康检查**:backend(`/health`)、frontend(nginx 80)、postgres(`pg_isready`)加 `healthcheck`。
- **HTTPS**:用 nginx 侧 TLS 终结(自签证书本地验证 / 生产挂真实证书),或 Caddy 自动 HTTPS;二选一,实施时定。

## 本章不做(超出 demo 量级)

- 多实例高可用、读写分离、连接池调优。
- 存量 SQLite **数据**迁移到 PG(dev 数据可重建;生产无存量,迁移工具链已具备,真要做用 `alembic` + 数据泵)。
- 云托管 K8s / 灰度 / 监控告警(roadmap 已排除)。
