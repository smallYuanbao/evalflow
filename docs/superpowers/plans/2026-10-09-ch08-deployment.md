# EvalFlow Ch08 实施计划:部署容器化(Docker)

## 背景(对应 spec)

功能与体验齐了,最后把「本地两条命令跑起来」升级为「Docker 一键起」。打包 FastAPI + 前端 + ChromaDB,Ollama 留在宿主机。

**关键现状(决定实现方式)**:
- `retriever.py` 用 `chromadb.PersistentClient(path="data/chroma")`,`tests/test_retriever.py` 靠 `monkeypatch.setattr(retriever, "_client", ...)` mock。所以 retriever 改造**必须保留模块级 `_client` 变量**。
- 前端 `client.ts` BASE = `import.meta.env.VITE_API_BASE ?? 'http://localhost:8002'`,可配置。
- `config.py` 已用 pydantic-settings,加环境变量零成本。

**核心决策(比 spec 更细化)**:retriever 不「一刀切改成 HttpClient」,而是**按环境切换** —— 设了 `CHROMA_HOST` 走独立 chroma 服务(HttpClient,容器模式),否则走本地文件(PersistentClient,本地 dev / 测试不变)。这样本地开发和现有测试零破坏,又满足容器化的标准架构。

## 任务清单

### Task 1:retriever + config 支持 chroma 服务(按环境切换)

- [x] `backend/config.py`:加 `chroma_host: str = ""`(空 = 本地 PersistentClient)、`chroma_port: int = 8000`。
- [x] `backend/retriever.py`:模块级 `_client` 改为 `_make_client()` 按环境返回;`_coll()` / `retrieve()` / `ingest()` 逻辑不变(PersistentClient 与 HttpClient 共用 `get_or_create_collection` / `query` / `upsert` API)。

```python
def _make_client():
    if settings.chroma_host:
        return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return chromadb.PersistentClient(path="data/chroma")

_client = _make_client()  # 测试仍可 monkeypatch 这个变量
```

- [x] 验证:后端测试全绿(`test_retriever.py` 不依赖真实 chroma,靠 monkeypatch)。

### Task 2:backend Dockerfile

- [x] `backend/Dockerfile`:python:3.12-slim;先 `pip install` 依赖(pyproject 里的 dependencies,注释说明保持同步),再 COPY backend;uvicorn 启动。

### Task 3:frontend Dockerfile + nginx + .env.production

- [x] `frontend/.env.production`:`VITE_API_BASE=/api`(prod 走同源 nginx 反代,dev 仍直连 localhost:8002)。
- [x] `frontend/nginx.conf`:静态托管 + SPA 回退(`try_files ... /index.html`)+ `/api/` 反代到 `backend:8000/`(去掉 /api 前缀)。
- [x] `frontend/Dockerfile`:node:20 构建 → nginx 托管 dist。

### Task 4:docker-compose + .env.example + .dockerignore

- [x] `docker-compose.yml`:chroma(官方镜像)+ backend + frontend 三服务;chroma/SQLite 各挂命名卷;`CHAT_*` 从宿主 `.env` 注入(密钥不进镜像);`EMBED_BASE_URL=http://host.docker.internal:11434`(Ollama 在宿主机);`CHROMA_HOST=chroma`。
- [x] `.env.example`:补 `EMBED_BASE_URL` / `CHROMA_HOST` / `CHROMA_PORT`。
- [x] `.dockerignore`:排除 node_modules / .venv / data / .env / .git。

### Task 5:验证

- [x] 后端 pytest 全绿(retriever 改造无回归)。
- [x] 前端 build 全绿(.env.production 让 BASE=/api)。
- [x] `docker compose config` 语法校验(若本机有 docker)。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| docker compose up 一键起三服务 | Task 4 |
| 前端 nginx 托管 + 反代 /api | Task 3 |
| 环境变量注入、密钥不进镜像 | Task 4(docker-compose `${CHAT_API_KEY}` + .dockerignore 排除 .env) |
| ChromaDB/SQLite 持久化到命名卷 | Task 4 |
| 不破坏本地 dev / 测试 | Task 1(按环境切换) + Task 5 |

## 本章不做

- K8s / 云部署、CI/CD、HTTPS / 生产级加固、Ollama 容器化(spec 已明确)。
