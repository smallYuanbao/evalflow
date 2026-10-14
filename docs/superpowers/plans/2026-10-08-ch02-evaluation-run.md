# EvalFlow Ch02 评测主流程 Implementation Plan

> **For agentic workers:** 按 task 顺序逐个执行。步骤用 checkbox（`- [ ]`）追踪。每个 task 完成即测试通过；提交由用户指示（不自动 commit）。

**Goal:** 跑通评测主流程:建评测集 → 发起 run → 逐条「检索+生成」→ recall/faithfulness 打分 → 落库可查。run 状态机 running→done/failed。

**Architecture:** 复用 Ch01 单进程 FastAPI + SQLite,新增 `openai` 客户端(生成+judge)、后台 BackgroundTasks 串行跑 run。检索用内存知识库 + 关键词匹配(最小实现)。

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy, pydantic-settings, openai, pytest。

**Spec:** `docs/superpowers/specs/2026-10-08-ch02-evaluation-run-design.md`

## Global Constraints

- 技术选型定死:复用 Ch01 + `openai` 包 + FastAPI BackgroundTasks,不许换。
- 密钥从 .env 读(`settings.chat_*`),不进仓库、不硬编码、不打印。
- judge 温度固定 0;judge 失败记 NULL 不记 0;recall 机械匹配不碰 LLM。
- run 串行跑(不并发写 SQLite 单文件)。
- `run_pipeline` 签名不变(`{output, retrieved_context}`),只换内部实现。
- 每个 task 完成即测试通过;是否提交由用户指示。

---

### Task 1: LLM 客户端 + judge prompt

**Files:**
- Modify: `pyproject.toml`(uv add openai)
- Create: `backend/llm.py`, `backend/prompts.py`
- Test: `tests/test_llm.py`(仅测 chat_json 解析,mock 客户端,不调真实 LLM)

**Interfaces:**
- `llm.chat(messages, temperature=0.0) -> str`:普通对话,返回文本。
- `llm.chat_json(messages, temperature=0.0) -> dict | None`:JSON mode 强制输出 JSON,解析失败返回 None。
- `prompts.FAITHFULNESS_PROMPT`:faithfulness judge 的 prompt 模板(含 `{context}` / `{answer}` 占位)。

**面试要点(要能复述):**
- 为什么 judge 温度 0——评分不能有温度,同一份证据+答案重放不能跳分。

**Step 1: 装 openai 包**

```bash
cd /Users/lidong/Desktop/workFile/evalflow
uv add openai
```

**Step 2: llm.py**

```python
import json

from openai import OpenAI

from backend.config import settings

_client = OpenAI(api_key=settings.chat_api_key, base_url=settings.chat_base_url)


def chat(messages: list[dict], temperature: float = 0.0) -> str:
    r = _client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
    )
    return r.choices[0].message.content or ""


def chat_json(messages: list[dict], temperature: float = 0.0) -> dict | None:
    """JSON mode 强制输出 JSON;解析失败返回 None(调用方按失败处理)。"""
    r = _client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = r.choices[0].message.content or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None
```

**Step 3: prompts.py**

```python
FAITHFULNESS_PROMPT = """你是 RAG 评测裁判,判断「回答」是否忠实于「证据」:回答里每个论断都要能在证据里找到依据,不编造、不夸大。

证据:
{context}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""
```

**Step 4: 测试(mock 客户端,不调真实 LLM)**

`tests/test_llm.py`:

```python
from types import SimpleNamespace

from backend import llm


def _fake_resp(content: str):
    # 模拟 openai 响应结构:resp.choices[0].message.content
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_chat_json_parses(monkeypatch):
    monkeypatch.setattr(
        llm._client.chat.completions, "create",
        lambda **kw: _fake_resp('{"score": 0.8, "reason": "ok"}'),
    )
    assert llm.chat_json([{"role": "user", "content": "x"}]) == {"score": 0.8, "reason": "ok"}


def test_chat_json_bad_json_returns_none(monkeypatch):
    monkeypatch.setattr(
        llm._client.chat.completions, "create",
        lambda **kw: _fake_resp("不是 json"),
    )
    assert llm.chat_json([{"role": "user", "content": "x"}]) is None
```

