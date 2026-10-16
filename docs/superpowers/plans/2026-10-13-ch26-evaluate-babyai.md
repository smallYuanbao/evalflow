# EvalFlow Ch26 实施计划:评测 baby-ai + 可复现性闭环

## 背景(对应 spec)

演示版,但带上可复现性:让 EvalFlow 能评真实 RAG 应用 baby-ai,且 run 快照记录**对方系统的状态**,使「这次比上次好」成立。

## 任务清单

### Task 0:环境编排(前置)

- [x] 把 Chroma 从 8000 挪到 8001(8000 现被 EvalFlow 后端占用)。
- [x] 改 baby-ai 的 `CHROMA_URL`;启动 baby-ai 的 python-server(3001)。
- [x] 验证 `POST /api/chat` 能正常返回 `answer` + `references`。

> **2026-10-16 补充**:Task 0 这一组是**当时**的做法,端口后来又调过一轮:
> Chroma 现在回到 `8000`(docker),EvalFlow 后端在 `8002`;baby-ai 的前端 / 后端 / 精排
> 分别在 `5180` / `8010` / `8011`(不再跑在 3001)。当前值以 `scripts/devguard.mjs` 顶部的端口表为准。
> 原文保留 —— 它记录的是当时的决策,不是当前配置。

### Task 1:baby-ai 加 `/api/meta`

- [x] 新增只读端点,返回:service / commit / model / embed_model / collection / collection_count / vector_top_k / rerank_top_k / query_rewrite。
- [x] commit 用 `git rev-parse --short HEAD`(取不到则 null)。

### Task 2:EvalFlow 配置与适配器

- [x] `config.py` 加 `eval_target`(默认 local)/ `babyai_base_url`;`.env.example` 同步。
- [x] 新增 `backend/external_babyai.py`:调 `/api/chat` 组装 `{output, retrieved_context, hits}`;每次全新 session_id、history=None。
- [x] `pipeline.run_pipeline` 按 `eval_target` 分发。

### Task 3:快照记录对方状态

- [x] `snapshot.py` 加 `external` 段:`{target, base_url, meta, meta_error}`。
- [x] meta 拿不到 → `meta=null` + `meta_error` 写明原因(**不静默记空**)。
- [x] 仅 `eval_target != local` 时才去取 meta。

### Task 4:前端展示

- [x] RunDetailView「复现上下文」加「被测系统」块:目标 / commit / 模型 / 检索参数 / 知识库。
- [x] `meta_error` 非空时显示醒目提示(「被测系统状态未知,本次结果不可与历史对比」)。

### Task 5:适配评测集 + 实跑

- [x] 建 5~7 条对齐 baby-ai 知识库的评测集(含库内 / 库外)。
- [x] `EVAL_TARGET=babyai` 跑一次,记录指标与快照。
- [x] 记录一次「改动 → 再评测」的对比(若有可改的开关,如 `QUERY_REWRITE_ENABLED`)。

### Task 6:测试

- [x] 后端:适配器组装正确;`eval_target=local` 时行为不变;meta 失败时 `meta_error` 有值。
- [x] 全量 + build + e2e 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| baby-ai 的 /api/meta | Task 1 |
| EVAL_TARGET=babyai 时输出来自 baby-ai | Task 2 |
| 快照含 external + 详情页可看 | Task 3/4 |
| meta 拿不到显式标记 | Task 3/6 |
| 87/33 全绿(默认不变) | Task 6 |

## 风险

- **跨仓库改动**:Task 1 改的是 baby-ai(另一个 git 仓库),提交要分开。
- **限流**:样本 ≤7 条可绕开 10/min;超了会被 429。
- **端口**:Task 0 动了正在跑的服务编排,做完要确认 EvalFlow 栈仍正常。
