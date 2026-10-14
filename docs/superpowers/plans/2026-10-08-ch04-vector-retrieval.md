# EvalFlow Ch04 真实向量检索可视化 Implementation Plan

> **For agentic workers:** 按 task 顺序逐个执行。步骤用 checkbox（`- [ ]`）追踪。每个 task 完成即验证通过；提交由用户指示（不自动 commit）。

**Goal:** 把 Ch02 的关键词检索换成真正的 embedding 向量检索（Ollama bge-m3 + ChromaDB），并可视化：run 详情页展示检索证据 + 相似度，新增知识库 2D 嵌入散点图（PCA）。

**Architecture:** Ollama 本地 bge-m3 生成 embedding（照 baby-ai）；ChromaDB PersistentClient 本地持久化；余弦相似度；numpy SVD 做 PCA 降维；前端 recharts ScatterChart 散点图。

**Tech Stack:** Python 3.12 + FastAPI + SQLite + ChromaDB + numpy + requests；前端 React 18 + antd v5 + recharts（沿用 Ch03）。

**Spec:** `docs/superpowers/specs/2026-10-08-ch04-vector-retrieval-design.md`

## Global Constraints

- embedding 来源定死：Ollama `bge-m3`（本地，需 `ollama serve` 启动），不接外部 embedding API、不装 torch。
- 向量库用 ChromaDB `PersistentClient`（不引入 Docker）；collection 显式配 cosine。
- 只做 dense 向量检索，不做 BM25 混合 / reranker（进阶参考 baby-ai）。
- 命中落 `Trace.retrieval_hits`（JSON 文本列），不新建 Retrieval 表。
- 每个 task 完成即验证；是否提交由用户指示。

---

### Task 1: 依赖 + 配置 + 启动 Ollama

**Files:**
- Modify: `pyproject.toml`(加 chromadb / numpy / requests)
- Modify: `backend/config.py`(加 embed 配置)

**Step 1: 加依赖**

```bash
cd /Users/lidong/Desktop/workFile/evalflow
# chromadb 依赖 onnxruntime;onnxruntime >=1.24 已无 Intel Mac(x86_64) wheel,必须 pin 到 1.23.2
uv add chromadb numpy requests "onnxruntime==1.23.2"
```

**Step 2: config.py 加 embedding 配置**

```python
class Settings(BaseSettings):
    ...
    embed_base_url: str = "http://localhost:11434"  # Ollama
    embed_model: str = "bge-m3"                     # 本机已下载
```

**Step 3: 启动 Ollama(实现/联调时需要)**

```bash
ollama serve   # 后台常驻;或确认已启动:ollama list 能连上
```

验证:`uv run python -c "import chromadb, numpy, requests; print('ok')"` 通过。

---

### Task 2: 知识库扩展(3 条 → 多分类 ~23 条)

**Files:**
- Modify: `backend/knowledge.py`

**Step 1: 改写 KNOWLEDGE 为带 id/category 的 chunk 列表**