运行 `uv run pytest` 通过。

---

### Task 2: 最小检索 + 管线升级(真检索+真生成)

**Files:**
- Create: `backend/knowledge.py`, `backend/retriever.py`
- Modify: `backend/pipeline.py`(mock → 真检索+真生成)
- Test: `tests/test_retriever.py`

**Interfaces:**
- `knowledge.KNOWLEDGE`:内存知识库,每条 `{keywords: [..], text: ..}`。
- `retriever.retrieve(query, top_k=2) -> list[str]`:关键词匹配,返回命中条目的 text 列表。
- `pipeline.run_pipeline(question) -> dict`:签名不变,内部 retrieve + llm.chat。

**面试要点(要能复述):**
- 为什么 Ch02 检索用最小实现(关键词匹配)——Ch02 重点是「跑通评测流程」,别把这一章变成 RAG 章节;真实向量检索后置。

**Step 1: knowledge.py**

```python
# 内存知识库(Ch02 最小检索源,真实向量检索 Ch03/Ch04)
# 注意:text 里的措辞要和 seed 的 expected_output 要点对齐,recall 是子串匹配
KNOWLEDGE = [
    {"keywords": ["发烧", "退烧", "体温"],
     "text": "宝宝发烧38度以上可物理降温(温水擦浴);超过39度或持续不退要就医;退烧用药需遵医嘱。"},
    {"keywords": ["辅食", "米粉"],
     "text": "满6个月可添加辅食,首选强化铁米粉,再逐步加菜泥、果泥。"},
    {"keywords": ["夜醒", "睡眠", "总醒"],
     "text": "宝宝晚上总醒常见于出牙、睡眠倒退或环境不适,先排查温度与出牙。"},
]
```

**Step 2: retriever.py**

```python
from backend.knowledge import KNOWLEDGE


def retrieve(query: str, top_k: int = 2) -> list[str]:
    """最小检索:关键词命中数越多排名越前。"""
    scored = []
    for k in KNOWLEDGE:
        hits = sum(1 for kw in k["keywords"] if kw in query)
        if hits > 0:
            scored.append((hits, k["text"]))
    scored.sort(key=lambda x: -x[0])
    return [text for _, text in scored[:top_k]]
```

**Step 3: pipeline.py 升级**

```python
from backend import llm
from backend.retriever import retrieve


def run_pipeline(question: str) -> dict:
    """检索 + 生成(真实 LLM)。签名不变,内部从 mock 换成真实现。"""
    context_list = retrieve(question)
    context = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(context_list)) or "(无证据)"
    output = llm.chat([
        {"role": "system", "content": "你是育儿客服助手,只依据给定证据回答,证据没有就说不清楚。"},
        {"role": "user", "content": f"证据:\n{context}\n\n问题:{question}"},
    ])
    return {"output": output, "retrieved_context": context}
```

**Step 4: 测试**

`tests/test_retriever.py`:

```python
from backend.retriever import retrieve


def test_retrieve_fever():
    texts = retrieve("宝宝发烧38度怎么办")
    assert any("物理降温" in t for t in texts)


def test_retrieve_no_match_returns_empty():
    assert retrieve("今天天气怎么样") == []
```

运行 `uv run pytest` 通过。

---

### Task 3: 两个 evaluator(recall 机械 + faithfulness judge)

**Files:**
- Create: `backend/evaluators.py`
- Test: `tests/test_evaluators.py`

**Interfaces:**
- `recall(expected_output: str, retrieved_context: str) -> float`:要点命中率 0~1,机械匹配。
- `faithfulness(output: str, retrieved_context: str) -> dict | None`:返回 `{"score", "reason"}`;judge 失败返回 None。

**面试要点(要能复述,这章核心):**
- recall 机械 vs faithfulness LLM——分层解耦,检索段确定性可复现,上游 LLM 挂了 recall 照样跑。
- judge 挂返回 None(记 NULL)——「没评上」≠「零分」,失败样本不污染均值。

