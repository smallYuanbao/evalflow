# EvalFlow Ch24 实施计划:交互细节再修

## 背景(对应 spec)

六个修:输入框计数遮挡、期望要点换行、金标准可清空、分桶必选、基线不写脏 URL、标签加释义。

## 任务清单

### Task 1:加样本表单

- [x] 期望要点块留底部间距(计数不遮按钮)。
- [x] 期望要点改 `TextArea`(autoSize)+ 加 label。

### Task 2:分桶必选

- [x] `canAdd = 问题非空 && 分桶已选`;按钮禁用 + 未选时提示「影响打分方式」。

### Task 3:金标准清空

- [x] 弹窗加「清空金标准」按钮(已有金标准时才可点)。
- [x] 清空单个输入框 = 移除该指标(之前会写成 0)。

### Task 4:基线不写脏 URL

- [x] 拆 `urlBaseline`(显式)/ `autoBaseline`(默认);只有用户动手才写 URL。

### Task 5:基线选择器加标签

- [x] 门禁卡右侧 Select 前加「对比基线」标签 + 悬停解释。

### Task 5b:标签释义

- [x] 新增 `utils/metrics.ts`(`METRIC_LABELS` + `METRIC_DESC`),收敛 4 处重复定义。
- [x] 指标卡 / 门禁表 / 校准表 / 逐条明细的指标名加 Tooltip。
- [x] 分桶、金标准标签加 Tooltip。

### Task 5c:按钮说明

- [x] 「导出 CSV」悬停说明:导的是逐条明细(问题/回答/耗时/各指标分数)。
- [x] 「一键复跑」悬停说明:按快照配置重跑。

### Task 5d:CSV 表头中文

- [x] `backend/metrics.py` 加 `METRIC_LABELS`;`run_export_csv` 表头改中文。
- [x] 更新 `test_stats.py` / `test_api.py` 的表头断言。

### Task 6:测试

- [x] 前端:未选分桶不能加样本、金标准可清空(33 全绿)。
- [x] e2e:加样本步骤补「选分桶」。
- [x] 后端 87 / 前端 33 / build / e2e 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 计数不遮挡 | Task 1 |
| 期望要点换行 | Task 1 |
| 金标准可清空 | Task 3/6 |
| 分桶必选 | Task 2/6 |
| URL 不被自动改写 | Task 4 |
| 标签释义 | Task 5 |
