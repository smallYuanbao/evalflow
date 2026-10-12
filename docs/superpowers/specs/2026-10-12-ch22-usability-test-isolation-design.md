# EvalFlow Ch22 设计:可用性修复与测试隔离

## 定位

三件「用起来才发现」的问题,都不是新功能:

1. **趋势页可读性**:X 轴只有 `#613`,看不懂是什么;且无法按评测集看趋势。
2. **模型对比页**:散点图每个点常显模型名 → 点一多糊成一团;且模型名千奇百怪。
3. **测试污染 dev 库**:测试和 dev 共用 `data/eval.db`,测试数据灌进 dev,直接搞坏了模型对比页。

第 3 条是前两条的**共同病根**——模型对比页里 432 个 `unknown`、一堆 `model-a-<时间戳>`,全是测试写进去的。

## 现状(代码位置)

| 问题 | 位置 | 现状 |
|---|---|---|
| 趋势轴标签无意义 | [TrendView.tsx](../../frontend/src/views/TrendView.tsx) `name: '#'+r.id` | 接口已返回 `dataset_name`/`created_at`,前端丢了没用 |
| 趋势无法按评测集过滤 | [stats.py](../../backend/stats.py) `runs_trend(limit)` | 无 `dataset_id` 参数 |
| 散点标签重叠 | [ModelCompareView.tsx](../../frontend/src/views/ModelCompareView.tsx) `<LabelList>` | 每个点都渲染名字 |
| 测试污染 dev 库 | 根 [conftest.py](../../conftest.py) | 无独立测试库;顶层 `from backend.db import init_db` |

## 决策

### 决策 1:趋势轴放短标签,中文信息进 tooltip

轴标签 `#613` → `Run #613`;评测集名(中文)/时间/指标值放**自定义 tooltip**,悬停才看。

**理由**:趋势图 X 轴是「历次 run」,标签多、轴空间有限,塞不下中文数据集名。短标签 + 富 tooltip 是标准做法。

### 决策 2:趋势加 `dataset_id` 过滤

`runs_trend(limit, dataset_id=None)` + `GET /runs/trend?dataset_id=`;前端加「全部评测集」下拉。

下拉选项**从全部 run 推导,不受当前筛选影响**——否则选了之后选项自己缩没。

### 决策 3:散点图去掉常显标签

删掉 `<LabelList>`,模型名/成本/分数/Run 数放 tooltip;X 轴刻度限小数位。

**理由**:散点图的价值是**看分布**(谁便宜又好),不是「读每个点的名字」。名字属于「想细看时」的信息,tooltip 正合适。

### 决策 4:测试隔离数据库(**治本**)

在**根 conftest.py 最顶部**(早于任何 backend import)设 `DATABASE_URL=sqlite:///data/test.db`。

**关键坑**:一开始放在 `tests/conftest.py` 里**不生效**——根 conftest 先加载,且它在模块顶层就 `from backend.db import init_db`,而 `backend.db` 在 **import 时**就按 settings 建好了 engine。晚一步就只能改到已经指向 dev 库的 engine。所以必须放在**最先加载、且早于 backend import**的地方。

### 决策 5:清理 dev 库脏数据

备份 `data/eval.db` 后重置,由 alembic 重建 schema + `seed()` 灌回示例评测集。

**破坏性操作,已获用户显式确认(指名 `data/eval.db`)后执行。**

## 验收

- [x] 趋势轴显示 `Run #N`,tooltip 含中文评测集名 + 时间 + 指标值。
- [x] 趋势可按评测集过滤(后端参数 + 前端下拉)。
- [x] 散点图不再有重叠标签,名字进 tooltip。
- [x] 测试写独立库,dev 库跑测试前后行数不变。
- [x] dev 库清理完成(622 评测集/677 run → 1 评测集/0 run;备份留档)。

## 本章不做

- 给 run 加「名字」字段(run 本就没有名字概念,用 id + 数据集名足够)。
- 自动化的历史数据保留策略(测试隔离后不再累积,清理是一次性动作)。
