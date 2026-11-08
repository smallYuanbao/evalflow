# TODO

> 记录**已经明确、但暂时不做**的事项。做完后移入对应的 spec/plan。

## 暂停：Gold 人工抽检与重新校准

**状态**：2026-10-19 暂停。先花时间把评测平台的运行原理和核心概念搞清楚，再回来做。

**背景**：

- 数据集 #4（baby-ai 端到端 v3）已有 15 条 **AI 预标** gold，
  来自 run #22 的证据与回答。
- 当前 gold 是 Claude 按评分卡预标的（`docs/reports/2026-10-18-gold-scores-filled.csv`），
  **不是独立人类金标准**。
- 校准结果（run #22，n=15）：
  - `answer_correctness` corr 0.972，可用；
  - `context_recall` corr 0.788，可用；
  - `faithfulness` corr 0.264，排序不可靠；
  - `context_precision` bias −0.353，judge 与标注口径差异最大；
  - `answer_relevance` 方差太小，相关系数无意义。

**恢复后要做的事**：

1. 人工抽检 5 条，重点看分歧最大的：
   - item 34 发烧（context_precision：标注 1.0 vs judge 0.6）
   - item 44 红点点（0.6 vs 0.25）
   - item 35 拉肚子（context_recall：0.67 vs 0.33）
   - item 43 夜里闹腾（correctness：0.33 vs 0.6）
   - item 47 半夜哭醒（correctness：0.67 vs 0.9）
2. 修改 `docs/reports/2026-10-18-gold-scores-filled.csv`，重新导入并跑校准。
3. 根据校准结论决定门槛指标：在人工确认前，`context_precision` 和
   `answer_relevance` 不进硬门槛。

**相关文件**：

- [评分表](reports/2026-10-18-gold-scores-filled.csv)
- [可读版](reports/2026-10-18-gold-scores-filled.md)
- [标注材料（run #22 证据与回答）](reports/2026-10-18-gold-annotation-materials.md)
- [操作指南](reports/2026-10-18-gold-annotation-guide.md)
- [实施计划](superpowers/plans/2026-10-18-rejection-dual-signal-and-gold.md)

---

## P1：知识库覆盖判定（bucket 标签）没有可复现流程

**问题**：

- 目前没有工具回答「知识库里到底有没有能回答这个问题的内容」。
- 现有 `GET /datasets/{id}/validate?run_id=` 的证据检查，是拿**某一次 run 实际召回的
  证据**去比要点。它分不清两种完全不同的情况：
  - 知识库里有，但这次检索没召回（真实检索失败，题目应保留）；
  - 知识库里根本没有（标签写错了，题目不该按 recall 评）。
- v2 审查时用的是临时脚本 + 人工判断，**没有落成可重复的工具**。
  下次加评测集、换知识库、或别人接手时，同样的判断要从头再来。

**影响**：`bucket` 是评分语义的总开关（`库外` 只评拒答，其余评 recall + judge）。
标签错了，指标、门禁、归因全部跟着错，而且**是静默的**——不报错，只是结论不可信。

**最小方案**：

1. `scripts/classify_coverage.py`
   - 输入：评测集 JSON（或 dataset_id）
   - 直接遍历 Chroma 全库（`rag_docs` / `rag_samples` / `rag_medical`），
     **不经过被测系统的检索器**
   - 对每个期望要点：逐字命中数 + 样例文档 id/片段
   - 对问题做多种改写（原文 / 同义词 / 按要点拆），大 top-k 检索，检查是否可达
   - 输出建议标签：`库内` / `知识缺口` / `库外`，并附证据
2. 报告落盘 `docs/reports/`，每条标签记录证据（doc ids / quotes），可 review
3. 边界样本人工确认（partially answerable 的尤其是重灾区）
4. 验收：在 v3 上复现已知结论——
   `飞机抱=0`、`常见反应=0`、肠绞痛=知识缺口、红点点=库内（检索可达）

**后续（可选）**：

- `DatasetItem` 增加 coverage 元数据（判断依据、doc ids、判断时间、KB 版本）
- 加 `GET /datasets/{id}/coverage` 接口 + 前端入口
- 把知识库版本/哈希写进标签；KB 变了自动提示重新判定

**当前状态**：v3 的标签是 2026-10-18 人工 + 临时脚本审过的，**内容本身没问题**；
缺的是「下次还能同样做」的流程。

---

## 其它已知待办（未排期）

| 事项 | 说明 |
|---|---|
| 周期性残留 run 回收 | 目前只在 API 启动时执行；可加 watchdog 定期跑同样的双超时判定 |
| `context_precision` 口径 | 标注与 judge 差 0.35；需要先定义「相关」是"有用"还是"直接相关" |
| 查询扩展 | item 25 这类模糊问题仍靠宽泛检索；计划做词表优先的受控扩展 |
| 多轮指代消解评测 | evalflow 数据集条目只有单条 input，没有 history；要测需扩 schema |
| 数据集 1/2 归档、删除 `11111` | 需要确认后执行，删除不可逆 |
| failed run 19/20 清理 | 后端没有删除 run 的接口，需要脚本或接口 |
