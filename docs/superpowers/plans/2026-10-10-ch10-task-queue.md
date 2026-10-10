# EvalFlow Ch10 实施计划:评测任务队列化(Celery + Redis)

## 背景(对应 spec)

把「进程内串行 BackgroundTasks」升级为「Celery 队列 + worker 并发」:入队即返回、样本并发、进度可见、重启不永久卡死。

**关键现状(决定实现方式)**:
- `execute_run` 是纯函数,现有 `test_run_service.py` 直接调用它——保持纯函数可测,`celery_app.run_task` 薄包装入队。
- `test_api.py` 用 TestClient 触发 `create_run`,原来靠 BackgroundTasks 同步执行——改 `run_task.delay` 后需 mock 成同步执行,测试不依赖 redis。
- `db.py` 已有 `_migrate` 加列机制,复用给 `runs` 加 `progress`;SQLite 已 `check_same_thread=False`,补 WAL + busy_timeout。
- 本机已装 `redis-server`;celery/redis 需 pip 装进 venv。

## 任务清单

### Task 1:依赖 + 配置 + Celery app

- [x] `pyproject.toml`:加 `celery[redis]>=5.4.0`,并 `pip install` 进 venv。
- [x] `backend/config.py`:加 `redis_url`(默认 `redis://localhost:6379/0`)、`run_concurrency`(默认 4)。
- [x] `backend/celery_app.py`(新):`Celery("evalflow", broker=redis_url, backend=redis_url)` + `acks_late=True` + `run_task(run_id)` 薄包装调用 `run_service.execute_run`。

### Task 2:execute_run 拆调度 + 单样本并发

- [x] `backend/run_service.py`:`execute_run` 改为「并发调度」——`ThreadPoolExecutor(max_workers=run_concurrency)` 并发跑 `_process_item`,主线程逐条收结果 + 更新 `progress`,全部完成置 done,任一异常置 failed。
- [x] 抽 `_process_item(run_id, item, top_k)`:单样本「检索 + 生成 + 评测 + 写 Trace/Score」,独立 SessionLocal(原 for 循环体迁入)。

### Task 3:进度字段 + create_run 入队 + 启动恢复

- [x] `backend/models.py`:`Run` 加 `progress = Column(Integer, default=0)`。
- [x] `backend/db.py`:connect 事件加 `PRAGMA journal_mode=WAL` + `busy_timeout=5000`;`_migrate` 给 runs 加 progress 列。
- [x] `backend/main.py`:`create_run` 用 `run_task.delay(rid)` 替代 `BackgroundTasks`;lifespan 启动时把 `running` 的 run 置 `failed`(兜底)。

### Task 4:前端展示进度

- [x] `frontend/src/types.ts`:`Run` 加 `progress?: number`(item_count 由 config 快照给,或用 run 表 total)。
- [x] `RunsView` / `RunDetailView`:状态为 running 时展示「已完成 N 条」进度。

### Task 5:Docker 编排 + 测试

- [x] `docker-compose.yml` + `backend/Dockerfile`:加 `redis` 服务与 `worker` 服务(同镜像跑 `celery worker`)。
- [x] 更新 `tests/test_api.py`:mock `run_task.delay` 为同步执行,保持接口断言。
- [x] 更新 `tests/test_run_service.py`:覆盖并发下进度 + 完成/失败状态(现有 4 个用例不破坏)。
- [x] 新增状态恢复断言(启动扫描 running → failed)。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| execute_run 入队由 worker 消费 | Task 1 + 3 |
| 样本并发执行(可配并发数) | Task 2(`run_concurrency`) |
| run 状态可恢复(重启不卡 running) | Task 3(lifespan 兜底) |
| 进度上报 | Task 2 + 3(progress)+ 4(前端) |
| 同时多 run 并发 + 杀进程重启状态正确 | Task 2 + 3 + 5(测试) |

## 本章不做

- 断点续跑、任务优先级、LLM 重试/熔断(Ch11)、PostgreSQL(Ch14)。