**Step 1: evaluators.py**

```python
from backend import llm
from backend.prompts import FAITHFULNESS_PROMPT


def recall(expected_output: str, retrieved_context: str) -> float:
    """机械匹配:ground truth 要点命中率。expected_output 用 / 切要点,判断子串是否出现在 context。"""
    points = [p.strip() for p in expected_output.split("/") if p.strip()]
    if not points:
        return 0.0
    hits = sum(1 for p in points if p in retrieved_context)
    return round(hits / len(points), 4)


def faithfulness(output: str, retrieved_context: str) -> dict | None:
    """LLM judge,温度 0。失败返回 None(记 NULL 不记 0)。"""
    prompt = FAITHFULNESS_PROMPT.format(context=retrieved_context, answer=output)
    try:
        raw = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.0)
        if raw is None or "score" not in raw:
            return None
        score = float(raw["score"])
        score = min(max(score, 0.0), 1.0)
        return {"score": round(score, 4), "reason": str(raw.get("reason", ""))}
    except Exception:
        return None
```

**Step 2: 测试(recall 确定性 + faithfulness 失败注入,不调真实 LLM)**

`tests/test_evaluators.py`:

```python
from backend import evaluators


def test_recall_full_hit():
    ctx = "宝宝发烧38度以上可物理降温;超过39度要就医;退烧用药需遵医嘱。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == 1.0


def test_recall_partial_hit():
    ctx = "宝宝发烧可物理降温。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == round(1 / 3, 4)


def test_faithfulness_failure_returns_none(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: None)
    assert evaluators.faithfulness("答", "证") is None
```

运行 `uv run pytest` 通过。

---

### Task 4: run 生命周期(run_service 状态机)

**Files:**
- Create: `backend/run_service.py`
- Test: `tests/test_run_service.py`(mock 管线,不调真实 LLM)

**Interfaces:**
- `run_service.execute_run(run_id: int) -> None`:遍历 run 对应评测集的所有 item,逐条跑管线+打分+落库;全部完成 status=done,异常 status=failed。

**面试要点(要能复述):**
- 单条 judge 挂只让该条 score 记 NULL,继续下一条,不算 run 失败;只有 run 级异常才 failed。

**Step 1: run_service.py**

```python
import time

from backend.db import SessionLocal
from backend.evaluators import faithfulness, recall
from backend.models import DatasetItem, Run, Score, Trace
from backend.pipeline import run_pipeline


def execute_run(run_id: int) -> None:
    s = SessionLocal()
    run = s.get(Run, run_id)
    items = s.query(DatasetItem).filter(DatasetItem.dataset_id == run.dataset_id).all()
    try:
        for it in items:
            t0 = time.time()
            out = run_pipeline(it.input)
            latency_ms = int((time.time() - t0) * 1000)
            tr = Trace(run_id=run.id, dataset_item_id=it.id,
                       input=it.input, output=out["output"],
                       retrieved_context=out["retrieved_context"], latency_ms=latency_ms)
            s.add(tr)
            s.flush()
            # recall 机械匹配(确定性)
            s.add(Score(trace_id=tr.id, name="recall",
                        value=recall(it.expected_output, out["retrieved_context"])))
            # faithfulness LLM judge(可能挂,挂则 NULL)
            f = faithfulness(out["output"], out["retrieved_context"])
            if f is None:
                s.add(Score(trace_id=tr.id, name="faithfulness", value=None, comment="judge 失败"))
            else:
                s.add(Score(trace_id=tr.id, name="faithfulness", value=f["score"], comment=f["reason"]))
        run.status = "done"
        s.commit()
    except Exception:
        s.rollback()
        run = s.get(Run, run_id)
        run.status = "failed"
        s.commit()
    finally:
        s.close()
```

**Step 2: 测试(mock 管线跑通状态机)**

`tests/test_run_service.py`:

