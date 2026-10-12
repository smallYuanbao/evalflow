# EvalFlow Ch19 设计:分桶归因与模型性价比(Tier 2)

## 定位

Ch17 差距分析的 Tier 2 有两块(SSE 已定维持轮询,跳过):

1. **分桶归因**:回答「这次总体分数掉了,是哪个 bucket 拖的后腿」。把 Ch15 门禁的「和基线比 delta」下沉到 bucket 粒度——精准定位「跨文档类 Recall 掉了,但策略类没变」。
2. **模型性价比对比**:把「分数」和「成本」摆一起看,回答「GPT-4o 分数高 5%,但贵 20 倍,值不值」——直接帮业务做技术选型。

## 现状(代码位置)

| 能力 | 位置 | 缺口 |
|---|---|---|
| 分桶聚合 | [stats.py](../backend/stats.py) `aggregate_run` 返回 `by_bucket` | 只有单 run 的桶聚合,**无和基线的 delta** |
| 门禁 delta 逻辑 | [gate.py](../backend/gate.py) `evaluate_gate` | 只在**整体指标**粒度,没下沉到 bucket |
| 成本 + 模型快照 | [snapshot.py](../backend/snapshot.py) `chat_model` + `aggregate_run` 的 `cost` | 有数据,但**无按模型分组的对比视图** |
| 门禁卡(含基线选择器) | [RunDetailView](../frontend/src/views/RunDetailView.tsx) | 可复用其 baseline 选择器做归因 |

## 决策

### Feature 1:分桶归因

- **决策**:新增 `GET /runs/{run_id}/bucket-attribution?baseline_run_id=`,复用 `aggregate_run` 的 `by_bucket`,算 per-bucket per-metric 的 `delta = run − baseline`。返回 `{buckets: [{bucket, count, deltas: {metric: delta}}]}`。
- **前端**:RunDetailView 门禁卡下方加「分桶归因」表(行 = bucket,列 = 指标 delta,红降绿升),baseline 复用门禁卡的选择器。

### Feature 2:模型性价比对比

- **决策**:新增 `GET /runs/model-comparison`,按 `config.chat_model` 分组 done 的 run,返回每模型 `{model, run_count, avg_cost, avg_cost_per_item, avg_scores}`。`chat_model` 从 config 快照解析(缺省归「unknown」)。
- **前端**:新视图「模型对比」(菜单入口),表格(模型 / run 数 / 各指标均值 / 平均成本 / 单条成本)+ 散点图(x=平均成本,y=faithfulness),一眼看「贵多少、好多少」。

## 验收

- [x] 分桶归因:给定 run + 基线,能出每个 bucket 的逐指标 delta。
- [x] 模型对比:按模型分组出 run 数 / 平均分数 / 平均成本 / 单条成本。
- [x] 现有 79 后端 / 20 前端测试全绿(77→79、18→20)+ e2e。

## 本章不做

- SSE(已定维持轮询)。
- 模型对比的统计显著性 / 置信区间(Tier 拓展点)。
- 自动「换模型」建议(只展示数据,不下结论)。
