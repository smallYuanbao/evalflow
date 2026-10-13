# EvalFlow Ch29 设计:对比前提的显式校验(可比性)

## 定位

修一个**正确性缺口**:门禁 / 分桶归因 / 逐条 Diff 的结论,都建立在「两边测的是同一批题」
这个前提上,但**代码从来没校验过这个前提**。

## 问题

`dataset_hash` 早就记进了 run 快照(Ch09),覆盖 `(input, expected_output, bucket)` 三项——
任何一条样本增删改都会变。但**没人用它来校验对比的前提**:

| 端点 | 比两个 run | 校验了什么 |
|---|---|---|
| `GET /runs/{id}/gate?baseline_run_id=` | ✅ | ❌ 无 |
| `GET /runs/{id}/bucket-attribution?baseline_run_id=` | ✅ | ❌ 无 |
| `GET /runs/{a}/diff/{b}` | ✅ | ⚠️ 只看 `dataset_id`,不看内容 |

**后果**:给评测集加一条样本,`dataset_id` 不变、`dataset_hash` 变了。
此时门禁照常输出 PASS/FAIL——**用户会把它读成「质量回归」,而它其实是「换了一批题」**。

这比「没有门禁」更危险:**一个错误的结论比没有结论更容易误导人**。

## 决策

### 决策 1:用 `dataset_hash`,不加 `version` 字段

**理由**:
- hash 是**自动的、精确的**——覆盖 `(input, expected_output, bucket)`,改一个字都会变;
- 手写的 version 号**要靠人记得 bump**。忘了 bump 就会出现「内容变了、版本号没变」——
  这属于「**静默失效**」那一类问题(见 Ch27),比不做更糟。

**放弃**:给 `Dataset` 加 version 列 + 迁移 + UI。收益只是「人能读」,代价是一个会漂移的手工步骤。

### 决策 2:三种取值,`null` 也是一等公民

```python
{"comparable": True,  "reason": None}          # 同一批题,可以比
{"comparable": False, "reason": "20 条 vs 5 条, hash 51f2835e vs b6396b9f, ..."}
{"comparable": None,  "reason": "有一方是早期 run、快照里没有 dataset_hash,无法判断"}
```

`None` 必须存在:早期 run 的快照里没有 hash,**不能默认当成「可比」**——
那就是把「不知道」伪装成「知道」。这和 Ch26 的 `meta_error` 是同一个模式。

### 决策 3:一个共享函数,三处接入

`stats.dataset_comparability(run_a_id, run_b_id)`,由 gate / bucket-attribution / diff 共用。
**同一个概念只写一遍**——避免三处各判各的、慢慢长歪。

### 决策 4:前端把前提摆在结论前面

新增 `ComparabilityAlert` 组件,在门禁结论、归因表、Diff 区**之前**显示。
- `false` → 橙色 warning + 具体原因(题目数 + hash 前缀)
- `null` → 蓝色 info(「无法确认」,不是错误)
- `true` → 不显示

## 这是本章真正想说的模式

把 Ch26 和 Ch29 放在一起看,是同一个模式:

| 章 | 「结论」 | 「前提」不成立时 |
|---|---|---|
| Ch26 | 这次比上次好/坏 | 拿不到被测系统状态 → `meta_error` + 「不可与历史对比」 |
| Ch29 | 门禁 PASS/FAIL | 两次不是同一批题 → `comparable: false` + 原因 |

> **一个结论的价值,不超过它前提的可靠性。前提不成立时,系统必须说出来,
> 而不是给一个看起来正常的数字。**

## 验收

- [x] `dataset_comparability` 三种取值各有测试(hash 同 / 不同 / 缺失)。
- [x] gate / bucket-attribution / diff 三个端点都返回 `comparability`。
- [x] 前端三处都显示提示,且**排在结论之前**。
- [x] 实测:Run14 vs Run12(同集)→ `comparable: true`;
      Run12(20 条) vs Run10(5 条)→ `false` + 「20 条 vs 5 条, hash …」。
- [x] 后端 95 / 前端 33 / e2e 全绿。

## 本章不做

- 评测集的**版本管理流程**(改名、归档、分支):那是产品功能,和「校验可比性」是两件事。
- 跨评测集的**归一化对比**(比如把不同题集的分数折算到同一尺度):超出范围。
