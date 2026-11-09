# Ch07 · EvalFlow 接入 ecom-agent

> 日期：2026-11-08
> 被测系统：ecom-agent `POST /api/eval/chat` + `GET /api/meta`
> 对应 ecom spec：`docs/superpowers/specs/ch07-eval-design.md`（另一个仓库）

## 改了什么

| 文件 | 内容 |
|---|---|
| `backend/external_ecom.py` | 新增适配器：`run_pipeline_ecom` / `fetch_meta`；限流、429/5xx/超时重试 |
| `backend/config.py` | `ecom_base_url` / `ecom_timeout` / `ecom_max_rpm` |
| `backend/run_service.py` | `EVAL_TARGET=ecom` 分支 |
| `backend/snapshot.py` | 外部快照按 target 分发；ecom 记录 `/api/meta` |
| `backend/evaluators.py` | 要点支持 `a|b` 任选；无检索上下文时机械指标记 NULL |
| `tests/test_external_ecom.py` | 6 条：映射、重试、4xx、meta、快照 |
| `tests/test_evaluators.py` | 新增 4 条：任选、无上下文、空 hits |
| `tests/test_run_service.py` | 无上下文样本的指标集合改为 5 个（3 个 NULL + 2 个答案 judge） |

## 三个关键点

1. **ecom 是黑盒**：`top_k` / `retrieval` 传参不生效，评测只量最终输出。
2. **无检索上下文记 NULL**：B/C/E 出口没有 `references` / `hits`，
   context / faithfulness 不评，机械指标不记 0。
3. **失败语义**：4xx 不重试（样本错误）；429/5xx/超时退避重试 2 次。

## 运行方式

```bash
EVAL_TARGET=ecom \
ECOM_BASE_URL=http://127.0.0.1:8081 \
uv run uvicorn backend.main:app --port 8002
# worker 也要带同样环境变量重启
```

ecom 评测实例：

```bash
ENABLE_EVAL_API=true \
DATABASE_URL=sqlite+aiosqlite:///./data/eval.db \
uv run uvicorn app.main:app --port 8081
```

## run-01（ecom 44 条）

| 指标 | 值 | 覆盖 |
|---|---|---|
| recall | 0.95 | 10 / 44 |
| hit_at_k / MRR | 1.00 / 1.00 | 10 / 44 |
| context_precision | 0.91 | 10 / 10 |
| context_recall | 0.90 | 10 / 10 |
| faithfulness | 1.00 | 10 / 10 |
| answer_relevance | 0.8614 | 44 / 44 |
| answer_correctness | 0.9818 | 44 / 44 |

分桶：

| 桶 | answer_relevance | answer_correctness |
|---|---|---|
| B1 | 0.99 | 0.92 |
| B2 | 1.00 | 1.00 |
| B3 | 0.90 | 1.00 |
| B4 | 0.97 | 1.00 |
| B5 | 0.625 | 1.00 |
| B6 | 0.525 | 1.00 |
| B7 | 0.60 | 1.00 |

### 两个指标口径修正

1. **hit@k / MRR 只对有回答证据的出口算**：B3/B4 的 policy 检索不算回答证据；
   无 context 时**不写评分行**（不适用 ≠ 失败），覆盖率会显示 `10 / 10`，
   不再出现 `10 / 44` 这种容易被误读成漏测的口径。
2. **judge 认识 `/` 与 `|`**：context_recall / answer_correctness 的 prompt
   明确 `/` 分组、`|` 任选。

### 低分说明

- B1 `退货政策是什么`：回答缺 7 天窗口，answer_correctness 0.3；
- B5–B7 answer_relevance 低：转人工/拒答是正确行为，不应按普通问答解读。

## 验证

- `uv run pytest tests/test_external_ecom.py tests/test_evaluators.py tests/test_run_service.py -q` → 34 passed
- 全量 → **126 passed**
- 真实联调：`run_pipeline_ecom("退货政策是什么")` 返回 answer + 5 hits + 811 字 context；
  `fetch_meta()` 返回 `kb_version` / `chat_model` / `prompt_version`
- run #31：44/44 完成，指标见上
- 覆盖率口径改为「不适用不写行」后未重跑；下一轮 run-02 会显示 `10 / 10`
