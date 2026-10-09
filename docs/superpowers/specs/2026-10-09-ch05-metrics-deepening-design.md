# EvalFlow Ch05 设计:评测指标深化(RAGAS 风格多维指标)

## 目标

Ch04 之后,评测平台能跑真实向量检索,但「打分」还停在 Ch02 的基础三层:`recall`(机械子串匹配)、`faithfulness`(单个 LLM judge)、`rejection`(拒答词)。这套指标离「专业 RAG 评测」还有距离——它答不了面试里最常被追问的三个问题:

1. **检索到底准不准?** 召回的证据里有没有噪声(该丢的没丢)、有没有漏检(该找的没找到)。
2. **回答到底对不对、切不切题?** 不只是「有没有抄证据」,而是「答案与标准答案的语义一致度」「有没有跑题」。
3. **机械匹配和语义判断差在哪?** 什么时候 LLM judge 值得花这个钱/时间,什么时候机械匹配就够了。

Ch05 把指标升级为 **RAGAS 风格的多维指标**,覆盖 RAG 的两个阶段、四个经典维度:

- **检索阶段(Retrieval)**
  - Context Precision(上下文精度)—— 检索到的证据里,真正相关、有用的占比(有没有噪声)。
  - Context Recall(上下文召回)—— 回答问题所需的要点,证据是否都覆盖了(有没有漏检)。
- **生成阶段(Generation)**
  - Faithfulness(忠实度)—— 已有,回答是否忠于证据、不编造。
  - Answer Relevance(答案相关性)—— 回答是否切题、不跑题。
  - Answer Correctness(答案正确性)—— 回答与标准答案的语义一致度(比机械子串强,能识别同义改写)。
- **库外题专用**
  - Rejection(拒答)—— 已有,库外题的正确行为是不答。

验收标准:

1. 库内样本评 **6 个指标**:`recall`(机械基线)+ `context_precision` / `context_recall` / `faithfulness` / `answer_relevance` / `answer_correctness`(5 个 LLM judge)。
2. 库外样本只评 `rejection`(拒答),逻辑不变。
3. 所有 LLM judge 沿用「失败记 NULL、不记 0」的容错约定(judge 挂不算错,聚合时跳过)。
4. 聚合从「硬编码 3 个指标名」改为「按指标注册表遍历」—— 以后加指标只在注册表加一行,不改聚合主体。
5. run 详情页动态渲染指标卡片 + 分桶表(不再硬编码 3 列)。
6. 后端 / 前端测试 + build 全绿。

## 指标定义(为什么是这几个)

RAG 评测业界公认拆成两阶段:先看「检索」抽得好不好,再看「生成」答得好不好。RAGAS(Retrieval Augmented Generation Assessment)把这套拆成五个指标,是当前最主流的 RAG 评测框架,也是大厂 AI 应用面试的高频考点。Ch05 对齐 RAGAS 的五指标,并保留已有的机械基线。

| 指标 | 阶段 | 判法 | 度量的问题 | 输入 |
|---|---|---|---|---|
| recall(机械,已有) | 检索 | 机械子串匹配 | 标准答案要点有多少字面出现在证据里 | expected_output, retrieved_context |
| context_precision | 检索 | LLM judge | 证据里有多少是真正相关、有用的(噪声少) | question, retrieved_context |
| context_recall | 检索 | LLM judge | 回答所需要点,证据是否都覆盖了(漏检少) | question, expected_output, retrieved_context |
| faithfulness | 生成 | LLM judge(已有) | 回答是否忠于证据、不编造 | retrieved_context, output |
| answer_relevance | 生成 | LLM judge | 回答是否切题、不跑题不啰嗦 | question, output |
| answer_correctness | 生成 | LLM judge | 回答与标准答案的语义一致度 | question, expected_output, output |
| rejection(机械,已有) | 库外 | 拒答信号词 | 库外题是否拒答 | output |

