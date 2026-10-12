# EvalFlow Ch18 实施计划:可解释性与 Judge 校准(Tier 1)

## 背景(对应 spec)

三个能力让评测「可信 + 可解释」。建议顺序:**Trace 详情 → Run Diff → 校准**(前两个无迁移、前端为主;校准含迁移,体量最大)。

## 任务清单

### Tranche A:Trace 详情页 + Judge Reason(无迁移)

#### Task 1:后端露出 reason

- [x] `backend/main.py` `list_traces` 的 score 对象加 `comment` 字段(`{"name","value","comment"}`)。

#### Task 2:前端展开行 + 完整链路

- [x] `frontend/src/types.ts` `TraceRow.scores` 加 `comment?: string`。
- [x] `RunDetailView.tsx` 逐条明细改 antd Table `expandable`,展开行显示:证据全文(含 hits 分数)、回答、各 Judge 的 score + reason 列表。

#### Task 3:测试

- [x] 后端:`test_api.py` 断言 list_traces 返回 comment。
- [x] 前端:RunDetailView 测试断言展开后能看到 reason。

### Tranche B:Run Diff 视图(无迁移)

#### Task 4:后端 diff 端点

- [x] `backend/main.py` 加 `GET /runs/{a}/diff/{b}`:按 `dataset_item_id` 匹配 trace 对,返回 `{input, a:{...}, b:{...}, deltas:{metric: b-a}, different_datasets}`;run 不存在 404,不同数据集返回标记不静默错配。

#### Task 5:前端逐条 Diff 区

- [x] `api/index.ts` + `types.ts` 加 `getRunDiff(a,b)` 与类型。
- [x] `CompareView.tsx` 加「逐条 Diff」区:并排证据 + 分数,delta 红绿高亮;证据不同并排亮出。

#### Task 6:测试

- [x] 后端:diff 匹配 + delta 正确、404。
- [x] 前端:diff 渲染断言。

### Tranche C:Judge Calibration 校准集(含迁移)

#### Task 7:gold_scores 列 + 迁移

- [x] `backend/models.py` `DatasetItem` 加 `gold_scores`(Text 可空)。
- [x] `alembic revision --autogenerate` 生成迁移并核对(剔除了无关的 retrieval_hits 类型漂移)。

#### Task 8:后端校准端点

- [x] `PUT /datasets/{id}/items/{item_id}/gold`(写金标准 JSON)。
- [x] `GET /runs/{run_id}/calibration`:对含 gold 的 trace,按 metric 算 bias + MAE + Pearson corr + n。

#### Task 9:前端标注 + 报告

- [x] `DatasetDetailView.tsx` 加「标金标准」入口(per-item 编辑 modal)。
- [x] `RunDetailView.tsx` 加「校准」卡,展示 judge vs gold 的 bias/MAE/corr/n。

#### Task 10:测试

- [x] 后端:gold 写入 + 校准报告 bias/MAE/corr 正确。
- [x] 前端:标注入口 + 校准卡渲染。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| Trace 展开行看 Judge score+reason | Task 1–3 |
| Diff 并排证据 + delta 高亮 | Task 4–6 |
| 校准 bias/MAE/corr/n 报告 | Task 7–10 |
| 72 后端 / 14 前端全绿 + 新增 | 各 Task 测试 |