```python
# 多分类育儿知识库(Ch04 扩充,供向量检索 + 散点图按 category 着色)
KNOWLEDGE = [
    # 发烧
    {"id": "fever-1", "category": "发烧", "text": "宝宝发烧38度以上可物理降温(温水擦浴);超过39度或持续不退要就医。"},
    {"id": "fever-2", "category": "发烧", "text": "退烧用药需遵医嘱,3月龄以下发热应尽快就医,不自行用药。"},
    {"id": "fever-3", "category": "发烧", "text": "热性惊厥时让宝宝侧卧、不要往嘴里塞东西,一般几分钟内自行缓解。"},
    {"id": "fever-4", "category": "发烧", "text": "发烧期间多补水,观察精神状态;精神差、拒奶、出皮疹要就医。"},
    # 辅食
    {"id": "food-1", "category": "辅食", "text": "满6个月可添加辅食,首选强化铁米粉,再逐步加菜泥、果泥。"},
    {"id": "food-2", "category": "辅食", "text": "新辅食一次只加一种,观察3天无过敏再加下一种。"},
    {"id": "food-3", "category": "辅食", "text": "辅食性状从泥糊状逐步过渡到碎末、小块,锻炼咀嚼。"},
    {"id": "food-4", "category": "辅食", "text": "一岁前辅食不加盐糖,蜂蜜一岁内禁用(有肉毒杆菌风险)。"},
    # 睡眠
    {"id": "sleep-1", "category": "睡眠", "text": "宝宝晚上总醒常见于出牙、睡眠倒退或环境不适,先排查温度与出牙。"},
    {"id": "sleep-2", "category": "睡眠", "text": "建立固定睡前程序(洗澡、喂奶、哄睡)有助于宝宝自主入睡。"},
    {"id": "sleep-3", "category": "睡眠", "text": "4月龄前后有睡眠倒退期,白天规律作息、夜间少干预可平稳度过。"},
    # 喂养
    {"id": "feed-1", "category": "喂养", "text": "喂奶后竖抱拍嗝能减少吐奶;吐奶量少、精神好多为生理性。"},
    {"id": "feed-2", "category": "喂养", "text": "肠绞痛多在傍晚哭闹,飞机抱、顺时针揉腹可缓解。"},
    {"id": "feed-3", "category": "喂养", "text": "奶量按需喂养,观察尿量(一天6片以上湿尿布)判断是否吃够。"},
    # 皮肤
    {"id": "skin-1", "category": "皮肤", "text": "湿疹要保湿,厚涂无香精润肤霜,洗澡水温别太高。"},
    {"id": "skin-2", "category": "皮肤", "text": "红屁屁勤换尿布、保持干燥,涂含氧化锌的护臀膏。"},
    {"id": "skin-3", "category": "皮肤", "text": "痱子要通风降温、穿纯棉透气衣,别捂太厚。"},
    # 疫苗
    {"id": "vaccine-1", "category": "疫苗", "text": "疫苗按接种本时间表打,轻微发热、接种部位红肿属常见反应。"},
    {"id": "vaccine-2", "category": "疫苗", "text": "接种当天多观察,体温超过38.5度或哭闹不止要及时就医。"},
    {"id": "vaccine-3", "category": "疫苗", "text": "急性发热、严重过敏史等暂缓接种,具体由接种医生评估。"},
    # 排便
    {"id": "stool-1", "category": "排便", "text": "母乳宝宝便便偏稀偏黄属正常,只要吃睡好、体重涨就不用担心。"},
    {"id": "stool-2", "category": "排便", "text": "便秘可顺时针揉腹、增加纤维辅食,必要时就医。"},
    {"id": "stool-3", "category": "排便", "text": "腹泻注意补水防脱水,精神差、尿量少、便血要就医。"},
]
```

> 注意:Ch02 的 `retriever.py` 依赖旧的 `KNOWLEDGE`(dict 带 `keywords`),Task 3 会一起改造,所以这里改了数据结构后,Task 3 完成前检索会报错——按顺序执行即可。

---

### Task 3: embedding + 向量检索(改造 retriever)

**Files:**
- Create: `backend/embedding.py`
- Modify: `backend/retriever.py`(关键词计数 → ChromaDB 向量检索)
- Modify: `backend/pipeline.py`(返回检索命中 hits)

**Step 1: embedding.py(照 baby-ai 的 /api/embed)**

```python
import requests

from backend.config import settings


def embed(texts: list[str]) -> list[list[float]]:
    """调用 Ollama 的 bge-m3 生成向量(参照 baby-ai 的 get_embedding)。"""
    r = requests.post(
        f"{settings.embed_base_url}/api/embed",
        json={"model": settings.embed_model, "input": texts},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embeddings"]
```

**Step 2: retriever.py(ChromaDB 向量检索)**