```python
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace
from backend import run_service


def _seed_run(monkeypatch):
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q: {"output": f"答:{q}", "retrieved_context": "物理降温 就医 用药"},
    )
    monkeypatch.setattr(
        run_service, "faithfulness",
        lambda o, c: {"score": 0.9, "reason": "ok"},
    )
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds); s.flush()
    s.add(DatasetItem(dataset_id=ds.id, input="q1", expected_output="物理降温/就医/用药", bucket="a"))
    run = Run(dataset_id=ds.id, status="running", config="{}")
    s.add(run); s.commit()
    rid = run.id
    s.close()
    return rid


def test_execute_run_done(monkeypatch):
    rid = _seed_run(monkeypatch)
    run_service.execute_run(rid)
    s = SessionLocal()
    run = s.get(Run, rid)
    assert run.status == "done"
    assert s.query(Trace).filter(Trace.run_id == rid).count() == 1
    names = {sc.name for sc in s.query(Score).filter(Score.trace_id == s.query(Trace).filter(Trace.run_id == rid).first().id)}
    assert names == {"recall", "faithfulness"}
    s.close()


def test_execute_run_failed(monkeypatch):
    rid = _seed_run(monkeypatch)

    def _boom(q):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_service, "run_pipeline", _boom)
    run_service.execute_run(rid)
    s = SessionLocal()
    assert s.get(Run, rid).status == "failed"
    s.close()
```

运行 `uv run pytest` 通过。

---

### Task 5: API 层(CRUD + run 发起 + 结果查询)+ seed 升级

**Files:**
- Modify: `backend/main.py`(加 CRUD + run 接口,含 lifespan init_db)
- Modify: `backend/seed.py`(只造评测集,移除 run/trace/score)
- Create: `conftest.py`(测试会话自动建表)
- Test: `tests/test_api.py`

**Interfaces:**
- `POST /datasets`、`POST /datasets/{id}/items`、`GET /datasets`
- `POST /runs`(BackgroundTasks 后台跑)、`GET /runs/{id}`(聚合)、`GET /runs/{id}/traces`(明细)

**Step 1: main.py 升级**

```python
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from backend.db import SessionLocal
from backend.models import Dataset, DatasetItem, Run, Score, Trace
from backend.run_service import execute_run

app = FastAPI(title="EvalFlow", version="0.2.0")


class DatasetIn(BaseModel):
    name: str
    description: str = ""


class ItemIn(BaseModel):
    input: str
    expected_output: str
    bucket: str = ""


class RunIn(BaseModel):
    dataset_id: int
    config: str = "{}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/datasets")
def create_dataset(body: DatasetIn):
    s = SessionLocal()
    ds = Dataset(name=body.name, description=body.description)
    s.add(ds); s.commit(); s.refresh(ds)
    s.close()
    return {"id": ds.id, "name": ds.name, "description": ds.description}


@app.post("/datasets/{dataset_id}/items")
def add_item(dataset_id: int, body: ItemIn):
    s = SessionLocal()
    it = DatasetItem(dataset_id=dataset_id, input=body.input,
                     expected_output=body.expected_output, bucket=body.bucket)
    s.add(it); s.commit(); s.refresh(it)
    s.close()
    return {"id": it.id, "input": it.input, "bucket": it.bucket}


@app.get("/datasets")
def list_datasets():
    s = SessionLocal()
    ds = s.query(Dataset).all()
    s.close()
    return [{"id": d.id, "name": d.name, "description": d.description} for d in ds]


@app.post("/runs")
def create_run(body: RunIn, background: BackgroundTasks):
    s = SessionLocal()
    run = Run(dataset_id=body.dataset_id, status="running", config=body.config)
    s.add(run); s.commit(); s.refresh(run)
    rid = run.id
    s.close()
    background.add_task(execute_run, rid)
    return {"id": rid, "status": "running"}


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    s = SessionLocal()
    run = s.get(Run, run_id)
    traces = s.query(Trace).filter(Trace.run_id == run_id).all()
    recall_vals = []
    faith_vals = []
    for tr in traces:
        for sc in s.query(Score).filter(Score.trace_id == tr.id):
            if sc.name == "recall" and sc.value is not None:
                recall_vals.append(sc.value)
            if sc.name == "faithfulness" and sc.value is not None:
                faith_vals.append(sc.value)
    s.close()

    def avg(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {"id": run.id, "dataset_id": run.dataset_id, "status": run.status,
            "config": run.config, "item_count": len(traces),
            "scores": {"recall_avg": avg(recall_vals), "faithfulness_avg": avg(faith_vals)}}


@app.get("/runs/{run_id}/traces")
def list_traces(run_id: int):
    s = SessionLocal()
    out = []
    for tr in s.query(Trace).filter(Trace.run_id == run_id):
        scs = [{"name": sc.name, "value": sc.value}
               for sc in s.query(Score).filter(Score.trace_id == tr.id)]
        out.append({"trace_id": tr.id, "input": tr.input, "output": tr.output,
                    "retrieved_context": tr.retrieved_context,
                    "latency_ms": tr.latency_ms, "scores": scs})
    s.close()
    return out
```

