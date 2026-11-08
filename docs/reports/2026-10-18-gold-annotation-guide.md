# Gold 重标操作指南

> **状态（2026-10-19）**：Claude 已按评分卡完成一版 **AI 预标**，写入
> `2026-10-18-gold-scores-filled.csv` 并导入数据集 #4。
> 这不是独立的人类金标准，建议至少人工抽检 3~5 条后再当作校准依据。
> 下面的流程保留，用于人工复标或修正。

## 为什么要重标

`gold_scores` 是人工参考分，唯一用途是校准 LLM judge（`GET /runs/{id}/calibration`）。
当前库里的 gold 继承自 v2，至少 item 27 是在**空回答/故障样本**上标的，
因此现有校准结论不可用。

本次在 **run #22**（`baby-ai 端到端 v3`，19/19，无故障样本）的干净输出上重新标注。

## 标注原则

1. **盲标**：标注材料里只有问题、标准要点、检索证据、回答，没有 judge 分数。
   先独立打分，之后再做对比——否则测出来的只是「你和 judge 想得一样」。
2. **评的是这一轮的输出**：证据和回答都来自 run #22。不要按"理想系统应该怎样"打分。
3. **五个指标分开看**：
   - `context_*` 评检索证据；
   - `answer_*` 评最终回答；
   - `faithfulness` 看回答有没有超出证据。
4. 分数取 0~1，建议 0.25 粒度。拿不准就写中间值，不要空着——空值会跳过该指标。

## 操作步骤

### 1. 打开材料

- 标注材料：[2026-10-18-gold-annotation-materials.md](2026-10-18-gold-annotation-materials.md)
- 评分表模板：[2026-10-18-gold-scores-template.csv](2026-10-18-gold-scores-template.csv)

### 2. 复制模板并填写

```bash
cd /Users/lidong/Desktop/workFile/evalflow
cp docs/reports/2026-10-18-gold-scores-template.csv \
   docs/reports/2026-10-18-gold-scores-filled.csv
```

在 `...-filled.csv` 里给 15 行填 5 列分数：

| 列 | 含义 |
|---|---|
| `faithfulness` | 回答里的论断有多少能在证据里找到依据 |
| `context_precision` | 5 条证据里真正相关且有用的占比 |
| `context_recall` | 标准要点被证据覆盖的比例 |
| `answer_relevance` | 回答是否直接回应问题 |
| `answer_correctness` | 回答与标准要点的语义一致程度 |

`note` 列可选，用来记"这条拿不准"或"证据明显跑题"。

### 3. 预期投入

15 条，约 30~45 分钟。每条平均 2~3 分钟。

### 4. 导入并看校准结果

```bash
# 先 dry-run 检查格式
.venv/bin/python scripts/import_gold.py \
  docs/reports/2026-10-18-gold-scores-filled.csv --dataset-id 4 --dry-run

# 没有问题再写入（会自动备份旧 gold）
.venv/bin/python scripts/import_gold.py \
  docs/reports/2026-10-18-gold-scores-filled.csv --dataset-id 4

# 看 judge vs gold 的 bias / MAE / corr
curl -s http://localhost:8002/runs/22/calibration | jq
```

## 重要限制

- **gold 与 run #22 绑定**：分数是对这一轮的证据和回答打的。如果之后改了被测系统
  的检索链路或换了知识库，需要重新标注，不能拿旧 gold 校准新 run。
- **不要用 judge 输出回填 gold**：那会让校准变成循环论证（误差恒为 0）。
- **样本量只有 15**：Pearson 相关系数只能看方向，不能当强结论。