```python
import chromadb

from backend.embedding import embed
from backend.knowledge import KNOWLEDGE

_client = chromadb.PersistentClient(path="data/chroma")


def _coll():
    # cosine:ChromaDB 默认 L2,显式配余弦;distance 越小越相似
    return _client.get_or_create_collection("knowledge", metadata={"hnsw:space": "cosine"})


def ingest() -> None:
    """把知识库嵌入并灌进 ChromaDB(幂等:upsert 按 id 覆盖)。"""
    coll = _coll()
    coll.upsert(
        ids=[k["id"] for k in KNOWLEDGE],
        embeddings=embed([k["text"] for k in KNOWLEDGE]),
        documents=[k["text"] for k in KNOWLEDGE],
        metadatas=[{"category": k["category"]} for k in KNOWLEDGE],
    )


def retrieve(query: str, top_k: int = 2) -> list[dict]:
    """真实向量检索:query 嵌入 → ChromaDB 余弦 top-k,返回 [{text, score}]。"""
    coll = _coll()
    if coll.count() == 0:
        ingest()
    res = coll.query(
        query_embeddings=[embed([query])[0]],
        n_results=top_k,
        include=["documents", "distances"],
    )
    docs = res["documents"][0]
    dists = res["distances"][0]
    # cosine distance = 1 - 余弦相似度,所以 score = 1 - distance
    return [{"text": t, "score": round(1 - d, 4)} for t, d in zip(docs, dists)]
```

**Step 3: pipeline.py 返回 hits**

```python
def run_pipeline(question: str) -> dict:
    hits = retrieve(question)
    context = "\n".join(f"[{i+1}] {h['text']}" for i, h in enumerate(hits)) or "(无证据)"
    output = llm.chat([...])  # 同上不变
    return {"output": output, "retrieved_context": context, "hits": hits}
```

验证:Ollama 启动后 `uv run python -c "from backend.retriever import ingest, retrieve; ingest(); print(retrieve('宝宝发烧怎么办'))"` 能打出命中 + 分数。

---

### Task 4: 数据模型 + run_service 落检索命中

**Files:**
- Modify: `backend/models.py`(Trace 加 retrieval_hits)
- Modify: `backend/run_service.py`(落 hits 到 trace)
- Modify: `backend/db.py`(老库补列迁移)

**Step 1: models.py Trace 加列**

```python
class Trace(Base):
    ...
    retrieved_context = Column(Text)      # 检索证据拼接文本(忠实度用)
    retrieval_hits = Column(Text, default="[]")  # 检索命中 JSON:[{text, score, rank}]
```

**Step 2: db.py 迁移补 retrieval_hits**

```python
# 沿用 Ch03 的 _migrate:若 traces 表缺 retrieval_hits 就 ALTER 补上
def _migrate(engine) -> None:
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("traces")}
        if "retrieval_hits" not in cols:
            conn.execute(text("ALTER TABLE traces ADD COLUMN retrieval_hits VARCHAR DEFAULT '[]'"))
```

**Step 3: run_service.py 落 hits**

```python
import json
...
out = run_pipeline(it.input)
hits = [{"text": h["text"], "score": h["score"], "rank": i + 1}
        for i, h in enumerate(out["hits"])]
tr = Trace(run_id=run.id, dataset_item_id=it.id, input=it.input,
           output=out["output"], retrieved_context=out["retrieved_context"],
           retrieval_hits=json.dumps(hits, ensure_ascii=False),
           latency_ms=latency_ms)
```

验证:`uv run pytest` 现有测试仍绿(已把 retrieve 的 mock 点调整)。

---

### Task 5: PCA 降维 + /knowledge/map 接口

**Files:**
- Create: `backend/pca.py`
- Modify: `backend/main.py`(加 GET /knowledge/map + traces 补 retrieval_hits)

**Step 1: pca.py(numpy SVD 降到 2 维)**

```python
import numpy as np


def fit_pca(vectors: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    """在训练向量(知识块)上拟合 PCA 基底,返回 (均值, 前2主方向)。"""
    X = np.array(vectors)
    mean = X.mean(axis=0)
    _, _, Vt = np.linalg.svd(X - mean, full_matrices=False)
    return mean, Vt[:2].T  # (d,) 与 (d, 2)


def project(vectors: list[list[float]], mean: np.ndarray, basis: np.ndarray) -> list[tuple[float, float]]:
    """把向量投影到已拟合的 2D PCA 基底(知识块定基底,query 投影到同一坐标系)。"""
    if not vectors:
        return []
    X = np.array(vectors)
    pts = (X - mean) @ basis
    return [tuple(float(v) for v in row) for row in pts]
```

