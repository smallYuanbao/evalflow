# EvalFlow 评测集 v3 设计:把「尺子」校准成本地知识库的方言

## 背景

2026-10-18 对数据集 #3「baby-ai 端到端 v2」做了一次审查
（`docs/reports/2026-10-18-dataset-v2-review.md`），发现在 20 条样本上存在四类问题：

1. **要点不可达**：`飞机抱`、`常见反应` 在 3868 篇知识库文档中出现 0 次，
   机械指标（recall / hit@k / MRR）对它们永远判 0。
2. **同义改写**：`补水` vs 证据里的 `补液`、`揉腹` vs `按摩肚子`、`就医` vs `皮肤科`。
   语义正确但逐字不匹配，机械指标系统性偏低。
3. **真实检索失败**：要点在 KB 中可达，但 run #21 没召回（睡眠类两题、咳嗽）。
   这类应保留，属于被测系统的真实短板。
4. **历史 run 污染**：run 11–18 中每题有 1–5 条空回答/错误提示被当成正常回答打分，
   不能作为基线；run #21 是第一条干净基线。

## 目标

- v3 的机械指标与 judge 对同一批证据的判定尽量收敛；
- 不掩盖被测系统的真实失败（检索失败、脱离证据作答要保留）；
- 评测集本身可版本化、可重建、可 review。

## 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 数据集 1/2 | 归档，不删除 | 历史价值；删除不可逆 |
| 机械指标与 judge | **并存**，不改匹配算法 | 二者测量不同对象：逐字证据 vs 语义覆盖；冲突是诊断信号 |
| 版本方式 | 新建 v3 文件，不原地改 v2 | 旧 run 保持可解释；跨版本明确不可比 |
| item 19（肠绞痛） | 移入「知识缺口」数据集，断言改为「应说明资料不足/拒答」 | KB 全无该主题，放在库内题里测 recall 是错配 |
| item 25（红点点） | `就医→皮肤科`，并单独分桶 `皮肤-开放` | 消除词面误差；保留模糊问法的真实性，单独归因 |
| 其余同义词 | 按证据/KB 原词修订 | 机械指标口径是逐字匹配，要点必须写 KB 方言 |
| gold_scores | 继承 v2，标注「未重新校准」 | 避免把未确认的判断当事实；校准在 v3 跑完后单独做 |

## 产物契约

### 版本文件 `datasets/babyai-e2e-v3.json`

```jsonc
{
  "name": "baby-ai 端到端 v3",
  "dataset_hash": "1fe68f0e...",   // content_hash([{input,expected_output,bucket}])
  "item_count": 19,
  "change_log": [ /* 每条修订 from/to/reason */ ],
  "items": [
    { "index": 1, "db_id": 14, "input": "...", "expected_output": "...",
      "bucket": "...", "gold_scores": {...} | null }
  ]
}
```

- `dataset_hash` 与 `Run.config.dataset_hash` 同一算法；导入前由脚本校验。
- `db_id` 仅用于和旧 run 的 `dataset_item_id` 对照，导入时忽略。

### 知识缺口数据集 `datasets/babyai-kb-gap-v1.json`

- 1 条（宝宝肠绞痛怎么缓解），`bucket = "库外"`、`expected_output = ""`。
- **复用现有 `库外` 评分路径**：只评 `rejection`，不评 recall/judge。
  语义上这里的「库外」表示「知识库无依据」，由数据集 description 说明。
- 不改 `run_service` / `dataset_check` 的分桶逻辑，避免为 1 条样本引入新的评分代码路径。

### 导入脚本 `scripts/import_dataset.py`

- `python scripts/import_dataset.py datasets/xxx.json`
- 导入前重算哈希，不一致直接拒绝；
- 同名评测集默认拒绝重复导入（`--allow-duplicate` 可覆盖）；
- 不导入 `db_id` / `index` / `dataset_hash`。

## 验收标准

1. `GET /datasets/{v3_id}/validate` 返回 0 error、0 warning（结构层面）。
2. v3 评测 run 完成 19/19，无空回答/错误提示。
3. 机械指标与 judge 的全要点未命中分歧，从 v2 的 5 条降到 ≤2 条。
4. 知识缺口 run 中，item 19 的 `rejection = 0`（baby-ai 没有拒答），
   证明该场景确实在测「无依据时是否老实说不知道」。
5. 不修改数据集 #3 与历史 run。

## 风险与取舍

- **用词依赖证据**：修订后的要点（如 `皮肤科`）只在当前证据措辞下可命中；
  后续检索结果变化仍可能漏。根治要靠「要点 alternatives 字段 + 匹配规则版本化」，
  不在本次范围。
- **开放题单独分桶**：`皮肤-开放` 使「皮肤」桶样本数从 3 降到 2，
  分桶均值不可与 v2 直接对比（`dataset_hash` 已会提示不可比）。
- **gold 未重标**：v3 的 gold 继承 v2；item 27 的 gold 对应历史空/故障回答，
  校准报告在重标前不应作为 judge 可信度结论。
