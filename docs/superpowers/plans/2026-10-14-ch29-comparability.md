# EvalFlow Ch29 实施计划:对比前提的显式校验

## 背景(对应 spec)

门禁/归因/Diff 都比两个 run,但从不校验「是不是同一批题」。评测集一改,
门禁照常给 PASS/FAIL,用户会读成「质量回归」。

## 任务清单

### Task 1:可比性函数

- [x] `stats.dataset_comparability(a, b)`:比对快照里的 `dataset_hash`。
- [x] 三种取值:`True`(同) / `False`(不同,附题目数+hash 前缀) / `None`(早期 run 无 hash)。

### Task 2:三处接入

- [x] `GET /runs/{id}/gate` → `comparability`。
- [x] `GET /runs/{id}/bucket-attribution` → `comparability`。
- [x] `GET /runs/{a}/diff/{b}` → `comparability`(比原来的 `dataset_id` 判断更严)。

### Task 3:前端

- [x] `ComparabilityAlert` 组件(共享):false=橙 warning / null=蓝 info / true=不显示。
- [x] RunDetailView(门禁卡、归因卡)+ CompareView(Diff 区)接入,**排在结论之前**。

### Task 4:测试与验证

- [x] 后端 3 个单测(hash 同 / 不同 / 缺失)。
- [x] 实测:同集 → true;20 条 vs 5 条 → false 且原因清楚。
- [x] 后端 95 / 前端 33 / e2e 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 三种取值有测试 | Task 1/4 |
| 三端点返回 comparability | Task 2 |
| 前端三处提示、排在结论前 | Task 3 |
| 实测验证 | Task 4 |
