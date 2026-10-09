# EvalFlow Ch05 评测指标深化 Implementation Plan

> **For agentic workers:** 按 task 顺序逐个执行。步骤用 checkbox（`- [ ]`）追踪。每个 task 完成即验证通过；提交由用户指示（不自动 commit）。

**Goal:** 把基础三层指标升级为 RAGAS 风格多维指标：库内样本评 6 个指标（recall 机械基线 + 5 个 LLM judge），聚合从硬编码改为按注册表动态遍历，前端动态渲染。

**Architecture:** 后端 `evaluators.py` 抽公共 `_judge()` 复用 LLM judge；`metrics.py` 定义指标注册表 `METRIC_ORDER`；`stats.py` 按注册表动态聚合；`run_service.py` 库内题评 6 指标；前端 `RunDetailView` 动态渲染指标卡片 + 分桶列。

**Tech Stack:** 复用 DeepSeek（`llm.chat_json` JSON mode）+ FastAPI + SQLite + antd/recharts。`Score` 表已通用，不改表。

**Spec:** `docs/superpowers/specs/2026-10-09-ch05-metrics-deepening-design.md`

## Global Constraints

- 指标对齐 RAGAS 五指标 + 保留机械 recall/rejection；不做指标开关（Ch06）。
- LLM judge 沿用「失败记 NULL、不记 0」；聚合跳过 NULL。
- 每个指标单次 LLM 调用（不做 RAGAS 原版的逐条/多轮）。
- 指标 key 与中文标签分离：后端只认 key，前端维护标签映射。
- 每个 task 完成即验证通过；是否提交由用户指示。

---

### Task 1: 新增 4 个 judge 的 prompt + 抽公共 `_judge()`

**Files:**
- Modify: `backend/prompts.py`（4 个新 prompt）
- Modify: `backend/evaluators.py`（抽 `_judge()` + 4 个新 judge 函数 + `faithfulness` 改走 `_judge`）

- [ ] **Step 1: prompts.py 加 4 个 prompt（与 FAITHFULNESS_PROMPT 同款格式）**

```python
CONTEXT_PRECISION_PROMPT = """你是 RAG 评测裁判,判断「证据」里有多少是真正相关、有助于回答问题的(噪声越少、精度越高)。

问题:
{question}

证据:
{context}

只输出 JSON,格式:{{"score": <0到1的浮点数,表示相关有用的证据占比>, "reason": "<一句话理由>"}}"""

CONTEXT_RECALL_PROMPT = """你是 RAG 评测裁判,判断「证据」是否覆盖了回答问题所需的全部要点(漏检越少、召回越高)。

问题:
{question}

标准答案要点:
{expected}

证据:
{context}

只输出 JSON,格式:{{"score": <0到1的浮点数,表示要点被证据覆盖的比例>, "reason": "<一句话理由>"}}"""

ANSWER_RELEVANCE_PROMPT = """你是 RAG 评测裁判,判断「回答」是否切题:是否直接回应了问题,有没有跑题、啰嗦、答非所问。

问题:
{question}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""

ANSWER_CORRECTNESS_PROMPT = """你是 RAG 评测裁判,判断「回答」与「标准答案要点」的语义一致程度(同义表达也算对,不要求逐字)。

问题:
{question}

标准答案要点:
{expected}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""
```

- [ ] **Step 2: evaluators.py 抽 `_judge()` + 4 个新 judge**

