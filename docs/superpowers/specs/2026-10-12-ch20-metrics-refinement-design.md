# EvalFlow Ch20 设计:评测精修(hit@k/MRR + 一键复跑 + Judge 方差)

## 定位

Ch17 差距分析的「拓展优化点」里三条高优先级项,让评测平台再专业一截:

1. **hit@k / MRR**:检索质量用标准机械指标度量(当前 `recall` 是子串匹配,太弱)。
2. **一键复跑**:把 Ch09 的「可复现」从声明变成可操作。
3. **Judge 方差**:和 Ch18 校准一起把「LLM-as-Judge 可信度」讲完整——校准看「和人类对不对」,方差看「自己稳不稳」。

## 现状(代码位置)

| 能力 | 位置 | 缺口 |
|---|---|---|
| recall(子串匹配) | [evaluators.py](../backend/evaluators.py) `recall` | 无排序/命中语义的检索指标 |
| 检索命中(带 rank) | [run_service.py](../backend/run_service.py) `out["hits"]` | 已落库 `retrieval_hits`,可后算 hit@k/MRR |
| 快照 | [snapshot.py](../backend/snapshot.py) | 有 top_k/retrieval,但无「一键复用」 |
| judge 采样 | [evaluators.py](../backend/evaluators.py) `_judge` | 采样 N 次只存均值,**方差被丢** |
| Score 模型 | [models.py](../backend/models.py) | 无 variance 字段 |

## 决策

### Track A:hit@k / MRR

- **决策**:运行期计算的**机械指标**(和 recall 一致),从 `out["hits"]`(有序)+ `expected_output` 推导相关 chunk——「chunk 文本含任一要点 → 相关」,**零新增标注**。
- **定义**:`hit_at_k` = 任一相关 chunk 出现在 top-k(0/1);`mrr` = `1 / 首个相关 chunk 的排名`(没有则 0)。
- **落地**:`evaluators.py` 加 `hit_at_k` / `mrr`;`_process_item` 存为 `Score(name="hit_at_k"/"mrr")`;进 `METRIC_ORDER`。

### Track B:一键复跑

- **决策**:**纯前端**。RunDetailView 加「复跑」按钮,从 config 快照取 `top_k` + `retrieval`,调 `createRun(dataset_id, {top_k, retrieval})`,跳转新 run。
- **已知 tradeoff**:理想要校验知识库/数据集 hash 是否漂移并警告;demo 先做「同配置重跑」,hash 校验留作后续。

### Track C:Judge 方差

- **决策**:`_judge` 采样后顺带算方差并返回;`Score` 加 `variance` 列(迁移);`list_traces` 露出;前端展开行显示「score(方差)」。
- **单样本时**(`judge_samples=1`)方差为 None(无法定义)。e2e mock / 测试 mock 不返回 variance → 走 `r.get("variance")` 兜底 None。

## 验收

- [x] hit@k/MRR:检索命中与否、排名是否正确度量,进指标卡/趋势/对比。
- [x] 一键复跑:RunDetailView 能按快照发起同配置新 run。
- [x] Judge 方差:多采样时能看每 judge 的方差。
- [x] 现有 82 后端 / 21 前端测试全绿(79→82、20→21)+ e2e。

## 本章不做

- hit@k 的「相关 chunk 人工标注」(用 expected_output 推导,零标注)。
- 复跑的 hash 漂移校验。
- 方差的聚合/告警(只展示到 trace 级)。
