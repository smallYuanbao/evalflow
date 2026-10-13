# EvalFlow Ch26 设计:评测真实 RAG 应用(baby-ai)+ 可复现性闭环

## 定位

把 EvalFlow 的「被测系统」从**自己的 toy pipeline** 换成**真实的 RAG 应用 baby-ai**,形成
「开发 → 评测 → 优化 → 再评测」的闭环。

**只做演示版,但带上可复现性**——这是本章和「随便接一下」的分界线(见「决策 3」)。

## 为什么要做

EvalFlow 现在评的是自己那套 23 条 chunk 的玩具管道——「自己评自己」,离真实差一口气。接上 baby-ai 之后:

- EvalFlow 从「教学 demo」升级成「**真在 dogfooding 的评测平台**」;
- 面试叙事立住:「我做了 RAG 应用(baby-ai),又做了评测平台(EvalFlow),然后**用它量化我自己 RAG 应用的每次改动**」。

域也天然匹配:两边都是育儿。

## 现状(接口已对上,这是可行性基础)

baby-ai 的 `POST /api/chat` 返回:

```python
ChatResponse(answer=..., references=[{id, text}, ...])
```

| EvalFlow 需要 | baby-ai 提供 | |
|---|---|---|
| `output` | `answer` | ✅ |
| `retrieved_context` / `hits` | `references[].text`(有序) | ✅ |
| 鉴权 | **宽松模式**,不带 token 即匿名用户 | ✅ 直接可调 |

`hit@k`/`MRR` 只用 text + 顺序,不需要分数 ✅(`retrieval_hits` 的 score 填占位值)。

**但 `/api/health` 只返回 `{status, uptime, timestamp}`——没有任何配置信息。**

## 决策

### 决策 1:baby-ai 加一个 `GET /api/meta` 暴露自身状态

**这是跨仓库的改动,理由必须站得住。**

可复现性的另一半在**对方系统**里。EvalFlow 现在的快照只记自己这边的(知识库版本 / prompt 版本 / 模型),串上 baby-ai 后**真正在变的是 baby-ai 那边**:

| 变的东西 | EvalFlow 能记到吗 |
|---|---|
| baby-ai 的检索参数(`VECTOR_SEARCH_TOP_K` / `RERANK_TOP_K`) | ❌ |
| 查询改写开关(`QUERY_REWRITE_ENABLED`) | ❌ |
| 知识库(chroma `rag_docs` 集合内容) | ❌ |
| 代码版本(git commit) | ❌ |
| 用的模型 / 嵌入模型 | ❌ |

**记不到这些,「这次比上次好」就不成立**——可能是你改了检索,也可能是知识库被更新了、模型被供应商升级了。

所以 baby-ai 暴露一个只读的 meta 接口:

```json
{
  "service": "baby-ai",
  "commit": "abc1234",
  "model": "deepseek-chat",
  "embed_model": "bge-m3",
  "collection": "rag_docs",
  "collection_count": 123,
  "vector_top_k": 10,
  "rerank_top_k": 4,
  "query_rewrite": true
}
```

**理由**:这是「让对方系统可被观测」的最小代价做法(~20 行);比 EvalFlow 去读对方文件系统可靠得多(那是脆弱的隐式耦合)。**接口是显式的契约**。

### 决策 2:EvalFlow 用 `EVAL_TARGET` 切换被测系统

沿用已有的 `E2E_MOCK` 模式:

```
EVAL_TARGET=local   (默认)  → 本地 toy pipeline,行为不变
EVAL_TARGET=babyai          → HTTP 调 baby-ai 的 /api/chat
```

`run_service` / `pipeline` 按 target 分发;`BABYAI_BASE_URL` 可配。

**理由**:不破坏现有行为和全部测试;切换是显式配置,不靠改代码。

### 决策 3:快照加 `external` 段;**拿不到就显式标记「未知」**

`Run.config` 增加:

```json
"external": {
  "target": "babyai",
  "base_url": "http://localhost:3001",
  "meta": { ...决策 1 的 meta... },
  "meta_error": null
}
```

**关键**:如果 meta 接口调不通,`meta` 为 `null` 且 `meta_error` 写明原因——**绝不用空值假装「已知」**。

Run 详情页的「复现上下文」加一块「被测系统」,展示这些字段;`meta_error` 非空时显示醒目提示。

**理由**:可复现性的价值在于「**知道自己知道什么、不知道什么**」。静默记空 = 假装可复现,比不做更危险——因为它会让人**误信**「这次比上次好」。

### 决策 4:评测集适配 baby-ai 的知识库

EvalFlow 现在的期望要点对齐的是自己那 23 条 chunk,baby-ai 的知识库是它自己的 `rag_docs`。

新建一个小评测集(5~7 条),期望要点**按 baby-ai 的实际答案写**,覆盖:
- 库内题(有证据,评 recall + judge)
- 库外题(评拒答)

**理由**:期望要点是 recall/hit@k 的基准,必须对齐被测系统的知识来源,否则测的是「知识库差异」不是「回答质量」。

**样本数控制在 7 条以内**:baby-ai 的 `/api/chat` 有 `@limiter.limit("10/minute")`,演示版直接绕开它(完整版必须解,见「本章不做」)。

### 决策 5:会话隔离

每次调用传**全新的 `session_id`**、`history=None`,避免题与题之间通过多轮记忆互相污染。

## 前提(环境编排)

baby-ai 的 `.env` 里 `CHROMA_URL=http://127.0.0.1:8000`,但 **8000 现在是 EvalFlow 后端**(之前为腾端口停掉了那台 chroma 容器)。要串起来必须先把端口排开,例如 Chroma 挪到 8001。

**这是本章的第一个动作**,不是可选项。

## 验收