```python
from backend import llm
from backend.prompts import (
    ANSWER_CORRECTNESS_PROMPT,
    ANSWER_RELEVANCE_PROMPT,
    CONTEXT_PRECISION_PROMPT,
    CONTEXT_RECALL_PROMPT,
    FAITHFULNESS_PROMPT,
)

# 拒答信号词:命中任一即判定为「拒答」(库外题的正确行为)
REJECT_MARKERS = ["不清楚", "不知道", "无法回答", "无法提供", "没有相关", "没有证据", "无法给出"]


def rejected(output: str) -> float:
    """机械判断回答是否为「拒答」。命中任一拒答词 → 1.0,否则 0.0(确定性,不碰 LLM)。"""
    return 1.0 if any(m in output for m in REJECT_MARKERS) else 0.0


def recall(expected_output: str, retrieved_context: str) -> float:
    """机械匹配:ground truth 要点命中率。expected_output 用 / 切要点,判断子串是否出现在 context。"""
    points = [p.strip() for p in expected_output.split("/") if p.strip()]
    if not points:
        return 0.0
    hits = sum(1 for p in points if p in retrieved_context)
    return round(hits / len(points), 4)


def _judge(prompt: str) -> dict | None:
    """LLM judge 公共函数:chat_json 打分 + 夹逼到 [0,1]。失败返回 None(记 NULL 不记 0)。"""
    try:
        raw = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.0)
        if raw is None or "score" not in raw:
            return None
        score = min(max(float(raw["score"]), 0.0), 1.0)
        return {"score": round(score, 4), "reason": str(raw.get("reason", ""))}
    except Exception:
        return None


def faithfulness(output: str, retrieved_context: str) -> dict | None:
    """生成阶段:回答是否忠于证据、不编造。"""
    return _judge(FAITHFULNESS_PROMPT.format(context=retrieved_context, answer=output))


def context_precision(question: str, retrieved_context: str) -> dict | None:
    """检索阶段:证据里相关有用的占比(噪声少)。"""
    return _judge(CONTEXT_PRECISION_PROMPT.format(question=question, context=retrieved_context))


def context_recall(question: str, expected_output: str, retrieved_context: str) -> dict | None:
    """检索阶段:标准答案要点被证据覆盖的比例(漏检少)。"""
    return _judge(CONTEXT_RECALL_PROMPT.format(question=question, expected=expected_output, context=retrieved_context))


def answer_relevance(question: str, output: str) -> dict | None:
    """生成阶段:回答是否切题、不跑题。"""
    return _judge(ANSWER_RELEVANCE_PROMPT.format(question=question, answer=output))


def answer_correctness(question: str, expected_output: str, output: str) -> dict | None:
    """生成阶段:回答与标准答案要点的语义一致度。"""
    return _judge(ANSWER_CORRECTNESS_PROMPT.format(question=question, expected=expected_output, answer=output))
```

验证:`uv run pytest tests/test_evaluators.py` 通过（faithfulness 签名不变，旧测试仍绿）。

---

### Task 2: 指标注册表 + 聚合动态化

**Files:**
- Create: `backend/metrics.py`（`METRIC_ORDER`）
- Modify: `backend/stats.py`（`aggregate_run` 按注册表动态遍历）

- [ ] **Step 1: metrics.py 注册表**

```python
# 指标注册表:指标 key 的展示顺序(检索 → 生成 → 库外)。
# 加指标 = 这里加一行 + run_service 加一个 judge 调用 + 前端标签映射加一行。
METRIC_ORDER = [
    "recall",
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevance",
    "answer_correctness",
    "rejection",
]
```

- [ ] **Step 2: stats.py 动态聚合（不再硬编码指标名）**

```python
from collections import defaultdict

from backend.db import SessionLocal
from backend.metrics import METRIC_ORDER
from backend.models import DatasetItem, Run, Score, Trace


def _avg(vals):
    return round(sum(vals) / len(vals), 4) if vals else None


def aggregate_run(run_id: int) -> dict:
    """聚合一次 run 的分数:按指标注册表动态遍历(不再硬编码指标名)。judge 挂(NULL)不参与均值。"""
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

    # 动态收集「实际评过」的指标名,按注册表顺序排;注册表外的兜底排最后(未知指标不丢)
    present = {name for tr in traces for name in score_by_trace.get(tr.id, {})}
    ordered = [m for m in METRIC_ORDER if m in present] + [m for m in present if m not in METRIC_ORDER]

    overall = {m: [] for m in ordered}
    buckets = defaultdict(lambda: {m: [] for m in ordered})
    count_by_bucket = defaultdict(int)
    for tr in traces:
        b = bucket_by_item.get(tr.dataset_item_id, "未分桶")
        count_by_bucket[b] += 1
        for m in ordered:
            v = score_by_trace.get(tr.id, {}).get(m)
            if v is not None:
                overall[m].append(v)
                buckets[b][m].append(v)

    by_bucket = {
        b: {"count": count_by_bucket[b], **{m: _avg(buckets[b][m]) for m in ordered}}
        for b in buckets
    }

    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "config": run.config,
        "item_count": len(traces),
        "scores": {m: _avg(overall[m]) for m in ordered},
        "by_bucket": by_bucket,
    }
```

