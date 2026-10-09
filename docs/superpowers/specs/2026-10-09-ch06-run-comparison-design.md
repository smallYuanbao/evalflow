# EvalFlow Ch06 设计:多 run 对比评测

## 目标

Ch05 把指标升级到 6 个,但每次只能看**单个 run 的绝对分数**。评测平台真正有价值的场景是「对比」:同一评测集,只改一个变量(检索命中数 top_k、温度、提示词、知识库),看 6 个指标怎么变,从而判断哪种配置更好。

Ch06 打通「可配置 + 对比」:

1. 发起评测时能配置变量(先做 `top_k`,即检索命中数)。
2. run 保存配置快照(`config` JSON),执行时**真正生效**。
3. 新增对比页:选多个 run,并排对比各指标。

验收标准:

1. 发起评测时可指定 `top_k`,run 真正按该 `top_k` 检索(不同 top_k 的 run 检索命中数不同)。
2. run 的 `config` 存 JSON 快照,列表/详情能回看「这次用了什么配置」。
3. 对比页:选 2+ 个 run,展示各指标横向对比表 + 分组柱状图。
4. 后端 / 前端测试 + build 全绿。

## 配置注入链路

```
POST /runs  {dataset_id, config: {top_k: 5}}
   │
   ▼
Run.config = '{"top_k": 5}'（配置快照,可回看、可复现）
   │
   ▼
execute_run 读 config → run_pipeline(question, top_k)
   │
   ▼
retriever.retrieve(query, top_k=top_k)（top_k 真正生效）
```

现状:`run_pipeline(question)` 与 `retriever.retrieve(query, top_k=2)` 都把 top_k 写死了。Ch06 要把它变成「从 config 流下来」的可配置参数。

## 后端改动

1. `backend/retriever.py`:`retrieve(query, top_k=...)` 的 top_k 已有默认值,无需改签名,只需调用方传入。
2. `backend/pipeline.py`:`run_pipeline(question, top_k=...)` 加参数,透传给 `retrieve`。
3. `backend/run_service.py`:`execute_run` 读 `run.config`(JSON)取出 `top_k`,传给 `run_pipeline`;解析失败/缺省回退默认值(2)。
4. `backend/main.py`:`POST /runs` 已收 `config`(现固定 `"{}"`),Ch06 让前端真实传入;`GET /runs` 补返回 `config`(列表回看)。

## 接口契约

### POST /runs(扩展)

请求体从 `{dataset_id, config}` 中的 config 由前端真实传入,Ch06 支持字段:`{top_k: number}`。

### GET /runs(扩展)

每行新增 `config`(该 run 的配置快照 JSON 字符串,列表页展示「top_k=5」这类标签)。

### 对比数据来源

**复用 `GET /runs/{id}`**,前端对选中的多个 run 并发拉取(`Promise.all`),拿到各自的 `scores`(6 指标)做对比。不新增批量接口——run 数量少(几十以内),并发拉够快,少一个接口就少一处要维护。

## 前端改动

- `RunsView.tsx`:
  - 发起评测旁加 `top_k` 选择(InputNumber / Select,默认 2)。
  - run 列表加多选(rowSelection)+「对比」按钮,选中 2+ 个后跳 `/compare?ids=1,2,3`。
- 新视图 `CompareView.tsx`(路由 `/compare`):
  - 对比表:行 = 指标(6 个),列 = 选中的 run,单元格 = 该 run 该指标均值。
  - 分组柱状图:每个指标一组,组内多根柱(每个 run 一根),recharts。
- `api/index.ts` + `types.ts`:发起评测带 config、列表补 config、对比页并发拉取。

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 对比变量 | 先做 `top_k`(检索命中数) | temperature/提示词/知识库:top_k 影响检索最直接、最好演示;config 结构通用,后续加变量不改架构 |
| 配置注入 | `run.config` JSON → execute_run 解析 → run_pipeline(top_k) | 全局变量:config 快照让每次 run 可回看、可复现,是评测平台的刚需 |
| 对比数据 | 前端并发拉 `GET /runs/{id}` | 新增 `/runs/compare`:复用现有接口最小改动;run 数量少,并发拉够快 |
| 对比展示 | 表格(行=指标,列=run)+ 分组柱状图 | 只有表:指标差异用图更直观;只有图:精确值看表更清楚,两者互补 |
| config 缺省 | 解析失败/缺字段回退默认 top_k=2 | 抛错:老 run(空 config)应兼容,回退默认值最稳 |

## 本章不做

- A/B 测试的统计显著性检验。
- 自动寻优(grid search / 超参搜索)。
- 更多配置变量(temperature、提示词模板、知识库切换)—— 架构已支持,留后续章节。