**Step 2: seed.py 升级(只造评测集,移除 run/trace/score)**

Ch01 的 seed 里那段「插 run + 跑管线 + 插 trace/score」要删掉——因为 run_pipeline 已经是真 LLM 调用,seed 再跑会烧 key 还重复;run/trace/score 现在归 run 生命周期管。seed 只负责造评测集,且 expected_output 与 `knowledge.py` 措辞对齐(recall 是子串匹配):

```python
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem


def seed() -> None:
    init_db()
    s = SessionLocal()
    ds = Dataset(name="育儿-常见病", description="示例评测集")
    s.add(ds)
    s.flush()
    items = [
        DatasetItem(dataset_id=ds.id, input="宝宝发烧38度怎么办",
                    expected_output="物理降温/就医/用药", bucket="护理"),
        DatasetItem(dataset_id=ds.id, input="6个月能加辅食吗",
                    expected_output="满6个月/铁米粉", bucket="喂养"),
        DatasetItem(dataset_id=ds.id, input="宝宝晚上总醒怎么回事",
                    expected_output="出牙/睡眠倒退/环境", bucket="睡眠"),
    ]
    s.add_all(items)
    s.commit()
    s.close()


if __name__ == "__main__":
    seed()
```

**Step 3: 测试(API,不调真实 LLM)**

`tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_datasets_crud():
    r = client.post("/datasets", json={"name": "t", "description": "d"})
    assert r.status_code == 200 and r.json()["name"] == "t"
    did = r.json()["id"]
    r = client.post(f"/datasets/{did}/items", json={"input": "q", "expected_output": "a/b", "bucket": "x"})
    assert r.status_code == 200
    assert client.get("/datasets").json()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}
```

运行 `uv run pytest` 通过。

---

### Task 6: 难样本 + 分桶聚合(让 demo 分数拉开差距)

**Files:**
- Create: `backend/stats.py`
- Modify: `backend/main.py`(get_run 委托 aggregate_run)
- Modify: `backend/seed.py`(补 2 条难样本)
- Test: `tests/test_stats.py`

**动机:** 上一版 demo 分数清一色 1.0,看不出平台「抓问题」的能力。补难样本 + 分桶后,一次 run 就能定位「哪个桶、什么原因丢分」。

**难样本两类(复用现有 recall/faithfulness,不新增指标):**
- KB 缺口题:`宝宝发烧38度怎么办需要观察什么`,expected_output 多一个库里没有的点「观察精神状态」→ recall 0.75。
- 口语检索漏题:`娃夜里老闹腾不睡觉咋办`,关键词不命中 → 检索空 → recall 0.0(模型诚实拒答,faithfulness 仍 1.0)。

**库外题暂不加:** 它需要第三个指标「拒答率」(库外 recall=0 是「正确拒答」不是「失败」),硬塞进 recall 会误导分桶,留作下一步。

**Step 1: stats.py(聚合 + 分桶)**

