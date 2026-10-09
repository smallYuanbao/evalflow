# EvalFlow Ch08 设计:部署容器化(Docker)

## 目标

Ch07 之后平台功能与体验都到位。Ch08 把「本地两条命令跑起来」升级为「Docker 一键起」,补齐工程化最后一块,也顺带讲清面试常问的「前后端如何部署」。

用 Docker 打包 FastAPI + 前端 + ChromaDB,`docker compose up` 一键启动。

验收标准:

1. `docker compose up` 一键起后端 + 前端 + ChromaDB 三个服务。
2. 前端由 nginx 托管构建产物,并反代 `/api` 到后端(或等价方案)。
3. 环境变量通过 `.env` 注入,不硬编码(尤其 `CHAT_API_KEY` 不进镜像)。
4. ChromaDB 数据 + SQLite 数据持久化到命名卷,容器重建不丢。

## 架构

```
docker-compose.yml
  ├─ chroma    官方 chromadb/chroma 镜像(HTTP 服务,端口 8000)
  │    └─ 数据挂命名卷 chroma_data
  ├─ backend   FastAPI 镜像(uvicorn,端口 8001 或容器内 8000)
  │    └─ SQLite 挂卷;embedding 走宿主机 Ollama(host.docker.internal:11434)
  └─ frontend  nginx 托管 vite build 产物,反代 /api → backend
```

**Ollama 不容器化**:本机已装且 `bge-m3`(1.2GB)已下载,重复容器化浪费;backend 容器通过 `host.docker.internal:11434` 访问宿主机 Ollama。

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| ChromaDB | Docker 官方 `chroma` 镜像(独立服务) | PersistentClient 内嵌 backend 容器:数据要挂卷且被 backend 独占;独立 chroma 服务是标准架构,也贴近 baby-ai 的 HttpClient 用法 |
| retriever 切换方式 | 按环境:设 `CHROMA_HOST` 走 HttpClient,否则 PersistentClient | 一刀切 HttpClient:破坏本地 dev 和现有测试;按环境切换两全 |
| 前端托管 | nginx + 反代 `/api` | FastAPI 托管静态:前后端耦合;nginx 是标准生产做法 |
| embedding | 宿主机 Ollama,backend 经 host.docker.internal 访问 | 容器化 Ollama:模型 1.2GB 已本地装,重复容器化浪费 |
| 数据持久化 | chroma 数据 + SQLite 各挂命名卷 | 不挂卷:容器重建数据全丢 |
| 密钥 | `.env` 注入,`CHAT_API_KEY` 不进镜像 | 写进 Dockerfile:密钥泄漏进镜像层,是安全大忌 |

## 需要改动(实现时细化)

1. `backend/retriever.py`:改为**按环境切换**——设 `CHROMA_HOST` 走独立 chroma 服务(HttpClient,容器模式),否则走本地文件(PersistentClient,本地 dev / 测试不变)。比「一刀切改成 HttpClient」更稳:本地开发与现有 `test_retriever.py`(monkeypatch `_client`)零破坏。
2. `backend/config.py`:`chroma_host`(空 = 本地 PersistentClient)/ `chroma_port` 环境变量。
3. `backend/Dockerfile`(uvicorn)+ `frontend/Dockerfile`(build 阶段 + nginx 阶段)。
4. `docker-compose.yml` + `.env.example` 补 docker 相关变量。
5. nginx 配置:`/api` 反代到 backend,`/` 服务静态。

## 本章不做

- K8s / 云平台部署。
- CI/CD 流水线。
- HTTPS / 域名 / 生产级反向代理加固。
- Ollama 容器化(GPU/模型管理复杂度,超出 demo 范围)。
