# 评测集版本文件

这里存放**纳入 git 的评测集快照**。数据库 `data/eval.db` 是运行时产物（已被
`.gitignore` 排除），换机器或误删后就没了；评测集本身必须可 review、可重建，
所以以文件为准。

## 版本列表

| 文件 | 条数 | 状态 | 说明 |
|---|---|---|---|
| `babyai-e2e-v2.json` | 20 | 已弃用（保留为基线） | 2026-10-13 建；审查报告见 `docs/reports/2026-10-18-dataset-v2-review.md` |
| `babyai-e2e-v3.json` | 19 | **当前主评测集** | 要点对齐知识库用词；肠绞痛移出；红点点标记为开放题 |
| `babyai-kb-gap-v1.json` | 1 | 独立场景 | 知识库没有依据的主题，只评「是否拒答/说明资料不足」 |

### 两个特殊分桶

- **`库外`**：只评 `rejection`，不评 recall/judge。v3 的 4 条非育儿问题用它；
  kb-gap 数据集也复用它来表示「知识库无依据」——语义由数据集 description 说明。
- **`皮肤-开放`**：v3 里「小宝宝身上起红点点是啥」单独分桶。它是一个宽泛的鉴别诊断问题，
  固定要点判分天然偏低；单独归因，避免拉低整个「皮肤」桶。

## 文件约定

| 字段 | 说明 |
|---|---|
| `name` / `description` | 与 `datasets` 表一致 |
| `source` | 导出时来自哪张库、哪个 id，便于追溯 |
| `dataset_hash` | 与 `Run.config.dataset_hash` 同一算法（`backend.snapshot.content_hash`），用于校验导出是否完整 |
| `items[].index` | 文件内稳定序号（1 起） |
| `items[].db_id` | 导出时的数据库行 id，仅用于和旧 run 的 `dataset_item_id` 对照；重建后可能变化 |
| `items[].input` | 问题 |
| `items[].expected_output` | 期望要点，用 `/` 分隔。**必须逐字出现在检索证据里**，否则机械指标判 0 |
| `items[].bucket` | 分桶标签。`库外` 是特殊值：只评拒答，不评 recall |
| `items[].gold_scores` | 人工参考分（JSON），仅用于 `GET /runs/{id}/calibration` 校准 judge；不参与 run 打分 |

## 校验导出是否忠实

重建时的 hash 必须等于文件里的 `dataset_hash`：

```python
from backend.snapshot import content_hash
hash_items = [{"input": i["input"], "expected_output": i["expected_output"],
               "bucket": i["bucket"]} for i in data["items"]]
assert content_hash(hash_items) == data["dataset_hash"]
```

## 版本与修改

- **不要原地改历史版本**：改动会产生新的 `dataset_hash`，历史 run 会自动标记为不可比。
  修订时新建版本文件（如 `babyai-e2e-v3.json`），保留旧文件作为基线。
- 修改后先跑「评测集自检」，再跑一次评测确认指标变化符合预期。
- `gold_scores` 必须是**独立于被测 judge 的人工判断**；从 judge 输出抄回来的 gold
  会让校准变成循环论证（误差恒为 0，没有意义）。