> 关键:基底只由**知识块**拟合,query 只做投影——若把知识块 + query 一起 PCA,query 数量远多于知识块时(此处 70:23)会主导主方向,把知识块挤成一团、看不出分类聚类。

**Step 2: main.py 加 /knowledge/map**

```python
@app.get("/knowledge/map")
def knowledge_map():
    """知识库可视化:知识块拟合 PCA 基底,样本问题投影到同一 2D 坐标系。"""
    from backend.embedding import embed
    from backend.knowledge import KNOWLEDGE
    from backend.pca import fit_pca, project

    s = SessionLocal()
    inputs = [it.input for it in s.query(DatasetItem).all()]
    s.close()

    chunk_texts = [k["text"] for k in KNOWLEDGE]
    chunk_vecs = embed(chunk_texts)
    mean, basis = fit_pca(chunk_vecs)
    chunk_pts = project(chunk_vecs, mean, basis)
    query_pts = project(embed(inputs), mean, basis) if inputs else []

    chunks = [{"id": KNOWLEDGE[i]["id"], "text": KNOWLEDGE[i]["text"],
               "category": KNOWLEDGE[i]["category"],
               "x": round(chunk_pts[i][0], 4), "y": round(chunk_pts[i][1], 4)}
              for i in range(len(chunk_texts))]
    queries = [{"input": inputs[j],
                "x": round(query_pts[j][0], 4), "y": round(query_pts[j][1], 4)}
               for j in range(len(inputs))]
    return {"chunks": chunks, "queries": queries}
```

**Step 3: main.py traces 补 retrieval_hits(解析 JSON)**

```python
# list_traces 里,每行 trace 增加:
"retrieval_hits": json.loads(tr.retrieval_hits or "[]")
```

验证:后端起 + Ollama 起,`curl localhost:8000/knowledge/map` 返回带 x/y 的 chunks 与 queries。

---

### Task 6: 前端(证据分数 + 知识库散点图)

**Files:**
- Modify: `src/types.ts`、`src/api/index.ts`
- Create: `src/components/EmbeddingScatter.tsx`
- Create: `src/views/KnowledgeMapView.tsx`
- Modify: `src/App.tsx`(路由 + 菜单)
- Modify: `src/views/RunDetailView.tsx`(证据列渲染 hits)

**Step 1: types.ts + api/index.ts**

```ts
// types.ts
export interface KnowledgeChunk { id: string; text: string; category: string; x: number; y: number }
export interface KnowledgeQuery { input: string; x: number; y: number }
export interface KnowledgeMap { chunks: KnowledgeChunk[]; queries: KnowledgeQuery[] }
// TraceRow 加:
export interface TraceRow { ...; retrieval_hits?: { text: string; score: number; rank: number }[] }

// api/index.ts
getKnowledgeMap: (signal?: AbortSignal) => request<KnowledgeMap>("/knowledge/map", { signal }),
```

**Step 2: EmbeddingScatter.tsx(recharts ScatterChart)**

```tsx
import { Empty } from "antd";
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

const COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

export default function EmbeddingScatter({ chunks, queries }: { chunks: KnowledgeChunk[]; queries: KnowledgeQuery[] }) {
  if (!chunks.length) return <Empty description="暂无知识库数据" style={{ margin: "0 auto" }} />;
  // 按 category 分组,每组一个 Scatter 系列,用不同颜色
  const cats = Array.from(new Set(chunks.map((c) => c.category)));
  return (
    <ResponsiveContainer width="100%" height={420}>
      <ScatterChart>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" dataKey="x" name="x" />
        <YAxis type="number" dataKey="y" name="y" />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
        <Legend />
        {cats.map((cat, i) => (
          <Scatter key={cat} name={cat} data={chunks.filter((c) => c.category === cat)} fill={COLORS[i % COLORS.length]} />
        ))}
        <Scatter name="query" data={queries} fill="#000000" shape="cross" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
```

