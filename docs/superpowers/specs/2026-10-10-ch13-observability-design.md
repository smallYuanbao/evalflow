# EvalFlow Ch13 设计:可观测性(结构化日志 + 指标趋势 + 导出)

## 目标

现在评测跑完,能看单次 run 的分数、能横向对比多个 run,但**答不了「faithfulness 这几次跑是升还是降」**,也**没法从日志里按 run/trace 定位问题**。

Ch13 补上「可观测」三件套:结构化日志(统一格式 + 关键字段)、历史指标趋势(折线图)、指标导出(CSV)。

## 现状问题

| 问题 | 现状 | 后果 |
|---|---|---|
| 日志非结构化 | `run_service` 里 `logging.exception("run %s 执行失败", run_id)`,run_id 混在消息文本里 | 没法按字段检索/聚合,喂不进日志平台 |
| 无样本耗时日志 | `_process_item` 算了 latency_ms 但只落库,不打日志 | 不知道哪个样本慢、慢在哪 |
| 无指标趋势 | 有 CompareView(勾选 N 个 run **横向**对比),无**单指标随时间/序列的折线** | 答不了「升还是降」 |
| 无导出 | 数据困在 DB / 前端 | 没法拿出去做外部分析 |

## 设计

### 1. 结构化日志

- **格式**:`JsonFormatter`,每行一条 JSON:`{ts, level, logger, event, 关键字段..., exc}`。机器可解析,可喂 ELK/Loki。
- **关键字段**(通过 `extra` 传入):`run_id`、`trace_id`、`latency_ms`(样本耗时)、`duration_ms`(run 总耗时)、`attempt`(重试次数)。
- **范围**:只配置 `backend` 命名空间的 logger,`propagate=False`,**不碰 uvicorn/celery 自己的 logger**(避免重复输出/格式打架)。
- **接入点**:`main.py` lifespan(FastAPI 进程)+ `celery_app.run_task`(worker 进程),`setup_logging()` 幂等。
- **关键日志点**:run 开始/完成/失败(带 run_id + duration)、每样本完成(带 trace_id + latency)、LLM 重试(带 attempt)。

### 2. 历史指标趋势

- **后端**:`GET /runs/trend` 批量聚合最近 N 个 run 的「per-metric 均值」,一次查询完成(前端逐 run 拉是 N+1)。
- **前端**:新 `TrendView`,recharts 折线图——X 轴 = run 序列(按时间),Y = 分数,下拉切换指标。直接回答「升还是降」,是版本对比的雏形。
- **注意**:`/runs/trend` 必须注册在 `/runs/{run_id}` **之前**,否则 `trend` 会被当成 run_id 解析成 422。

### 3. 指标导出(CSV)

- **后端**:`GET /runs/{run_id}/export` → CSV 下载,每行一个 trace,列 = input / output / latency_ms + 各指标分。
- **前端**:RunDetailView 加「导出」按钮。
- **理由**:CSV 是「外部分析」最友好的格式(Excel 直接开),JSON 趋势接口本身已可导出。

## 关键决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 日志范围 | 只配 `backend` logger | 不抢 uvicorn/celery 的日志配置,职责清晰 |
| 日志格式 | JSON lines | 结构化、机器可解析,后续接日志平台零改造 |
| 结构化方式 | `extra={"run_id": ...}` | 比 f-string 拼字段更规范,字段独立可检索 |
| 趋势数据 | 新批量接口 `/runs/trend` | 避免前端 N+1;聚合逻辑集中在 stats |
| 趋势图 | 折线 LineChart,单指标可切 | 正是「升还是降」的最直观表达 |
| 导出格式 | CSV(逐 trace) | Excel 可开,外部分析最友好 |

## 需要改动(实现时细化)

1. `backend/logging_config.py`(新):`JsonFormatter` + `setup_logging()`。
2. `backend/main.py`:lifespan 调 `setup_logging()`;加 `/runs/trend`(注意顺序)+ `/runs/{id}/export`。
3. `backend/celery_app.py`:`run_task` 里调 `setup_logging()`。
4. `backend/run_service.py`:`logger = getLogger(__name__)`,run 开始/完成/失败 + 每样本完成日志。
5. `backend/llm.py`:重试时 `logger.warning(..., extra={"attempt": ...})`。
6. `backend/stats.py`:`runs_trend(limit)` 批量聚合。
7. 前端:新 `TrendView`(折线图)+ 路由/菜单;RunDetailView「导出」按钮;`api`/`types` 补类型。
8. 测试:趋势聚合、导出 CSV、日志 formatter。

## 本章不做

- 分布式链路追踪(OpenTelemetry / Jaeger)——Ch13 只做结构化日志,追踪是更重的主题。
- 日志集中存储/检索(ELK / Loki)。
- 指标告警 / 回归门禁。
