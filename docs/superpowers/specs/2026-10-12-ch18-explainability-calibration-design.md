# EvalFlow Ch18 设计:评测可解释性与 Judge 校准(Tier 1)

## 定位

Ch17 差距分析把「评测平台核心能力」排出了优先级,Tier 1 三项都指向同一件事——**让评测「可信 + 可解释」**:

1. **Trace 详情页 + Judge Reason**:能下钻到单条样本,看「问题→证据→答案→每个 Judge 怎么打的分、理由是什么」。
2. **Run Diff 视图**:并排对比两次 run 的失败案例,高亮证据差异,回答「为什么改完变好/变坏了」。
3. **Judge Calibration 校准集**:人工金标准校准 Judge,证明「LLM 打的 4.5 分,人类也认」。

三项分两个 tranche:**可解释性**(1+2,前端为主,无迁移)先做;**校准**(3,含 DB 迁移)体量最大,单独收尾。

## 现状(代码位置)

| 能力 | 位置 | 缺口 |
|---|---|---|
| Judge reason 已存 | [models.py](../backend/models.py) `Score.comment` | 已存但**没露出**:[list_traces](../backend/main.py) 返回 `{"name","value"}` 无 comment |
| 逐条明细 | [RunDetailView](../frontend/src/views/RunDetailView.tsx) 表格 | 分数打成「忠实度=0.8」,**无 reason、无完整链路** |
| run 对比 | [CompareView](../frontend/src/views/CompareView.tsx) | 只比**指标均值**,无逐条 diff、无证据差异 |
| 金标准标注 | [models.py](../backend/models.py) `DatasetItem` | **无** gold 字段 |

## 决策

### Feature 1:Trace 详情页 + Judge Reason

- **决策**:reason 已在库里,只做「API 露出 + 前端渲染」,不新增存储。`list_traces` 的 score 对象加 `comment` 字段。
- **前端**:逐条明细改 antd Table `expandable` 展开行——点「+」展开完整链路:证据全文(含 hits 分数)、回答、每个 Judge 的 score + reason。**不新开路由/Drawer**(展开行信息量够、代码最少)。

### Feature 2:Run Diff 视图

- **决策**:新增 `GET /runs/{a}/diff/{b}`,按 `dataset_item_id` 匹配两条 run 的 trace 对,返回并排数据 + 逐指标 delta。
- **匹配键用 `dataset_item_id` 而非 `input`**:input 文本不唯一(重复样本会错配),且跨数据集 diff 语义弱(题目不同,delta 是「换题」造成、会误导归因)。`dataset_item_id` 才是「同一条样本」的真实身份。
- **跨数据集兜底**:两个 run 的 `dataset_id` 不同时,返回 `different_datasets: true` 标记,前端提示「不在同一评测集,逐条对比无意义」,不做静默错配。
- **前端**:CompareView 加「逐条 Diff」区——并排展示 Run A/B 的证据与分数,delta 红(下降)绿(提升)高亮;证据文本不同时并排亮出差异。

### Feature 3:Judge Calibration 校准集

- **决策**:`dataset_items` 加 `gold_scores` JSON 列(可空),存人工金标准分数,如 `{"faithfulness": 0.9, "answer_relevance": 0.8}`。需要 **alembic 迁移**。
- **复用现有 run 机制**:校准 = 「在带金标准标注的数据集上跑一次 run,比较 judge 分 vs 金标准分」,不发明新的执行路径(校准的 judge 必须走和生产完全相同的流程,结果才有代表性)。
- **报告指标**:每个 metric 的 **bias**(judge 均值 − gold 均值,系统性偏松/偏严)+ **MAE**(平均绝对误差)+ **Pearson 相关系数**(排序一致性)+ 样本数(n)。bias 最可操作(能指导加修正量);n 小时 Pearson 噪声大,重点看 bias + MAE。
- **已知 tradeoff**:理想上「校准集」应与「被评测集」分开(避免泄漏);demo 用「gold_scores 作为数据集上的可选标注」可接受。
- **端点**:`PUT /datasets/{id}/items/{item_id}/gold`(标金标准)+ `GET /runs/{run_id}/calibration`(校准报告)。
- **前端**:DatasetDetailView 加「标金标准」入口;RunDetailView 加「校准」卡,展示 judge vs gold 一致性。

## 验收

- [x] Trace 展开行能看到每个 Judge 的 score + reason。
- [x] Diff 视图:同一条输入并排两条 run 的证据与分数,delta 高亮。
- [x] 校准:带 gold 标注的数据集跑 run 后,能出 bias + MAE + corr + n 报告。
- [x] 现有 77 后端 / 18 前端测试全绿(72→77 后端、14→18 前端)+ e2e。

## 本章不做

- 统计显著性 / 置信区间(Tier 拓展点,另行)。
- 校准结论落库 / 自动重标(报告读时计算即可)。
- SSE / 索引 / 模型性价比等其它差距项(各自单独处理)。
