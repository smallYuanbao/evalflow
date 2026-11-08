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

## 验证

- `uv run pytest tests/test_external_ecom.py tests/test_evaluators.py tests/test_run_service.py -q` → 34 passed
- 全量 → **126 passed**
- 真实联调：`run_pipeline_ecom("退货政策是什么")` 返回 answer + 5 hits + 811 字 context；
  `fetch_meta()` 返回 `kb_version` / `chat_model` / `prompt_version`
