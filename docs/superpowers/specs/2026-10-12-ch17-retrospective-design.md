# EvalFlow Ch17 设计:复盘叙事与差距分析

## 定位

Ch01–Ch16 把评测平台从「最小闭环」做到了「生产级硬化(CI/e2e/非root) + 混合检索 + 回归门禁」。Ch17 是收尾章,做两件事:

1. **差距分析**:对照「一个成熟评测平台该有的能力」做一次体检,标出已做/部分做/没做,排优先级——为后续章节和面试准备指路。
2. **复盘叙事**:把 Ch01–Ch16 的设计决策、踩坑、三项目(MewHelp / baby-ai / EvalFlow)关系打包成面试能讲的故事 + README 升级。

本章基本**不写新功能**,是「盘点 + 叙事」的收尾。差距分析定稿后,挑出的高优先级项再单独开章做。

## 差距分析(体检结果)

> 对照来源:一次对「评测平台成熟度」的系统梳理,共 6 大类 14 个点。结论:**3 项已做、7 项部分做、4 项没做**。

### 体检表

| 类别 | 能力点 | 状态 | 现状 |
|---|---|---|---|
| ① 实时性 | SSE 实时进度 | 🟡 部分 | 有进度(`Run.progress` + 原子自增),但前端是**轮询**;详情页轮询已补(本 session),仍是轮询不是 SSE |
| ① 任务 | 后台任务队列 Redis+Celery | ✅ 已做 | Ch10:`run_task.delay` 入队、worker 消费、重启自愈 |
| ① 存储 | 索引(created_at / run_id) | ❌ 没做 | [models.py](../backend/models.py) 未加 `index=True`,demo 规模无感 |
| ② 对比 | Run Diff 视图 | 🟡 部分 | [CompareView](../frontend/src/views/CompareView.tsx) 只比指标分数,无并排失败案例、无证据差异高亮 |
| ② 详情 | Trace 详情页 + Judge reason | 🟡 部分 | 有「逐条明细」但**不展示 Judge 的 reason**(reason 已在 `Score.comment`)、无独立详情页 |
| ② 地图 | 知识库地图 bucket 筛选 | ❌ 没做 | 且概念错位:bucket 是**数据集样本**维度,知识库地图是**知识 chunk**维度 |
| ③ 门禁 | 基线对比 + 掉 5% 报警 | ✅ 已做 | Ch15 门禁(阈值 + `max_regression=0.05` + PASS/FAIL);缺「持久化基线」(现为请求级 `baseline_run_id`) |
| ③ CI | GitHub eval-on-push + PR 评论 | 🟡 部分 | Ch14 有 `ci.yml`(pytest/vitest/build/e2e),无「push 触发评测 + PR 评论」;仓库无 remote |
| ③ 归因 | 分桶归因 / 热力图 | 🟡 部分 | `by_bucket` 聚合已有,无「哪个 bucket 拖后腿 + 对比基线」的归因 |
| ④ 成本 | 成本看板 | 🟡 部分 | Ch12 有总费用/总 token,缺**单条平均成本** |
| ④ 选型 | 模型性价比对比 | ❌ 没做 | 数据管道在(`chat_model` 快照 + cost),缺对比视图 |
| ⑤ CI/CD | (与「GitHub eval」同) | 🟡 部分 | 同上 |
| ⑥ 校准 | Judge Calibration 校准集 | ❌ 没做 | 最硬核一块,见优先级 Tier 1 |
| ⑥ 结构化 | JSON Mode | ✅ 已做 | Ch11 `chat_json` 强制结构化输出,解析失败记 NULL |
| ⑥ 版本 | Judge Prompt 版本化 | 🟡 部分 | 有 `PROMPTS_VERSION="v1"`,但**所有 prompt 共用一个版本号**,未把 judge 与 pipeline 分开 |

### 优先级

**Tier 1 —— 命中「评测平台」核心价值 + 面试,建议优先做**

