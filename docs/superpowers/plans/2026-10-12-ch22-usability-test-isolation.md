# EvalFlow Ch22 实施计划:可用性修复与测试隔离

## 背景(对应 spec)

三件:趋势可读性、散点图标签、测试污染 dev 库。第 3 条是前两条的病根。

## 任务清单

### Task 1:趋势页轴标签 + tooltip

- [x] `TrendView.tsx`:`name` 改 `Run #${id}`;自定义 Tooltip 显示 评测集名(中文)/时间/指标值。

### Task 2:趋势按评测集过滤

- [x] `stats.py` `runs_trend(limit, dataset_id=None)`;`main.py` 端点透传。
- [x] `api/index.ts` `listRunsTrend(dataset_id?, signal?)`。
- [x] `TrendView.tsx` 加「全部评测集」下拉,选项从全部 run 推导(不受筛选影响)。

### Task 3:散点图去重叠标签

- [x] `ModelCompareView.tsx` 删 `<LabelList>`;自定义 Tooltip 显示 模型名/Run 数/单条成本/指标值;X 轴刻度限小数位。

### Task 4:测试隔离数据库

- [x] 根 `conftest.py` 顶部(早于 backend import)设 `DATABASE_URL=sqlite:///data/test.db`。
- [x] 验证:跑测试前后 dev 库行数不变,`data/test.db` 独立生成。

### Task 5:清理 dev 库(用户确认后执行)

- [x] 备份 `data/eval.db` → `data/eval.db.bak-20261012-214344`。
- [x] 删除 `data/eval.db`(+ WAL/SHM),重启后端由 alembic 重建 schema。
- [x] `seed()` 灌回示例评测集(1 个评测集 / 7 样本 / 0 run)。

### Task 6:测试

- [x] 后端 `test_stats.py` 加 `dataset_id` 过滤断言(86 全绿)。
- [x] 前端 24 全绿 + build 通过。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 轴 `Run #N` + 中文 tooltip | Task 1 |
| 按评测集过滤 | Task 2 |
| 散点去重叠标签 | Task 3 |
| 测试写独立库 | Task 4 |
| dev 库清理 | Task 5(待确认) |
