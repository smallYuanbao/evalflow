# EvalFlow Ch19 实施计划:分桶归因与模型性价比(Tier 2)

## 背景(对应 spec)

两块:分桶归因(门禁 delta 下沉到 bucket)+ 模型性价比对比(分数×成本选型)。SSE 已定维持轮询,不做。

## 任务清单

### Track A:分桶归因(无迁移)

#### Task 1:后端归因端点

- [x] `backend/main.py` 加 `GET /runs/{run_id}/bucket-attribution?baseline_run_id=`:复用 `aggregate_run` 的 `by_bucket`,算 per-bucket per-metric `delta = run − baseline`;run/基线不存在 404。

#### Task 2:前端归因表

- [x] `api/index.ts` + `types.ts` 加 `getBucketAttribution` 与类型。
- [x] `RunDetailView.tsx` 门禁卡下方加「分桶归因」表(行=bucket,列=指标 delta,红降绿升),baseline 复用门禁选择器。

#### Task 3:测试

- [x] 后端:归因 delta 正确、404。
- [x] 前端:归因表渲染。

### Track B:模型性价比对比(无迁移)

#### Task 4:后端模型对比端点

- [x] `backend/main.py` 加 `GET /runs/model-comparison`:按 `config.chat_model` 分组 done run,返回每模型 `run_count / avg_scores / avg_cost / avg_cost_per_item`。

#### Task 5:前端模型对比视图

- [x] `api/index.ts` + `types.ts` 加 `getModelComparison` 与类型。
- [x] 新增 `ModelCompareView.tsx`(菜单入口):表格 + 散点图(x=成本,y=faithfulness)。

#### Task 6:测试

- [x] 后端:模型分组 + 均值/成本正确。
- [x] 前端:模型对比渲染。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 分桶归因逐指标 delta | Task 1–3 |
| 模型分组分数×成本 | Task 4–6 |
| 77 后端 / 18 前端全绿 + 新增 | 各 Task 测试 |