**Step 3: KnowledgeMapView.tsx**

```tsx
import { Button, Result, Skeleton } from "antd";
import { api } from "../api";
import { useRequest } from "../hooks/useRequest";
import EmbeddingScatter from "../components/EmbeddingScatter";

export default function KnowledgeMapView() {
  const { data, loading, error, reload } = useRequest((s) => api.getKnowledgeMap(s));
  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;
  if (error) return <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />;
  return <EmbeddingScatter chunks={data?.chunks ?? []} queries={data?.queries ?? []} />;
}
```

**Step 4: App.tsx 加路由 + 菜单**

```tsx
// 菜单加一项(选中态按 pathname 前缀判断):
//   /knowledge → "knowledge" 高亮
// 路由加:
<Route path="/knowledge" element={<KnowledgeMapView />} />
```

**Step 5: RunDetailView 证据列渲染 hits**

```tsx
// 「证据」列从 dataIndex="retrieved_context" 改为 render,展示命中的块 + 分数
{ title: "证据", dataIndex: "retrieval_hits",
  render: (hits?: { text: string; score: number; rank: number }[]) =>
    hits?.length
      ? hits.map((h) => <div key={h.rank}><Tag color="blue">#{h.rank} 相似度 {h.score}</Tag> {h.text}</div>)
      : "—" }
```

验证:`npm run build` 通过 + 起后端 & Ollama,`/knowledge` 看到散点图,run 详情证据列带分数。

---

### Task 7: 测试(后端 + 前端)

**Files:**
- Modify: `tests/test_api.py` 或新增 `tests/test_retriever.py`、`tests/test_pca.py`
- Create: `src/views/__tests__/KnowledgeMapView.test.tsx`

**Step 1: 后端测试(mock embed,不依赖 Ollama)**

```python
# test_retriever.py —— 用 monkeypatch 把 embed 换成确定性假向量,测检索逻辑
def test_retrieve_returns_topk_with_scores(monkeypatch):
    from backend import retriever
    # 每个文本映射到一个固定向量,保证余弦排序可预期
    monkeypatch.setattr(retriever, "embed",
                        lambda texts: [[1.0, 0.0] if "发烧" in t else [0.0, 1.0] for t in texts])
    hits = retriever.retrieve("宝宝发烧", top_k=2)
    assert hits and all("score" in h and "text" in h for h in hits)
    assert hits[0]["score"] >= hits[-1]["score"]  # 按分数降序

# test_pca.py
def test_pca_projects_to_2d():
    from backend.pca import fit_pca, project
    mean, basis = fit_pca([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    pts = project([[1, 0, 0], [0, 1, 0], [0, 0, 1]], mean, basis)
    assert len(pts) == 3 and all(len(p) == 2 for p in pts)
```

**Step 2: 前端 KnowledgeMapView 测试(mock api)**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { api } from "../../api";
import KnowledgeMapView from "../KnowledgeMapView";

vi.mock("../../api", () => ({ api: { getKnowledgeMap: vi.fn() } }));

test("渲染知识库散点图", async () => {
  vi.mocked(api.getKnowledgeMap).mockResolvedValue({
    chunks: [{ id: "fever-1", text: "发烧物理降温", category: "发烧", x: 0, y: 0 }],
    queries: [],
  });
  render(<KnowledgeMapView />);
  await waitFor(() => expect(screen.getByText("发烧")).toBeInTheDocument());
});
```

验证:`uv run pytest` 全绿、`npm test` 全绿、`npm run build` 通过。

---

### 验收(端到端)

1. `ollama serve` 启动 Ollama(bge-m3 已下载)。
2. 后端 `uv run uvicorn backend.main:app --reload --port 8000`;前端 `npm run dev`(5173)。
3. 浏览器:发起一次 run,详情页「证据」列显示命中知识块 + 相似度分数;打开 `/knowledge` 看到 2D 散点图(按分类着色,query 用叉号叠加)。
4. `uv run pytest` 后端全绿、`npm test` 前端全绿、`npm run build` 通过。
