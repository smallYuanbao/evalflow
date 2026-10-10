# EvalFlow Ch13 实施计划:可观测性(结构化日志 / 指标趋势 / 导出)

## 背景(对应 spec)

把「跑完只能看单次分数」升级为「日志可检索 + 趋势可看 + 数据可导出」。核心验收:**能回答 faithfulness 这几次跑是升还是降**。

**关键现状(决定实现方式)**:
- `run_service.execute_run` 已 `import logging` 且 `logging.exception` 兜底,但消息非结构化(run_id 混在文本里),`_process_item` 已算 `latency_ms` 只是没打日志。
- `aggregate_run` 是「单 run 聚合」,趋势要的是「多 run 批量」,得新写批量聚合避免 N+1。
- 前端已有 recharts(CompareView 柱状图 / BucketChart),折线图复用同一套。
- 路由 `/runs/{run_id}` 已存在,`/runs/trend` 必须放它**前面**。

## 任务清单

### Task 1:结构化日志

- [x] `backend/logging_config.py`(新):`JsonFormatter`(ts/level/logger/event + extra 字段 + exc)+ `setup_logging()`(幂等,只配 `backend` logger,`propagate=False`)。
- [x] `backend/main.py`:lifespan 调 `setup_logging()`。
- [x] `backend/celery_app.py`:`run_task` 里调 `setup_logging()`(worker 进程也走结构化日志)。
- [x] `backend/run_service.py`:`logger = logging.getLogger(__name__)`;run 开始/完成/失败(带 `run_id` + `duration_ms`)、每样本完成(带 `trace_id` + `latency_ms`)。
- [x] `backend/llm.py`:重试时 `logger.warning(..., extra={"attempt": ...})`。
- [x] 测试:`JsonFormatter` 输出含 run_id/trace_id/耗时字段;异常带 exc。

### Task 2:历史指标趋势

- [x] `backend/stats.py`:`runs_trend(limit=50)` 批量聚合——一次查询所有 run 的 trace/score,按 run 分组算 per-metric 均值,带 dataset_name。
- [x] `backend/main.py`:`GET /runs/trend`(**注册在 `/runs/{run_id}` 之前**)。
- [x] 前端:新 `TrendView.tsx`——recharts 折线图,X=run 序列,Y=分数,`Select` 切换指标。
- [x] 前端:`api.listRunsTrend` + `types.RunTrend`;App.tsx 加 `/trend` 路由 + 菜单项「趋势」。
- [x] 测试:`runs_trend` 正确聚合多 run 的 per-metric 均值。

### Task 3:指标导出(CSV)

- [x] `backend/main.py`:`GET /runs/{run_id}/export` → CSV 下载(每行一个 trace,input/output/latency + 各指标分)。
- [x] 前端:RunDetailView 加「导出」按钮(触发浏览器下载)。
- [x] 测试:导出 CSV 含表头 + 每 trace 一行。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 结构化日志(统一格式 + run_id/trace_id/耗时) | Task 1 |
| 历史指标趋势(答「升还是降」) | Task 2 |
| 指标导出 CSV | Task 3 |

## 本章不做

- OpenTelemetry/Jaeger 链路追踪、ELK/Loki 集中存储、指标告警(spec 已列)。
