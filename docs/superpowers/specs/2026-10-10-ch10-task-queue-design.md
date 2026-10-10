# EvalFlow Ch10 设计:评测任务队列化(Celery + Redis)

## 目标

Ch09 解决了「可复现」,但执行模型还是硬伤:`execute_run` 跑在 FastAPI `BackgroundTasks`(进程内)上,`for it in items` 串行执行——7 条样本要 ~50 次 LLM 调用一条条排队,而且**进程一重启,`running` 的 run 永久卡死**。

Ch10 把执行模型升级为「Celery 队列 + worker 并发」:请求入队立即返回,worker 后台并发跑,进度可见,重启后状态不永久卡死。

## 现状问题

| 问题 | 现状 | 后果 |
|---|---|---|
| 任务在进程内 | `create_run` 用 `BackgroundTasks` | FastAPI 重启 → 任务丢、run 永久 running |
| 串行执行 | `execute_run` `for it in items` | 每样本 1 生成 + 5 judge ≈ 6 次 LLM,串行极慢 |
| 无进度 | 只有 running/done/failed | 前端只能干等,不知道跑到第几条 |
| 无恢复兜底 | running 卡死没人管 | 重启后脏状态 |

## 架构

```
前端 ──POST /runs──▶ FastAPI(create_run)
                        │ run_task.delay(run_id)  ← 入队即返回
                        ▼
                   Redis(broker)
                        ▼
                 Celery worker(--pool=threads, 并发 N)
                        │ 消费 task → execute_run(run_id)
                        ▼
                样本并发(ThreadPoolExecutor)+ 逐条写 Trace/Score + 更新 progress
                        ▼
                   SQLite(WAL)+ Chroma + LLM
```

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 队列 | **Celery + Redis** | 面试标准答案(「异步任务怎么做的」);本机已装 redis-server;生产级正解。轻量自研队列是反模式 |
| 并发模型 | worker `--pool=threads`(单进程多线程)+ run 内 `ThreadPoolExecutor` | LLM 调用是 IO 密集,线程合适;单进程多线程避免 SQLite 多进程写锁(Ch14 换 PostgreSQL 才放开多进程) |
| SQLite 并发 | WAL 模式 + `busy_timeout=5000` | 单进程多线程下 WAL 允许读写并发;busy_timeout 让写锁等待而非直接 `database is locked` |
| 任务拆分 | `execute_run` 保持**纯函数**(可测),`celery_app.run_task` 薄包装入队 | 测试不依赖 redis/worker;职责清晰(纯逻辑 vs 任务编排) |
| 进度 | `runs` 表加 `progress` 字段(已完成样本数) | 前端轮询可见;复用已有 `_migrate` 加列不破坏旧库 |
| 状态恢复 | 启动时扫描 `running → failed` 兜底 + Celery `acks_late`(worker 崩溃消息重投) | 简单可靠;「断点续跑」留后续 |
| 测试 | 单元测试 mock `run_task.delay` 为同步执行 | 不依赖 redis/worker,保持现有测试风格 |

## 需要改动(实现时细化)

1. `pyproject.toml`:加 `celery[redis]>=5.4.0`。
2. `backend/config.py`:加 `redis_url`(默认 `redis://localhost:6379/0`)、`run_concurrency`(默认 4)。
3. `backend/celery_app.py`(新):Celery 实例(broker/backend = redis_url,`acks_late=True`)+ `run_task(run_id)` 薄包装。
4. `backend/run_service.py`:拆成 `execute_run`(调度:并发 + 进度 + 状态)+ `_process_item`(单样本:检索/生成/评测/写库)。
5. `backend/main.py`:`create_run` 用 `run_task.delay(rid)` 替代 BackgroundTasks;lifespan 加启动恢复。
6. `backend/db.py`:connect 事件加 `PRAGMA journal_mode=WAL` + `busy_timeout`;`_migrate` 给 runs 加 progress。
7. `backend/models.py`:`Run` 加 `progress` 字段。
8. 前端:run 列表/详情展示进度(已完成/总数)。
9. `docker-compose.yml` + 后端 Dockerfile:加 redis + worker 服务。
10. 测试:更新 test_api(create_run 入队 mock)、test_run_service(并发/进度/失败),新增状态恢复。

## 本章不做

- 断点续跑(已完成样本跳过)、任务优先级/延迟队列、结果后端的高级查询。
- LLM 重试/熔断(Ch11)、PostgreSQL(Ch14)、鉴权限流(Ch12)。
