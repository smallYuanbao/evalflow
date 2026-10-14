# EvalFlow Ch32 实施计划:评测集自检

## 背景(对应 spec)

`recall` 是子串匹配,评测集要点写错会**静默**让分数偏低。参照 MewHelp 的 `eval-check` 补上。

## 任务清单

- [x] `backend/dataset_check.py`:`check_structure`(5 条规则)+ `check_against_run`(证据比对)。
- [x] `GET /datasets/{id}/validate?run_id=` 端点(数据集不存在 404)。
- [x] 前端:数据集详情页「评测集自检」按钮 + 结果弹窗(按 level 分色)。
- [x] 测试:5 条结构规则 + 证据检查 + 干净数据集不误报。
- [x] 实测:在真实评测集上跑,抓到 2 条要点与知识库措辞对不上的题。
- [x] 复盘补「和 MewHelp 的评测比」章节。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 端点 + 404 | 任务 2 |
| 结构规则有单测 | 任务 4 |
| 证据检查 | 任务 1/4 |
| 前端入口 | 任务 3 |
| 全绿 | 任务 4 |
