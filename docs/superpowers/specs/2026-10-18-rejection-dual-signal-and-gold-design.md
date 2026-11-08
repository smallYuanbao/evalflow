# 拒答双信号 + Gold 重标 设计

## 背景

v2/v3 评测集审查暴露出两个测量问题：

1. **拒答判定只靠词表**：`rejected()` 是字符串匹配，实测同时存在
   - 假阳性：回答说「超出了我的范围」后照样给出完整教程，词表判成拒答；
   - 假阴性：回答换了个说法「可不归我管」，词表里没有，判成没拒答。
2. **gold_scores 不可用**：当前 gold 继承自 v2，至少 item 27 是在空回答/故障样本上标的，
   run #21 的校准结果（MAE 0.09–0.24、corr 0.06–0.61）不能说明 judge 的可信度。

## 决策一：拒答双信号

**规则：词表 + LLM judge，judge 主判、词表兜底。**

| 情况 | 判定 | 理由 |
|---|---|---|
| 两信号一致 | 取该值 | 无歧义 |
| 两信号不一致 | **以 judge 为准**，分歧写进 `Score.comment` | judge 看有没有实质作答，能同时修假阳性和假阴性 |
| judge 失败（None） | 回退词表 | 裁判故障不应中断整轮评测 |

为什么不用 OR / AND：

- OR：假阳性仍然存在（词表命中就判拒答），修不了「口头拒答但实际作答」；
- AND：假阴性仍然存在（词表漏了就直接判未拒答），修不了措辞漂移；
- judge 主判：额外成本是每条库外题 1 次 judge 调用（一轮 4 条，可忽略）。

**可追溯**：`Score.comment` 同时记录两个信号和分歧原因，例如
`双信号不一致(词表=1.0, judge=0.0),以 judge 为准:回答给出了实质内容…`。
prompt 版本从 `judge_prompts v1` 升到 `v2`，历史 run 的 rejection 不与新 run 直接比较。

## 决策二：Gold 重标协议

- **盲标**：标注材料只给问题、标准要点、检索证据、回答，不给 judge 分数与评语。
- **绑定 run #22**：gold 是「这一轮的证据和回答应该得多少分」，不是恒定的题目属性。
  被测系统或检索链路变了要重标。
- **五指标独立打分**：`faithfulness` / `context_precision` / `context_recall` /
  `answer_relevance` / `answer_correctness`，0~1，建议 0.25 粒度。
- **人工判断优先**：不允许用 judge 输出回填 gold（否则校准是循环论证）。

## 产物契约

| 文件 | 作用 |
|---|---|
| `docs/reports/2026-10-18-gold-annotation-materials.md` | 15 条盲标材料（问题/要点/证据/回答） |
| `docs/reports/2026-10-18-gold-scores-template.csv` | 评分表；填好后复制为 `...-filled.csv` |
| `docs/reports/2026-10-18-gold-annotation-guide.md` | 操作指南与评分定义 |
| `scripts/import_gold.py` | 校验并写回 `DatasetItem.gold_scores`；自动备份旧值 |
| `GET /runs/22/calibration` | judge vs gold 的 bias / MAE / corr / n |

CSV 列：`item_id` + 五个指标（必需），`annotated_on_run` / `note`（可选）。
空值表示该指标不标，校准会跳过。

## 验收标准

1. 双信号单测覆盖：一致、两类不一致、judge 失败回退，共 4 例。
2. 全部后端测试通过（111）。
3. KB-gap 数据集：item 19 的回答含「没有证据」一词（词表假阳性），
   双信号最终判 **rejection=0**，comment 写明分歧。
4. v3 run：库外题的 `Score.comment` 均记录两信号。
5. gold 标注完成后：15 条全部写入，校准报告 `n=15`（或各指标实际数），
   报告里注明「gold 绑定 run #22」。

## 风险与取舍

- **judge 自身有方差**：双信号把「措辞判定」换成「语义判定」，准确率上升，
  但引入 LLM 噪声；单次 run 的 rejection 仍不建议当强结论。
- **成本**：每条库外题多 1 次 judge 调用；只影响 `库外` 桶。
- **gold 与 run 绑定**：重标后只能校准 run #22（或与之输出一致的 run），
  跨 run 复用会失真。
- **API 热重载会误伤运行中的 run**：`--reload` 触发 lifespan 的
  `_recover_stale_runs()`，把仍由 worker 执行中的 run 标成 failed（本轮实际发生，
  run 结束时又被 `_mark("done")` 覆盖）。评测期间应避免编辑文件，
  或把 uvicorn 的 `--reload-dir` 限制到 `backend/`。