```python
from collections import defaultdict

from backend.db import SessionLocal
from backend.models import DatasetItem, Run, Score, Trace


def _avg(vals):
    return round(sum(vals) / len(vals), 4) if vals else None


def aggregate_run(run_id: int) -> dict:
    """聚合一次 run 的分数:整体均值 + 按 bucket 分组均值。judge 挂(NULL)不参与均值。"""
    s = SessionLocal()
    run = s.get(Run, run_id)
    traces = s.query(Trace).filter(Trace.run_id == run_id).all()

    item_ids = [tr.dataset_item_id for tr in traces]
    bucket_by_item = dict(
        s.query(DatasetItem.id, DatasetItem.bucket).filter(DatasetItem.id.in_(item_ids))
    ) if item_ids else {}

    score_by_trace = defaultdict(dict)
    if traces:
        for sc in s.query(Score).filter(Score.trace_id.in_([tr.id for tr in traces])):
            score_by_trace[sc.trace_id][sc.name] = sc.value
    s.close()

    overall = {"recall": [], "faithfulness": []}
    buckets = defaultdict(lambda: {"recall": [], "faithfulness": []})
    count_by_bucket = defaultdict(int)
    for tr in traces:
        b = bucket_by_item.get(tr.dataset_item_id, "未分桶")
        count_by_bucket[b] += 1
        for key in ("recall", "faithfulness"):
            v = score_by_trace.get(tr.id, {}).get(key)
            if v is not None:
                overall[key].append(v)
                buckets[b][key].append(v)

    by_bucket = {
        b: {
            "count": count_by_bucket[b],
            "recall_avg": _avg(buckets[b]["recall"]),
            "faithfulness_avg": _avg(buckets[b]["faithfulness"]),
        }
        for b in buckets
    }

    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "config": run.config,
        "item_count": len(traces),
        "scores": {
            "recall_avg": _avg(overall["recall"]),
            "faithfulness_avg": _avg(overall["faithfulness"]),
        },
        "by_bucket": by_bucket,
    }
```

**Step 2: get_run 委托 aggregate_run**

`main.py` 里 `GET /runs/{id}` 原来的 N+1 聚合删掉,换成:

```python
from backend.stats import aggregate_run

@app.get("/runs/{run_id}")
def get_run(run_id: int):
    return aggregate_run(run_id)
```

**Step 3: seed 补难样本**

items 从 3 条扩到 5 条:

```python
    items = [
        # 易:常规问法(检索能中,recall 应 1.0)
        DatasetItem(dataset_id=ds.id, input="宝宝发烧38度怎么办",
                    expected_output="物理降温/就医/用药", bucket="护理"),
        DatasetItem(dataset_id=ds.id, input="6个月能加辅食吗",
                    expected_output="满6个月/铁米粉", bucket="喂养"),
        DatasetItem(dataset_id=ds.id, input="宝宝晚上总醒怎么回事",
                    expected_output="出牙/睡眠倒退/环境", bucket="睡眠"),
        # 难:KB 缺口(ground truth 多一个库里没有的点,recall 应 0.75)
        DatasetItem(dataset_id=ds.id, input="宝宝发烧38度怎么办需要观察什么",
                    expected_output="物理降温/就医/用药/观察精神状态", bucket="护理"),
        # 难:口语化问法(关键词检索漏,recall 应 0.0)
        DatasetItem(dataset_id=ds.id, input="娃夜里老闹腾不睡觉咋办",
                    expected_output="出牙/睡眠倒退/环境", bucket="睡眠"),
    ]
```

**Step 4: 测试 test_stats.py**

