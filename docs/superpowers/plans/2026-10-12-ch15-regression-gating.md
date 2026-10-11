# EvalFlow Ch15 实施计划:回归门禁

## 背景(对应 spec)

给 run 加 PASS/FAIL 门禁判定:绝对阈值 + 相对基线回归,读时计算不落库。核心是一个纯函数 + 一个端点 + 一张前端门禁卡。

## 任务清单

### Task 1:门禁纯函数与规则表

- [x] 新增 `backend/gate.py`:`GATE_RULES`(5 个 judge 指标的 `min` + `max_regression`)+ `evaluate_gate(scores, baseline_scores)` 纯函数,返回 `{passed, checks}`。
- [x] 规则细节:null 指标记 `passed=false` + `note="未评"`;无 baseline 时只做绝对阈值;`delta = value - baseline_value`。

### Task 2:门禁端点

- [x] `backend/main.py` 加 `GET /runs/{run_id}/gate?baseline_run_id=`:拉两个 run 的 `aggregate_run`,调 `evaluate_gate`,baseline 不存在返回 404。
- [x] 路由注册在 `/runs/{run_id}` 之后(静态段 `/runs/{run_id}/gate` 比动态段更具体,但动态段带类型 `int` 不会抢 `/gate`,仍需测一下)。

### Task 3:后端测试

- [x] `tests/test_gate.py`:刚好等于阈值 / 差一点 / 缺指标 NULL / 有 vs 无 baseline / baseline 404 五类。
- [x] 现有 56 后端测试保持全绿(现 65 = 56 + 9 门禁)。

### Task 4:前端门禁卡

- [x] `frontend/src/api` + `types.ts`:加 `getRunGate(id, baselineId?)` 与 `GateResult` 类型。
- [x] `RunDetailView.tsx` 顶部加「门禁」卡:PASS/FAIL 徽章 + 逐指标 check 表 + baseline 选择器(复用 `api.listRuns()`,默认最近另一个 done run)。

### Task 5:前端测试与构建

- [x] RunDetailView 单测补门禁卡断言(12→13),e2e 断言收紧到 header 内状态 Tag。
- [x] `npm run build` 通过。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| evaluate_gate 四类边界单测 | Task 1/3 |
| 端点 PASS/FAIL + checks + 404 | Task 2/3 |
| 前端门禁卡渲染 + 切换 baseline 重算 | Task 4 |
| 现有 56 后端测试全绿 | Task 3 |