1. **Trace 详情页 + Judge Reason 展示**(投入最低、性价比最高):reason 已在库里(`Score.comment`),只是前端没渲染。铺成「问题→证据(带分数)→答案→各 Judge 打分+理由」完整链路,是评测平台**可解释性**的灵魂。
2. **Run Diff 视图**(价值最高):并排失败案例 + 证据差异高亮,回答「为什么改了 X 后效果变好/坏」——评测平台区别于「只看一个分数」的分水岭。
3. **Judge Calibration 校准集**(概念最深):人工标 10–20 条金标准 → Judge 打分 → 校验与人类判断的一致性。LLM-as-Judge **可信度**的标准答案,面试极高频。

**Tier 2 —— 有价值,锦上添花**

4. **分桶归因**:复用门禁的 delta 逻辑,升级成「和基线比,哪个 bucket 掉了」。
5. **模型性价比对比**:同数据集 × 多模型 × 成本/分数,面试「技术选型」话题。
6. **SSE**:体验优化 + 本身是面试点,但非评测核心(真推送要跨 Celery worker 上 Redis pub/sub)。

**Tier 3 —— 零/低成本,随手做,不必单独成章**

7. **索引**:`index=True` 一行事 + 迁移。
8. **单条平均成本**:一行事。
9. **Judge Prompt 独立版本号**:拆 `pipeline_v` + `judge_v`,否则「模型变了还是评判标准变了」分不清。

**Tier 4 —— 超 demo 量级 / 需外部条件,先写文档备用**

10. **GitHub eval-on-push + PR 评论**:需 remote + CI 跑真实 LLM(密钥/成本)。
11. **知识库地图 bucket 筛选**:概念错位,优先级最低。

### 拓展优化点(体检清单之外,更硬核)

1. **检索机械指标 hit_rate@k / MRR**:当前 recall 是子串匹配(弱),加 hit@k/MRR 让检索质量可量化、可解释、不烧 LLM。
2. **Judge 方差/一致性**:Ch11 已采样多次取均值,顺手存 `variance`,识别「不稳定 Judge」。
3. **统计显著性 / 置信区间**:两个 run 差 2% 是真变好还是噪声?bootstrap 置信区间,避免「噪声当改进」。
4. **语义相似度机械指标**:embedding 算「回答 vs 标准答案」相似度,作 answer_correctness 的机械兜底。
5. **一键复跑**:config 快照已有,加「用同一快照重跑」按钮,让 Ch09 可复现真正可用。
6. **评测报告导出(Markdown/HTML)**:比 CSV 更面向人,一键生成能贴进 PR 的报告。

## 复盘叙事(本章后半,另行细化)

> 本 spec 先落「差距分析」;复盘叙事部分随推进补全,骨架如下:

1. **设计决策一句话回顾**:每章一个「为什么这样选」(SQLite→PG 可切换、Celery 队列化、nginx 自签而非 Caddy、应用层 RRF 而非 Milvus、门禁读时计算不落库…)。
2. **三项目关系图**:MewHelp(Agent 编排 / Milvus / MCP / 微调)、baby-ai(RAG 管线 / 混合检索 / 精排)、EvalFlow(评测 / 门禁 / 趋势)——三者能力映射 + 「混合检索三实现」这个差异化钩子。
3. **面试叙事**:一条能完整讲出的主线「为什么要建评测平台 → 怎么让 Judge 可信 → 怎么用它当发布门禁」。
4. **README 升级**:从「怎么跑」升级到「怎么讲」。

## 验收

- [x] 差距分析体检表 + 优先级定稿(本章第一部分)。
- [ ] 复盘叙事四块落地(设计决策回顾 / 三项目关系 / 面试叙事 / README)。
- [ ] 差距分析挑出的 Tier 1 项,给出明确「下一步先做哪个」的结论。

## 本章不做

- 差距分析里列出的新功能(它们各自开章,不塞进 Ch17)。
- 三项目技术打通(EvalFlow 接 baby-ai 真实 pipeline)——那是「技术层」,单独成章,Ch17 只做叙事层的关系梳理。
