# EvalFlow Ch02 设计:评测主流程(run 生命周期 + recall/faithfulness)

## 目标

Ch02 跑通评测主流程:建评测集 → 发起 run → 逐条跑管线(检索+生成) → 两个 evaluator 打分 → 结果落库可查。这是「评测」二字真正落地的章节,前端仍不做。

验收标准:
1. API 能建评测集(POST /datasets)、加样本(POST /datasets/{id}/items)。
2. POST /runs 发起一次评测,后台串行遍历该评测集所有样本,逐条:检索+生成 → 存 trace → recall/faithfulness 打分 → 存 score,最终 run.status = done;中途异常 run.status = failed。
3. GET /runs/{id} 返回聚合分数(recall/faithfulness 均值 + 按 bucket 分桶均值),GET /runs/{id}/traces 返回逐条明细(input/output/scores)。
4. recall 用机械匹配(不碰 LLM);faithfulness 用 LLM judge(温度 0);judge 挂→该条 score=NULL(不记 0),不阻塞整轮。
5. 库外题(bucket="库外")只评「拒答」rejection(机械关键词,1=正确拒答),聚合返回拒答率。

## 技术栈(定死,不可自行更换)

- 复用 Ch01:Python 3.12 + FastAPI + SQLAlchemy + SQLite + uv + pytest。
- 新增:`openai` 包(OpenAI 兼容客户端,生成 + judge 都走它)。
- 后台执行:FastAPI BackgroundTasks,串行跑(不并发写 SQLite 单文件)。
- 检索:Ch02 用「内存知识库 + 子串/关键词匹配」的最小实现,真实向量检索后置(Ch03/Ch04)。
- 密钥:从 .env 读 CHAT_MODEL / CHAT_BASE_URL / CHAT_API_KEY。本章需要真实 key(生成 + judge 各一次 LLM 调用),执行时由用户提供,不写进仓库、不写进文档。

## 架构与数据流

```
POST /runs {dataset_id, config}
   └─ 建 run(status=running)
        └─ BackgroundTasks 串行遍历 dataset_items:
             对每条 item:
               retrieve(query) ──────────────► 证据 context
               generate(query, context) ─────► 回答 output
               存 trace(input/output/context/latency)
               recall(context vs expected_output)   ── 机械匹配 ──► score
               faithfulness(output vs context)      ── LLM judge ─► score
             全部完成 ─► run.status=done
             中途异常 ─► run.status=failed
读:GET /runs/{id} 聚合 / GET /runs/{id}/traces 明细
```

run_pipeline 签名不变(Ch01 定的 `{output, retrieved_context}`),只是内部从 mock 换成「真检索 + 真生成」——第 2 章只换实现不换调用方。

## 目录结构(新增/改动)

```
backend/
  main.py          # 升级:评测集 CRUD + run 发起 + 结果查询
  config.py        # 复用
  db.py            # 复用
  models.py        # 复用(六张表)
  pipeline.py      # 升级:retrieve + generate(真实 LLM)
  retriever.py     # 新增:内存知识库 + 子串匹配
  knowledge.py     # 新增:几条育儿知识(检索源)
  llm.py           # 新增:OpenAI 兼容客户端(chat + 结构化输出)
  prompts.py       # 新增:faithfulness judge prompt
  evaluators.py    # 新增:recall(机械) + faithfulness(judge)
  run_service.py   # 新增:run 生命周期(遍历+打分+落库+状态流转)
  stats.py         # 新增:run 分数聚合(整体 + 按 bucket 分桶)
  seed.py          # 升级:知识库 + 样本(含难样本,让分数拉开差距)
tests/
  test_evaluators.py   # recall 确定性 / faithfulness 失败注入
  test_run_service.py  # 状态机(mock 管线跑通)
  test_api.py          # CRUD + run 发起/查询
```

## 数据模型

复用 Ch01 六张表,不新增。字段用法:
- runs.status:Ch01 定义的状态机 running/done/failed,Ch02 真正流转。
- runs.config:存本轮快照(model 名 / prompt 版本 / 温度),对比「改提示词前后」用。
- traces.retrieved_context:存检索证据,faithfulness 的输入。
- scores.name ∈ {recall, faithfulness, rejection};value 可空(judge 挂记 NULL)。

## evaluator 设计(核心)