**为什么机械 recall 要保留,而不是被 context_recall 取代?** 因为两者是「同一个问题(检索召回)」的两种判法——机械子串快、零成本、确定性,但识别不了同义改写;LLM 语义判断准,但要花钱花时间。保留机械基线,能直观对比「机械 vs 语义」的差距,这本身就是评测平台的价值,也是面试里能讲清楚的故事(什么时候机械够用、什么时候必须上 LLM judge)。

## 技术栈(定死,不可自行更换)

- **LLM judge**:复用 DeepSeek(`llm.chat_json`,JSON mode 强制输出,温度 0),不换模型、不引第三方评测库。
- **后端**:复用 FastAPI + SQLite。`Score` 表本来就通用(`name` + `value` + `comment`),**不需要改表结构**。
- **前端**:复用 antd + recharts;`RunDetailView` 从硬编码 3 指标改为动态渲染。

## 架构与数据流

```
评测 run(每条样本 question)
  pipeline.run_pipeline(question) → {output, retrieved_context, hits}
        │
        ▼
  run_service.execute_run —— 按 bucket 分派指标:
    库外题(bucket="库外")       库内题
      ├ rejection(机械)          ├ recall(机械基线,0 次 LLM)
                                 ├ context_precision(LLM judge)
                                 ├ context_recall(LLM judge)
                                 ├ faithfulness(LLM judge)
                                 ├ answer_relevance(LLM judge)
                                 └ answer_correctness(LLM judge)
        │ 每个指标 → Score(name=指标key, value=0~1, comment=reason/失败原因)
        ▼
  stats.aggregate_run —— 按「指标注册表」动态遍历,不再硬编码 3 个指标名:
    对每个指标:overall 均值 + by_bucket 均值(NULL 跳过)
        │
        ▼
  GET /runs/{id} → scores: {指标key: 均值}(动态 key)+ by_bucket: {bucket: {count, 指标key: 均值}}
        │
        ▼
  前端 RunDetailView 动态渲染:指标卡片遍历 scores,分桶表遍历指标列
```

## 后端改动(Ch05 需要)

1. `backend/prompts.py`:新增 4 个 judge 的 prompt(`CONTEXT_PRECISION_PROMPT` / `CONTEXT_RECALL_PROMPT` / `ANSWER_RELEVANCE_PROMPT` / `ANSWER_CORRECTNESS_PROMPT`),与 `FAITHFULNESS_PROMPT` 同款格式,都要求输出 `{"score": <0~1>, "reason": "<一句话>"}`。
2. `backend/evaluators.py`:新增 4 个 judge 函数,统一封装成「`judge(prompt_key, **fields) → dict | None`」的公共函数,避免 4 份重复的 `try/except + chat_json + 夹逼到 [0,1]` 逻辑(现有 `faithfulness` 也改走这个公共函数)。
3. `backend/stats.py`(或独立注册表):定义指标注册表 `METRIC_ORDER`(指标的展示顺序),`aggregate_run` 改成遍历注册表动态聚合,输出动态 key。
4. `backend/run_service.py`:库内题从「评 recall + faithfulness」扩到「评 6 个指标」;库外题不变。

## 指标注册表(单一事实来源)

指标 key 的**展示顺序**、**中文标签**需要前后端各维护一份映射,但 key 的集合以后端注册表为准:

```python
# backend/metrics.py(新)
METRIC_ORDER = [
    "recall", "context_precision", "context_recall",
    "faithfulness", "answer_relevance", "answer_correctness",
    "rejection",
]
```

前端 `RunDetailView` 维护 `key → 中文标签` 的映射(展示用),后端只认 key。加指标 = 后端注册表加一行 + run_service 加一个 judge 调用 + 前端标签加一行,聚合与渲染代码不改。

## 接口契约变更(前端视角)

### GET /runs/{id}(变更)

`scores` 与 `by_bucket` 从「固定 3 个 key」改为「动态 key」:

