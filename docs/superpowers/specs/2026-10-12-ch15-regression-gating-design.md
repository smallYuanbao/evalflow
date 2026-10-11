# EvalFlow Ch15 设计:回归门禁

## 定位

Ch14 把「上线才需要的硬骨头」补完了,平台能造评测集、发评测、看指标、看趋势、对比两次 run。但还差**最后一步**——把「能看指标」升级成「能用指标做发布决定」。

Ch15 加**回归门禁(regression gating)**:给一次 run 一个 PASS/FAIL 判定,回答「这次改动能不能上线」。它是评测平台存在的意义收口——模型/知识库/prompt 任何一处改动都可能悄悄把质量做坏,门禁是唯一的质量安全网。

## 现状(代码位置)

| 能力 | 位置 | 状态 |
|---|---|---|
| per-metric 均值聚合 | [stats.py](../backend/stats.py) `aggregate_run` 返回 `scores: {metric: avg}` | 已有 |
| 两次 run 对比 | [CompareView.tsx](../frontend/src/views/CompareView.tsx)(Ch06) | 已有,但只展示差异、不判 PASS/FAIL |
| 历史指标趋势 | [stats.py](../backend/stats.py) `runs_trend`(Ch13) | 已有 |
| 指标注册表 | [metrics.py](../backend/metrics.py) `METRIC_ORDER`(7 个指标) | 已有 |
| 阈值判定 / 基线回归 / 告警 | —— | **缺** |

## 决策

### 决策 1:门禁是「读时计算」的纯函数,不落库

不新增表、不加字段、不迁移。门禁 = 对已聚合指标套规则的**纯函数**,每次请求现算。

**理由**:门禁本质是「对已有数据的视图」,不是新状态。落库反而引入一致性负担(阈值改了要不要重算历史?)。读时计算让「改阈值/换基线」立即对历史 run 生效,且零迁移成本。demo 量级这是正解;生产若要做「某时点门禁结论快照」再落库不迟。

### 决策 2:规则 = 绝对阈值 + 相对基线回归容忍

每条规则两条腿,`AND` 关系:

- `min`——绝对下限(如 `faithfulness >= 0.7`)。
- `max_regression`——相对基线最多允许掉多少(如 `0.05`)。

判定:指标 `>= min` **且**(有基线时)`>= baseline_value - max_regression`。前者挡「绝对质量差」,后者挡「改坏了(相对上次)」——两次跑都过了绝对线、但这次比上次掉了 10%,照样判 FAIL。

### 决策 3:只门禁 LLM judge 指标,recall / rejection 不门禁

默认门禁 5 个 judge 指标:`faithfulness / context_precision / context_recall / answer_relevance / answer_correctness`。规则表放 [gate.py](../backend/gate.py),可配。

**理由**:recall 是机械关键词(非质量下限)、rejection(拒答率)是「越高越好」但不是质量地板,拿它们设 `min` 下限语义不对。门禁的对象是「LLM 判断的质量」,只挑这 5 个。

### 决策 4:baseline 显式传参,不自动猜

门禁接口收可选 `baseline_run_id`。不传 = 只做绝对阈值;传 = 加相对回归。前端给一个 run 选择器,默认选「时间上最近的另一个 done run」。

**理由**:「和谁比」是调用方的决定,不该由门禁自己猜(最近的 run 可能是 failed 或空 run)。显式传参最干净,也方便测试。

### 决策 5:独立端点 `GET /runs/{run_id}/gate`,不塞进 aggregate_run

新增 `GET /runs/{run_id}/gate?baseline_run_id=` 返回:

```json
{
  "passed": false,
  "baseline_run_id": 3,
  "checks": [
    {"metric": "faithfulness", "value": 0.72, "threshold": 0.7,
     "baseline_value": 0.85, "delta": -0.13, "passed": false, "note": "较基线下降超过容忍度"}
  ]
}
```

**理由**:保持 `aggregate_run` 干净(它被趋势/对比/详情页复用);门禁是详情页的附加视图,单独拉不拖累主接口。null 指标(judge 挂)记 `passed=false`、`note="未评"`——**门禁的门槛是「每个被门禁的指标都得评上且达标」**。

### 决策 6:前端门禁卡,复用对比语义

RunDetailView 顶部(费用统计卡之前)加「门禁」卡:

- PASS(绿)/ FAIL(红)徽章 + 一句话结论(FAIL 时列出掉线指标)。
- 逐指标 check 表:当前值 / 阈值 / 基线值 / 变化 / 通过与否。
- baseline 选择器(下拉选 run,默认最近另一个 done run),切换即重算。

**理由**:复用 Ch06 对比的「逐指标差异」展示,但加「阈值 + 判定」层,把「对比」升级成「结论」。

## 验收

- [x] `evaluate_gate` 纯函数单测:刚好等于阈值 / 差一点点 / 缺指标(NULL)/ 有 vs 无 baseline 四类边界。
- [x] 端点返回正确 `passed` + `checks`;baseline 不存在时返回 404。
- [x] 前端门禁卡渲染,切换 baseline 后重算;PASS 绿 / FAIL 红。
- [x] 现有 65 后端测试全绿(56 旧 + 9 门禁新增,不改旧行为)。

## 本章不做(超出 demo 量级)

- 门禁结论落库 / 历史门禁记录(读时计算即可)。
- 接 CI/CD 自动阻断发布(那要 workflow 里跑评测 + 读门禁结果,是 Ch15 之外的另一块)。
- 多级门禁 / 审批流 / 灰度放量(roadmap 已排除)。