### recall(机械匹配,不碰 LLM)
- 定义:ground truth 要点命中率 = 命中要点数 / 总要点数。
- expected_output 按 `/` 切分成要点,逐点判断「要点子串是否出现在 retrieved_context」。
- 确定性、可复现、无温度。上游 LLM 挂了也能跑。

### faithfulness(LLM-as-Judge)
- 定义:回答是否被检索证据支撑,0~1 分 + 理由。
- 输入:output + retrieved_context;输出结构化 {score: float, reason: str}。
- 温度固定 0(评分不能有温度,同证据重放不能跳分)。
- 失败处理:异常/超时→该条记 NULL(scores.value 可空),不记 0,继续下一条,不阻塞 run。

### rejection(机械拒答检测,库外题专用)
- 定义:库外题(bucket="库外")的正确行为是拒答;检测 output 是否含拒答信号词(不清楚/无法回答/没有相关等)。
- 确定性、不碰 LLM(与 recall 同哲学)。
- 只对库外题评 rejection(跳过 recall/faithfulness);记 0/1,聚合为拒答率。

## 接口契约

### POST /datasets
请求 `{name, description}` → 响应 `{id, name, description, created_at}`

### POST /datasets/{id}/items
请求 `{input, expected_output, bucket}` → 响应 item 对象

### GET /datasets
响应 `[{id, name, description, item_count}]`

### POST /runs
请求 `{dataset_id, config?}` → 立即返回 `{id, status: "running"}`,后台跑

### GET /runs/{id}
响应 `{id, dataset_id, status, config, item_count, scores: {recall_avg, faithfulness_avg, rejection_rate}, by_bucket: {bucket: {count, recall_avg, faithfulness_avg, rejection_rate}}}`

### GET /runs/{id}/traces
响应 `[{trace_id, input, output, retrieved_context, latency_ms, scores: [{name, value}]}]`

### GET /health(复用)

## run 生命周期(状态机)

```
POST /runs ─► running ─► done(全部完成)
                 └────► failed(遍历/写库异常)
```
- 单条 judge 挂:该条 score 记 NULL,继续下一条(不算 run 失败)。
- run 级异常(如遍历时数据库炸):status=failed,已完成的 trace 保留。

## 测试与验证

TDD(pytest):
- recall:机械匹配单元测试(给定 context 和 expected_output,断言命中率)。
- faithfulness:失败注入(mock judge 抛异常 → 该条 score=None);真实集成测试需 key(默认 skip,或手动用真实 key 跑)。
- run 生命周期:用 mock 管线(不调真实 LLM)跑通 running→done,以及异常→failed。
- API:建评测集/加样本/发起 run/查结果。

## 本章不做

- 前端(Ch03)
- 真实向量检索 / embedding(Ch03/Ch04,Ch02 用子串匹配最小检索)
- Ragas 那批指标(只做 recall + faithfulness 两个)
- 并发 run / 任务队列(Ch04)
- 分桶可视化的前端报表(后端分桶聚合已做,前端展示 Ch03)
- --skip-gen 分层跳过 / 失败重试

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 检索 | 内存知识库 + 子串匹配 | 真实向量检索:Ch02 重点是「跑通评测流程」,检索先用最小实现,别把 Ch02 变成 RAG 章节 |
| 生成 | 真实 LLM(OpenAI 兼容) | 继续 mock:faithfulness 就没真东西可评;生成走真实 LLM,评测才真实 |
| recall | 机械匹配,不碰 LLM | LLM judge:检索段要确定性可复现,分层解耦(对齐 MewHelp) |
| faithfulness | LLM judge,温度 0 | 温度 0.3:评分不能有温度,同证据重放不能跳分 |
| judge 失败 | 记 NULL 不记 0 | 记 0.0:失败样本污染分数,「没评上」≠「零分」 |
| run 执行 | BackgroundTasks 串行 | 并发:SQLite 单文件别并发写;demo 规模串行够用 |
| 密钥 | .env 读,不进仓库 | 硬编码:密钥泄露;执行时用户提供 |
| 分桶聚合 | 后端 GET /runs/{id} 返回 by_bucket(每桶 count + 两指标均值) | 前端自己算:聚合放后端,前端只展示;judge 挂(NULL)不参与均值 |
| 难样本 | seed 补 KB 缺口题 + 口语检索漏题 + 库外题 | 全简单题:分数清一色 1.0,看不出平台抓问题的能力 |
| 拒答检测 | 机械关键词(rejection),不碰 LLM | LLM judge:库外题少,机械更便宜且确定性;与 recall 同哲学分层 |
