# 拒答双信号 + Gold 重标 实施计划

## 背景(对应 spec)

`docs/superpowers/specs/2026-10-18-rejection-dual-signal-and-gold-design.md`

## 任务清单

### Task 1:拒答双信号

- [x] `backend/prompts.py` 新增 `REJECTION_PROMPT`；`JUDGE_PROMPTS_VERSION` 升到 `v2`。
- [x] `backend/evaluators.py` 新增 `rejection_judge()` 与 `rejection_dual()`：
      judge 主判、词表兜底，分歧写进 comment。
- [x] `backend/run_service.py`：库外题的判定移到开 DB session 之前
      （避免 LLM 调用跨写事务）；E2E 模式只走词表，保持确定性。
- [x] `Score.comment` 落库两信号与分歧原因。

### Task 2:测试

- [x] 新增 4 个双信号单测：一致 / 词表假阳性 / 词表假阴性 / judge 失败回退。
- [x] 更新 `test_execute_run_absent_bucket`，mock 掉双信号判定。
- [x] `pytest -q`：**111 passed**。

### Task 3:实跑验证

- [x] run #24（知识缺口数据集）：回答里出现「没有证据」这个词（词表判拒答），
      judge 判「给出了大量针对肠绞痛缓解的实质内容」→ **rejection=0**，judge 覆盖词表。
- [x] run #25（v3 全量，19/19）：4 条库外题的 comment 都记录了两信号。
      换轮胎那条词表=1、judge=0（先给了换轮胎步骤），以 judge 为准；
      其余 3 条两信号一致。
- [x] 结论：双信号按设计工作；单次 rejection 数值仍受 baby-ai 生成随机性影响
      （同一题不同 run 回答不同）。

### Task 4:Gold 重标准备

- [x] 从 run #22 导出 15 条库内题的盲标材料（问题/要点/证据/回答，不含 judge 分）。
- [x] 生成 CSV 模板（`item_id` + 5 指标 + annotated_on_run + note）。
- [x] 编写操作指南与评分定义。
- [x] `scripts/import_gold.py`：校验范围、自动备份旧 gold、支持 dry-run。
- [x] **AI 预标并导入**（2026-10-19）：Claude 按评分卡在 run #22 输出上逐条打分，
      写入 `2026-10-18-gold-scores-filled.csv`（note 标注 AI draft），
      经 `import_gold.py` 导入数据集 #4；旧值已自动备份。
- [ ] **人工抽检**（2026-10-19 暂停，见 [`docs/TODO.md`](../../TODO.md)）：
      建议至少抽 3~5 条（含 faithfulness/context_precision 分歧大的），
      修正后重新导入。当前 gold 是 AI 判断，不是独立人类金标准。
- [x] 校准结果（run #22，n=15）：

| 指标 | bias | MAE | corr | 解读 |
|---|---|---|---|---|
| faithfulness | −0.057 | 0.117 | 0.264 | 均值接近，排序一致性弱 |
| context_precision | **−0.353** | **0.353** | 0.352 | judge 系统性比标注更严；口径分歧最大 |
| context_recall | −0.089 | 0.134 | 0.788 | 可用 |
| answer_relevance | +0.020 | 0.040 | −0.430 | 双方都集中在 0.9~1.0，方差太小，corr 无意义 |
| answer_correctness | −0.050 | 0.053 | **0.972** | 高度一致，可作为主指标 |

### Task 5:文档同步

- [x] spec / plan 落盘。
- [x] 审查报告补充双信号与 gold 重标说明。
- [x] `datasets/README.md` 无需变化（数据契约未变）。

## 验收对照

| spec 验收项 | 结果 |
|---|---|
| 4 类双信号单测 | ✅ |
| 后端测试全绿 | ✅ 111 passed |
| KB-gap 词表假阳性被 judge 纠正 | ✅ rejection=0 |
| v3 库外题 comment 记录两信号 | ✅ 4/4 |
| gold 标注导入 + 校准 | ⏳ 待用户填写 CSV |

## 运行注意(本轮踩到)

- **API 热重载会误伤运行中的 run**：uvicorn `--reload` 触发的 lifespan
  `_recover_stale_runs()` 会把 worker 仍在执行的 run 标成 failed；run 完成时
  又被 `_mark("done")` 覆盖。
  **已解决**：改成心跳 + 进度双超时回收，见
  `docs/superpowers/plans/2026-10-19-stale-run-recovery.md`。
