# EvalFlow Ch20 实施计划:评测精修(hit@k/MRR + 一键复跑 + Judge 方差)

## 背景(对应 spec)

三条:检索标准机械指标(hit@k/MRR)、快照一键复跑、Judge 采样方差。顺序 ①→⑤→②。

## 任务清单

### Track A:hit@k / MRR(无迁移)

#### Task 1:机械指标函数

- [x] `backend/evaluators.py` 加 `hit_at_k(expected_output, hits)`、`mrr(expected_output, hits)`(从 expected_output 推导相关 chunk)。

#### Task 2:接入评测流

- [x] `run_service.py` `_process_item` 库内题存 `hit_at_k`/`mrr` 两个 Score。
- [x] `metrics.py` `METRIC_ORDER` 加 `hit_at_k`、`mrr`(放 recall 后)。

#### Task 3:前端标签 + 测试

- [x] 前端各视图 `METRIC_LABELS` 加 `hit_at_k`/`mrr`。
- [x] 更新 `test_run_service.py` 的 `INBUCKET`;加 hit@k/MRR 单测。

### Track B:一键复跑(纯前端)

#### Task 4:复跑按钮

- [x] `RunDetailView.tsx` 加「复跑」按钮:解析快照 top_k/retrieval → `api.createRun` → 跳转新 run。

#### Task 5:测试

- [x] 前端断言复跑按钮用快照配置调 createRun。

### Track C:Judge 方差(含迁移)

#### Task 6:judge 返回方差

- [x] `evaluators.py` `_judge` 采样后算方差并返回(`variance`,单样本为 None)。

#### Task 7:Score 加 variance 列 + 迁移

- [x] `models.py` `Score` 加 `variance`(Float 可空)。
- [x] `alembic revision --autogenerate`(剔除 retrieval_hits 漂移)。

#### Task 8:存储 + 露出

- [x] `run_service.py` 存 `r.get("variance")`。
- [x] `list_traces` score 对象加 `variance`。

#### Task 9:前端 + 测试

- [x] `TraceRow.scores` 加 `variance?`;展开行显示「score(方差)」。
- [x] 后端 `_judge` 方差单测;前端展开行方差断言。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| hit@k/MRR 进指标/趋势/对比 | Task 1–3 |
| 一键复跑 | Task 4–5 |
| Judge 方差到 trace 级 | Task 6–9 |
| 79 后端 / 20 前端全绿 + 新增 | 各 Task 测试 |