```json
{
  "id": 1, "dataset_id": 1, "status": "done", "config": "{}", "item_count": 20,
  "scores": {
    "recall": 0.72,
    "context_precision": 0.81,
    "context_recall": 0.68,
    "faithfulness": 0.95,
    "answer_relevance": 0.88,
    "answer_correctness": 0.76
  },
  "by_bucket": {
    "护理": { "count": 5, "recall": 0.8, "context_precision": 0.9, "context_recall": 0.7, "faithfulness": 0.95, "answer_relevance": 0.9, "answer_correctness": 0.8 },
    "库外": { "count": 3, "recall": null, "context_precision": null, "context_recall": null, "faithfulness": null, "answer_relevance": null, "answer_correctness": null, "rejection": 1.0 }
  }
}
```

- `scores` 里只有**该 run 实际评过**的指标(按注册表顺序),值为均值;某指标全 NULL 则该 key 值为 null(库外题不评 recall 等,所以若整个 run 全是库外题,`scores` 里只有 `rejection`)。
- `by_bucket` 每个分桶带**与 `scores` 相同的指标集合**(保证前端列对齐),值为该桶均值;某桶没评某指标则为 null。
- 旧字段名 `recall_avg` / `faithfulness_avg` / `rejection_rate` **废弃**,改为裸指标名。

### GET /runs/{id}/traces(不变)

逐条 trace 的 `scores: [{name, value}]` 已经是动态的(一个 Score 一行),Ch05 只是让每行的 score 条数变多,接口结构不变。

## 前端改动

- `RunDetailView.tsx`:
  - 指标卡片区从「写死 3 个 MetricCard」改为「遍历 `run.scores`」动态渲染,带 `key → 中文标签` 映射。
  - 分桶表从「写死 3 列」改为「动态列」:第一列分桶名 + count,其余列按指标注册表顺序动态生成(列头用中文标签)。
  - `types.ts` 的 `RunDetail` 类型:`scores` / `by_bucket` 从具体字段改为 `Record<string, number | null>`(动态 key)。
- 指标顺序由后端 `scores` 的 key 顺序保证(后端已按 `METRIC_ORDER` 注册表排序,JSON 保持插入顺序),前端只需一份 `key → 中文标签` 映射,不重复维护 `METRIC_ORDER`。

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 指标框架 | 对齐 RAGAS 五指标 + 保留机械 recall/rejection | 自创指标:RAGAS 是业界标准,面试高频,对齐它有据可依 |
| 机械 recall 去留 | 保留作「机械基线」,与 context_recall(语义)并存 | 删掉它:旧数据孤儿,且失去「机械 vs 语义」对比这一评测价值 |
| judge 实现 | 每个指标单次 LLM 调用,输出 score+reason | RAGAS 原版逐条/多轮:更精确但调用次数翻几倍、成本高,Ch05 先做单次 judge 的 demo 版 |
| judge 复用 | 抽公共 `judge()` 函数,4 个新指标 + faithfulness 都走它 | 各写一份:try/except + chat_json + 夹逼逻辑重复 5 次,必抽 |
| 聚合改造 | 按 `METRIC_ORDER` 注册表动态遍历 | 继续硬编码 3 个 key:每加一个指标要改聚合 + 前端 + 测试多处,违背「指标可扩展」 |
| LLM 调用成本 | 默认全评 6 个指标(每库内样本 5 次 LLM) | 可配置开关:Ch06 多 run 对比时再引入「选哪些指标/换检索配置」,Ch05 先把指标铺全 |
| 指标顺序 | 前端 `key → 中文标签` 映射 + 注册表顺序 | 后端直接返回中文:后端不该管展示文案,key 与标签分离是标准做法 |
| 失败容错 | judge 挂记 NULL,聚合跳过 | 记 0:把「没评上」和「评了 0 分」混淆,均值被拉低,错 |

## 本章不做

- 指标开关 / 配置化(Ch06 多 run 对比时一起做)。
- RAGAS 原版的逐条拆解、多轮 judge、加权(只做单次 judge 的 demo 版)。
- 指标评分结果的置信区间 / 显著性检验(统计学,超出 demo 范围)。
- 评测集一键全量回归 / CI 集成(Ch08 部署后再说)。