验证:`uv run pytest tests/test_stats.py`（需先更新测试，见 Task 4）。

---

### Task 3: run_service 库内题评 6 指标

**Files:**
- Modify: `backend/run_service.py`

- [ ] **Step 1: 库内题从 2 指标扩到 6 指标（库外题不变）**

```python
import json
import time

from backend.db import SessionLocal
from backend.evaluators import (
    answer_correctness,
    answer_relevance,
    context_precision,
    context_recall,
    faithfulness,
    recall,
    rejected,
)
from backend.models import DatasetItem, Run, Score, Trace
from backend.pipeline import run_pipeline

ABSENT_BUCKET = "库外"  # 库外题:知识库里没有答案,正确行为是拒答


def execute_run(run_id: int) -> None:
    s = SessionLocal()
    run = s.get(Run, run_id)
    items = s.query(DatasetItem).filter(DatasetItem.dataset_id == run.dataset_id).all()
    try:
        for it in items:
            t0 = time.time()
            out = run_pipeline(it.input)
            latency_ms = int((time.time() - t0) * 1000)
            hits = [{"text": h["text"], "score": h["score"], "rank": i + 1}
                    for i, h in enumerate(out["hits"])]
            tr = Trace(run_id=run.id, dataset_item_id=it.id,
                       input=it.input, output=out["output"],
                       retrieved_context=out["retrieved_context"],
                       retrieval_hits=json.dumps(hits, ensure_ascii=False),
                       latency_ms=latency_ms)
            s.add(tr)
            s.flush()
            if it.bucket == ABSENT_BUCKET:
                # 库外题:只评「拒答」(正确行为是不答)
                s.add(Score(trace_id=tr.id, name="rejection", value=rejected(out["output"])))
            else:
                # recall 机械基线(确定性,0 次 LLM)
                s.add(Score(trace_id=tr.id, name="recall",
                            value=recall(it.expected_output, out["retrieved_context"])))
                # 5 个 LLM judge:统一「judge 挂记 NULL 不记 0」
                judges = [
                    ("context_precision", context_precision(it.input, out["retrieved_context"])),
                    ("context_recall", context_recall(it.input, it.expected_output, out["retrieved_context"])),
                    ("faithfulness", faithfulness(out["output"], out["retrieved_context"])),
                    ("answer_relevance", answer_relevance(it.input, out["output"])),
                    ("answer_correctness", answer_correctness(it.input, it.expected_output, out["output"])),
                ]
                for name, r in judges:
                    if r is None:
                        s.add(Score(trace_id=tr.id, name=name, value=None, comment="judge 失败"))
                    else:
                        s.add(Score(trace_id=tr.id, name=name, value=r["score"], comment=r["reason"]))
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

验证:`uv run pytest tests/test_run_service.py`（需先更新测试，见 Task 4）。

---

### Task 4: 后端测试更新

**Files:**
- Modify: `tests/test_evaluators.py`（`_judge` + 4 个新 judge + 失败返回 None）
- Modify: `tests/test_stats.py`（动态聚合多指标）
- Modify: `tests/test_run_service.py`（库内 6 指标 / 库外 1 指标）

- [ ] **Step 1: test_evaluators.py 补 judge 测试**

```python
def _judge_ok(raw):
    # mock llm.chat_json 返回固定 dict
    def f(messages, temperature=0.0):
        return raw
    return f


