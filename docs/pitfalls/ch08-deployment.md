# Ch08 踩坑:Docker 容器化部署

> 这一章把 FastAPI + 前端 + ChromaDB 打包成 Docker 三服务。坑在「重构别破坏测试」和「容器网络/密钥」。

## 坑 1:重构要保留测试依赖的「抓手」

**现象**:把 retriever 从本地 PersistentClient 改成「按环境切换」时,`tests/test_retriever.py` 全挂。

**根因**:测试靠 `monkeypatch.setattr(retriever, "_client", ...)` mock 掉真实 chroma 客户端。如果重构把模块级 `_client` 变量改名/去掉,测试的 patch 目标就没了。

**修法**:retriever 改造**必须保留模块级 `_client` 变量**:

```python
_client = None
def _get_client():
    global _client
    if _client is None:
        _client = (chromadb.HttpClient(host=..., port=...) if settings.chroma_host
                   else chromadb.PersistentClient(path="data/chroma"))
    return _client
```

**原理**:测试靠 monkeypatch「按名字替换模块属性」来隔离外部依赖。**重构时如果改了被 mock 的符号名,测试会在你看不见的地方悄悄失效**。改接口/符号前先 grep 一遍谁在 patch 它。

## 坑 2:容器访问宿主机服务用 host.docker.internal

**现象**:backend 跑在容器里,连宿主机 Ollama(`localhost:11434`)连不上。

**根因**:容器里的 `localhost` 是容器自己,**不是宿主机**。Ollama 留在宿主机,容器要经特殊主机名访问。

**修法**:`EMBED_BASE_URL=http://host.docker.internal:11434`;Linux 若解析不到,给 backend 加 `extra_hosts: ["host.docker.internal:host-gateway"]`。

**原理**:容器网络的经典坑——`localhost` 在容器内外是两个世界。宿主机服务对容器是 `host.docker.internal`(Mac/Windows 内置,Linux 要配 host-gateway)。

## 坑 3:密钥不进镜像

**现象**:`.env` 里有真实 `CHAT_API_KEY`,如果被 `COPY` 进镜像或 commit 进 git,就泄露了。

**根因**:镜像会分层缓存、可能被推送到 registry;git 历史可被追溯。密钥一旦进去,删都删不干净。

**修法**:
1. `.dockerignore` 排除 `.env`(还有 node_modules/.venv/data/.git);
2. 密钥**运行时经环境变量注入**,不写进 Dockerfile:
   ```yaml
   environment:
     - CHAT_API_KEY=${CHAT_API_KEY}  # 从宿主 .env 注入
   ```

**原理**:**密钥只存在于运行时环境,不进入任何可持久化/可传播的产物**(镜像、git、日志)。这是 Ch12 鉴权/成本控制会再次强化的安全底线。

## 补充:SQLite/ChromaDB 数据要挂命名卷

容器重建会丢数据,除非把 `data/` 挂到命名卷(`sqlite_data`、`chroma_data`)。**有状态服务的数据目录必须 volume**,否则「重启就空库」。
