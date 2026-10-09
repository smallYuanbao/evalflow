# EvalFlow Ch04 设计:真实向量检索可视化

## 目标

Ch03 之后,「评测平台」已经闭环:建评测集 → 发起 run → 看三层指标 + 分桶 + 逐条 trace。但检索那一步还是 Ch02 的关键词计数(`retriever.py` 数关键词命中),不是真正的向量检索。

Ch04 把检索换成**真正的 embedding 向量检索**,并把检索过程「可视化」出来:

1. run 详情页:每条样本命中了哪些知识块、相似度多少(不再是纯文本证据)。
2. 新增「知识库可视化」页:2D 嵌入散点图(PCA 降维),直观看到语义相近的知识块聚在一起。

**embedding 与向量库参照 baby-ai 的实现**(用户指定):embedding 用 **Ollama 本地 `bge-m3`**,向量库用 **ChromaDB**。本机已装 Ollama 且 `bge-m3` 已下载(1.2GB),实现时只需 `ollama serve` 启动服务。

验收标准:
1. `retriever.retrieve` 走真实向量检索(Ollama bge-m3 + ChromaDB),按余弦相似度返回 top-k,不再是关键词计数。
2. 知识库从 3 条扩展到多分类约 20~30 条,能嵌入并持久化到 ChromaDB(重启不丢、可重复灌库)。
3. run 详情页:每条 trace 的「检索证据」展示命中的知识块 + 相似度分数。
4. 新增「知识库可视化」页:2D 散点图(PCA 降维),语义相近的知识块聚在一起,不同分类不同颜色。
5. 前端/后端测试 + build 全绿。

## 技术栈(定死,不可自行更换)

- embedding:Ollama `bge-m3`(本地 HTTP,参照 baby-ai;需 `ollama serve` 启动)。
- 向量库:ChromaDB `PersistentClient`(本地持久化,**不引入 Docker**,比 baby-ai 的 Docker HttpClient 更轻)。
- 相似度:余弦(cosine)——面试最常问;ChromaDB 默认 L2,显式配 `hnsw:space=cosine`。
- 降维:numpy SVD 实现 PCA 到 2 维(不引 sklearn)。
- 前端:复用 Ch03 的 recharts,新增 `ScatterChart` 散点图。
- 后端:复用 Ch03 的 FastAPI + SQLite,新增向量检索 + 可视化接口。

## 架构与数据流

```
                  ┌─────────────────────────────────────────────┐
                  │        首次检索时灌库(ingest)               │
                  │  knowledge.py 多分类 chunk ──embed──┐        │
                  │                                     ▼        │
                  │                              ChromaDB       │
                  │                          collection=knowledge│
                  │                          (cosine,持久化)     │
                  └─────────────────────────────────────────────┘

评测 run 时(每条样本 question):
  question ──embed──▶ query 向量 ──ChromaDB.query──▶ top-k 命中
                                                       (chunk + cosine score)
        │
        ▼
  pipeline.py:检索证据拼进 prompt → LLM 生成 → 返回 output + retrieved_context + hits
        │
        ▼
  run_service.py:把 hits 落进 Trace.retrieval_hits(JSON)

可视化:
  1) run 详情页:traces 的 retrieval_hits 渲染成「知识块 + 分数」列表
  2) /knowledge 页:所有知识块 embedding ──PCA──▶ 2D 坐标 ──ScatterChart──▶ 散点(按 category 着色)
```

## 后端补齐(Ch04 需要)

1. `backend/embedding.py`:调 Ollama `bge-m3` 生成向量(照 baby-ai 的 `/api/embed`,用 `requests`)。
2. `backend/knowledge.py`:3 条 → 多分类约 20~30 条 chunk(带 `category` 标签,散点图着色用)。
3. `backend/retriever.py`:改造成 ChromaDB 向量检索——`ingest()` 灌库 + `retrieve(query, top_k)` 返回 `[{text, score}]`。
4. `backend/models.py`:`Trace` 加 `retrieval_hits`(Text,存 JSON 字符串 `[{text, score, rank}]`)。
5. `backend/run_service.py`:把检索命中落进 trace 的 `retrieval_hits`。
6. `backend/pca.py`:numpy SVD 手写 PCA——知识块拟合 2D 基底,query 投影到同一坐标系(供散点图)。
7. `backend/main.py`:新增 `GET /knowledge/map`(返回知识块的 2D 坐标 + category);`GET /runs/{id}/traces` 补 `retrieval_hits`。

## 接口契约(前端视角)

### GET /knowledge/map
知识库可视化数据(后端对知识块 embedding 做 PCA 降维):
`{chunks: [{id, text, category, x, y}], queries: [{input, x, y}]}`
- `chunks`:所有知识块的 2D 投影(散点主体,按 category 着色)。
- `queries`:可选,把评测集里所有样本问题也投影进来叠加展示(让用户看到 query 落在哪些知识块附近)。

### GET /runs/{id}/traces(扩展)
每行新增 `retrieval_hits: [{text, score, rank}]`(该样本检索命中的知识块 + 相似度,rank 从 1 起)。

## 前端改动

- 新组件 `EmbeddingScatter.tsx`:recharts `ScatterChart`,chunks 按 category 着色,queries 用另一种标记叠加。
- 新视图 `KnowledgeMapView.tsx`(路由 `/knowledge`),顶部菜单加「知识库」。
- `RunDetailView.tsx`:「证据」列从纯文本升级为「知识块 + 相似度分数」列表(读 `retrieval_hits`)。
- `types.ts` + `api/index.ts` 加 `getKnowledgeMap` 与 `retrieval_hits` 类型。

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| embedding 来源 | Ollama 本地 `bge-m3`(参照 baby-ai) | DeepSeek 无 embedding 接口;本地 sentence-transformers 要装 torch(~2GB);Ollama 已装且 bge-m3 已下载,零 key、零 torch |
| 向量库 | ChromaDB `PersistentClient` | baby-ai 用 Docker HttpClient;EvalFlow 保持无 Docker,PersistentClient 零部署、本地持久化 |
| 相似度 | 余弦 cosine | 面试最常问;ChromaDB 默认 L2,显式配 cosine 更贴合「语义相似」 |
| 降维 | numpy SVD 手写 PCA | sklearn 太重;知识块几十个点,numpy SVD 够用且把 PCA 原理讲透 |
| 命中落库 | `Trace.retrieval_hits`(JSON 文本) | 新表 `Retrieval`:更规范但 Ch04 用 JSON 列更轻、够演示 |
| 知识库 | 3 条 → 多分类约 20~30 条 | 散点图要有簇,3 个点看不出聚类;多分类顺带把召回评得更有区分度 |
| 灌库时机 | 首次检索时 lazy `ingest()`(库空才灌,幂等 upsert) | 启动时灌:启动即连 Ollama、慢启动且测试要 mock;lazy 灌把「灌库」推迟到真正需要时,幂等所以可重复执行 |
| onnxruntime 兼容 | pin `onnxruntime==1.23.2` | chromadb 依赖 onnxruntime(无上限),而 >=1.24 已无 Intel Mac(x86_64)wheel;1.23.2 是最后一个带 x86_64 mac wheel 的版本 |

## 本章不做

- 混合检索 BM25 + 精排 reranker(baby-ai 有,属进阶,Ch04 只做 dense 向量检索)。
- 查询改写 / 多路召回 / 缓存熔断(baby-ai 的工程加固,不属于「向量检索可视化」主线)。
- Docker 部署 ChromaDB、向量库集群/多租户。
- embedding 模型微调 / 自定义训练。