```python
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace
from backend.stats import aggregate_run


def test_aggregate_by_bucket():
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a/b", bucket="护理")
    i2 = DatasetItem(dataset_id=ds.id, input="q2", expected_output="a/b", bucket="睡眠")
    s.add_all([i1, i2])
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q1", output="o1", retrieved_context="c")
    t2 = Trace(run_id=run.id, dataset_item_id=i2.id, input="q2", output="o2", retrieved_context="c")
    s.add_all([t1, t2])
    s.flush()
    s.add_all([
        Score(trace_id=t1.id, name="recall", value=1.0),
        Score(trace_id=t1.id, name="faithfulness", value=1.0),
        Score(trace_id=t2.id, name="recall", value=0.0),
        Score(trace_id=t2.id, name="faithfulness", value=None),  # judge 挂,不参与均值
    ])
    s.commit()
    rid = run.id
    s.close()

    agg = aggregate_run(rid)
    assert agg["scores"]["recall_avg"] == 0.5
    assert agg["scores"]["faithfulness_avg"] == 1.0  # 只有 1 条非 NULL
    assert agg["by_bucket"]["护理"]["recall_avg"] == 1.0
    assert agg["by_bucket"]["护理"]["count"] == 1
    assert agg["by_bucket"]["睡眠"]["recall_avg"] == 0.0
    assert agg["by_bucket"]["睡眠"]["count"] == 1
```

运行 `uv run pytest` 通过(17 passed)。

**验证(真实 key 端到端):** 5 条样本跑完 → recall 整体 0.75、护理桶 0.875、喂养桶 1.0、睡眠桶 0.5;faithfulness 全 1.0(模型始终忠于证据,证据为空也诚实拒答)。

---

### Task 7: 库外题 + 拒答率(rejection)第三指标

**Files:**
- Modify: `backend/evaluators.py`(加 `rejected()` + `REJECT_MARKERS`)
- Modify: `backend/run_service.py`(`ABSENT_BUCKET` 分支)
- Modify: `backend/seed.py`(补 2 条库外题)
- Modify: `backend/stats.py`(聚合加 rejection)
- Test: `tests/test_evaluators.py`、`tests/test_run_service.py`、`tests/test_stats.py`

**动机:** recall 测「检索召回」、faithfulness 测「生成忠实」,缺「库外该不该答」。加第三指标后形成三层评测:recall / faithfulness / rejection。

**设计决策(要能复述):**
- 拒答检测用机械关键词,不用 LLM judge——确定性、无温度、便宜,与 recall 同哲学(分层:机械的归机械,LLM 的归 LLM)。
- 库外题靠 `bucket="库外"` 标记;run_service 看到该桶只评 rejection,跳过 recall/faithfulness(库外题没有 ground-truth 答案,recall 无意义)。
- rejection 记 0/1(1=正确拒答),聚合即拒答率;只对库外题计算,不污染普通桶。

**Step 1: evaluators.py 加 rejected()**

```python
REJECT_MARKERS = ["不清楚", "不知道", "无法回答", "无法提供", "没有相关", "没有证据", "无法给出"]


def rejected(output: str) -> float:
    """机械判断回答是否为「拒答」。命中任一拒答词 → 1.0,否则 0.0。"""
    return 1.0 if any(m in output for m in REJECT_MARKERS) else 0.0
```

**Step 2: run_service.py 库外分支**

```python
ABSENT_BUCKET = "库外"
...
if it.bucket == ABSENT_BUCKET:
    s.add(Score(trace_id=tr.id, name="rejection", value=rejected(out["output"])))
else:
    # recall + faithfulness(原逻辑不变)
```

**Step 3: seed 补 2 条库外题**(expected_output 为空,只有 bucket="库外")

```python
DatasetItem(dataset_id=ds.id, input="宝宝拉肚子怎么办", expected_output="", bucket="库外"),
DatasetItem(dataset_id=ds.id, input="宝宝长湿疹怎么护理", expected_output="", bucket="库外"),
```

**Step 4: stats.py 聚合加 rejection**(overall + by_bucket 各加 rejection_rate)

**Step 5: 测试**(rejected 命中/未命中、库外分支、rejection 聚合)

运行 `uv run pytest` 通过(21 passed)。

**验证(真实 key 端到端,7 条):** recall 0.75、faithfulness 1.0、rejection_rate 1.0;库外桶单独 rejection_rate=1.0。两条库外题均诚实拒答(「没有可依据的证据,我无法给出建议」),证明 system prompt「证据没有就说不清楚」这条护栏生效。
