# EvalFlow Ch27 实施计划:拒答识别词表修正

## 背景(对应 spec)

Ch26 接真实系统暴露:EvalFlow 的拒答词表匹配不上 baby-ai 的措辞,库外题被误判成「没拒答」。

## 任务清单

### Task 1:扩词表

- [x] `evaluators.REJECT_MARKERS` 按「意图」分两组:不知道/没有证据 + 超出范围/只答某类。
- [x] `rejected()` docstring 写明这是启发式及其漏判边界。

### Task 2:测试用真实数据

- [x] 新增用例,直接用 baby-ai 的回答原文(含 emoji / markdown);正常回答仍为 0.0。

### Task 3:离线验证 + 全量

- [x] 用已存 trace 重算:Run 6 / Run 8 的 4 条库外 trace 0.0 → 1.0(不花钱、不用重跑)。
- [x] 后端 92 测试全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 真实拒答回答判 1.0 | Task 1/2 |
| 正常回答仍 0.0 | Task 2 |
| 已存 trace 重算 | Task 3 |
| 92 测试全绿 | Task 3 |
