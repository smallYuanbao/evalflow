# EvalFlow Ch31 实施计划:指标覆盖率 + 第一次真正的人工校准

## 背景(对应 spec)

收「可信」这条线的最后两块:分数要说明「基于几条」;校准机制要真跑一次。

## 任务清单

### Task 1:覆盖率

- [x] `stats.aggregate_run` 返回 `score_coverage: {metric: {scored, attempted}}`。
- [x] `gate.MIN_COVERAGE = 0.8`,低于它拒判并写明「样本不足(x/y 评上)」;不传 coverage 行为不变。
- [x] 门禁端点传入 coverage;前端 MetricCard 显示「采样 n/N」,低覆盖标黄。
- [x] 测试:覆盖率统计、门禁拒判、达标照常、不传兼容。

### Task 2:人工校准实操

- [x] 重跑评测(先修 baby-ai 的三个 bug)拿到干净数据。
- [x] 逐条读「问题+证据+回答」,人工打 5 个指标分,共 16 条,经 API 写入。
- [x] 取校准报告:faithfulness bias −0.138、answer_relevance corr 0.978 等。
- [x] 记录 n=8 → n=16 的对照(answer_relevance corr 0.315 → 0.978,小样本假象)。

### Task 3:验证

- [x] 后端 101 / 前端 33 / e2e 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| score_coverage 准确 | Task 1 |
| 门禁覆盖率拒判 | Task 1 |
| 前端显示采样 | Task 1 |
| 校准报告产出 | Task 2 |
| 全绿 | Task 3 |