def test_faithfulness_judge(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", _judge_ok({"score": 0.9, "reason": "ok"}))
    r = evaluators.faithfulness("答", "证")
    assert r == {"score": 0.9, "reason": "ok"}


def test_judge_clamps_score(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", _judge_ok({"score": 2.0, "reason": "x"}))
    assert evaluators.answer_relevance("q", "a")["score"] == 1.0


def test_judge_returns_none_on_parse_fail(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **k: None)
    assert evaluators.context_precision("q", "c") is None


def test_judge_returns_none_on_exception(monkeypatch):
    def _boom(*a, **k):
        raise Exception("timeout")
    monkeypatch.setattr(evaluators.llm, "chat_json", _boom)
    assert evaluators.context_recall("q", "e", "c") is None


def test_all_five_judges(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", _judge_ok({"score": 0.5, "reason": "ok"}))
    assert evaluators.faithfulness("a", "c")["score"] == 0.5
    assert evaluators.context_precision("q", "c")["score"] == 0.5
    assert evaluators.context_recall("q", "e", "c")["score"] == 0.5
    assert evaluators.answer_relevance("q", "a")["score"] == 0.5
    assert evaluators.answer_correctness("q", "e", "a")["score"] == 0.5
```

- [ ] **Step 2: test_stats.py 动态聚合**

```python
# 造一个 run:1 条库内题(评 recall/faithfulness/context_precision) + 1 条库外题(评 rejection)
# 断言:scores 含 recall/faithfulness/context_precision/rejection(按注册表顺序),库外桶 rejection=1.0、其余为 None
```

- [ ] **Step 3: test_run_service.py 6 指标**

```python
# mock run_pipeline + 5 个 judge(monkeypatch evaluators 里的函数),断言库内题产生 6 个 Score、库外题产生 1 个 rejection
```

验证:`uv run pytest` 全绿。

---

### Task 5: 前端动态渲染指标

**Files:**
- Modify: `frontend/src/types.ts`（`RunDetail.scores` / `by_bucket` 改动态 key）
- Modify: `frontend/src/views/RunDetailView.tsx`（指标卡片 + 分桶表动态列）

- [ ] **Step 1: types.ts 改动态 key**

```ts
export interface RunDetail {
  id: number; dataset_id: number; status: string; config: string; item_count: number
  scores: Record<string, number | null>                          // 指标 key → 均值(动态)
  by_bucket: Record<string, Record<string, number | null> & { count: number }>
}
```

- [ ] **Step 2: RunDetailView 动态渲染**

```tsx
// 指标 key → 中文标签(后端只认 key,展示文案放前端)
const METRIC_LABELS: Record<string, string> = {
  recall: "召回(机械)",
  context_precision: "上下文精度",
  context_recall: "上下文召回",
  faithfulness: "忠实度",
  answer_relevance: "答案相关性",
  answer_correctness: "答案正确性",
  rejection: "拒答率",
};

// 指标卡片:遍历 run.scores
<div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
  {Object.entries(run.scores).map(([k, v]) => (
    <MetricCard key={k} label={METRIC_LABELS[k] ?? k} value={v} />
  ))}
</div>

// 分桶表:动态列(分桶 + count + 各指标列)
const metricKeys = Object.keys(run.scores);
const bucketColumns = [
  { title: "分桶", dataIndex: "name" },
  { title: "样本数", dataIndex: "count" },
  ...metricKeys.map((k) => ({
    title: METRIC_LABELS[k] ?? k,
    dataIndex: k,
    render: fmt,
  })),
];
```

验证:`npm run build` 通过。

---

### Task 6: 前端测试更新

**Files:**
- Modify: `frontend/src/views/__tests__/RunDetailView.test.tsx`

- [ ] **Step 1: mock 多指标 scores,断言动态渲染**

```tsx
// getRun mock 返回 6 个指标的 scores,断言「上下文精度」「答案正确性」等标签渲染出来
// 分桶表断言动态列头存在
```

验证:`npm test` 全绿 + `npm run build` 通过。

---

### 验收(端到端)

1. 后端:`cd /Users/lidong/Desktop/workFile/evalflow && uv run pytest` 全绿。
2. 前端:`cd frontend && npm test && npm run build` 全绿。
3. 后端起后,对一个含「库内 + 库外」样本的评测集发起 run,详情页看到 6 个指标卡片 + 动态分桶列,库外桶只有「拒答率」有值。