- [x] baby-ai 的 `/api/meta` 返回自身状态。
- [x] `EVAL_TARGET=babyai` 时,run 的 `output`/`retrieved_context` 来自 baby-ai。
- [x] run 快照含 `external`,详情页能看到被测系统的版本与配置。
- [x] meta 拿不到时,快照显式标记 `meta_error`(不静默记空)。
- [x] 现有 87 后端 / 33 前端测试全绿(默认 target=local 行为不变)。

## 本章不做(完整版才需要的)

| 项 | 为什么不做 |
|---|---|
| 解 `/api/chat` 的 10/min 限流 | 演示版样本少可绕开;要解需改 baby-ai 或加节流 |
| CI 自动触发评测 + 门禁挡合并 | 同 Ch14 的 eval-on-push,是另一块工程 |
| 门禁阈值校准 | baby-ai 的分数分布 ≠ toy pipeline,要重新标定 |
| 评测集持续维护 / 覆盖场景分布 | 演示版一次性即可 |
| 多轮对话记忆的评测 | 现在是单轮问答;多轮要另一套样本设计 |

## 实跑结果(Run 6)

5 条样本(3 库内 + 2 库外),`EVAL_TARGET=babyai`,花 0.041 元:

| 指标 | 值 | 解读 |
|---|---|---|
| recall / hit@k / mrr | 0.78 / 1.0 / 0.51 | 检索能命中,但相关文档排位不够靠前 |
| context_precision / recall | 0.35 / 0.5 | 检索质量中等 |
| **faithfulness** | **0.1** | **baby-ai 大量靠通用知识作答,没忠于检索到的证据** |
| rejection | **0.0** | **两条库外题都没被判为「正确拒答」**——见下 |

**faithfulness 低是真信号**:逐条看,trace 里 baby-ai 自己都写着「以下回答基于我的通用医学知识」「我目前的知识库中没有相关信息」——**检索到了证据却没用它**。这正是 RAG 评测该抓的问题。

**rejection 0.0 暴露的是 EvalFlow 自己的缺陷**:baby-ai 其实**正确地拒绝了**库外题(「抱歉,我只能回答育儿相关问题哦」「不在我的专业范围内」),但 EvalFlow 的 `rejected()` 只认「不清楚/不知道/无法回答/没有相关/没有证据」这几个词,**匹配不上 baby-ai 的措辞**,于是判成「没拒答」。

> 也就是说:**这次评测既发现了被测系统的问题,也发现了评测平台自己的问题**(拒答词表不全)。
> 这是「评测平台也需要被校准」的活例子,也是接真实系统才能暴露的东西——评自己的 toy pipeline 永远遇不到。

**注意样本量**:5 条只够验证链路,不足以支撑质量结论。

## 「改动 → 再评测」实跑(Ch26 收尾)

**本意**:改 baby-ai 的一个配置(`QUERY_REWRITE_ENABLED` 开→关),再评一次,比指标。

**实际**:第二次评测**直接失败**了(`Run 7 failed`)。日志指向 baby-ai 的 `retriever.py:144`
`IndexError: list index out of range`。

### 查出来的东西:不是配置的锅

一系列对照实验:

| 实验 | 结果 |
|---|---|
| 关改写 + 重启后**单个**请求 | ✅ 200 |
| 关改写 + 重启后**立即并发 2 个** | ❌ 两个都 500 |
| **开**改写 + 重启后**立即并发 2 个** | ❌ **两个都 500** ← 关键对照 |

**结论**:跟 `QUERY_REWRITE_ENABLED` **无关**——是 baby-ai 里一个**早就存在的并发 bug**:

```python
# 修复前
def _init_bm25():
    _bm25_docs = []; _bm25_ids = []; _bm25_metadata = []   # ← 无锁重建
    ...
```

BM25 是**懒加载**(首次检索时初始化,要几秒:jieba 分词 + 遍历 3650 条文档)。多个请求同时进来时,
都看到 `_bm25_model is None`,于是**各自跑一遍初始化**——一个线程正在重建 `_bm25_ids`,
另一个已经在用它索引 → 越界。

**Run 6 只是运气好**没撞上。手工单点试用永远不会暴露这个 bug。

**修法**(baby-ai 分支 `feat/eval-meta-endpoint`):给懒加载加锁 + 入口二次检查,
重建过程持锁,已初始化则直接返回。

修复后验证:重启后立即并发 2 个 → 两个都 200,0 次 IndexError。

> **这就是「评测平台」最有说服力的产出**:它的**并发评测**把被测系统一个潜伏已久的
> 并发 bug 逼了出来,而这个 bug 在人工试用时不可见。

### 指标对比(Run 6 改写开 vs Run 8 改写关,各 5 样本)

| 指标 | 改写开 | 改写关 | Δ |
|---|---|---|---|
| context_precision | 0.35 | 0.45 | +0.10 |
| context_recall | 0.50 | 0.39 | −0.11 |
| faithfulness | 0.10 | 0.00 | −0.10 |
| answer_relevance | 0.70 | 0.80 | +0.10 |
| answer_correctness | 0.70 | 0.80 | +0.10 |

快照并排:**代码版本都是 `4e2e391`(没变),`query_rewrite` 从 true 变 false**。

**这是「为什么 meta 必须记」的最好例证**:如果只记 EvalFlow 自己那半边,两次 run 的快照看起来
一模一样,指标却有差异——**说不清为什么**。有了 meta,能直接指出「唯一的变量是这个开关」。

**诚实声明**:5 个样本上 ±0.1 的差异**基本是噪声**,不足以支撑「关掉改写更好/更差」的结论。
这里验证的是**「链路能捕捉并解释变化」**,不是质量结论。要下结论得扩样本 + 看统计显著性。
