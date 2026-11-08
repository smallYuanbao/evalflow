# 残留 run 回收：心跳 + 进度双超时

## 背景

旧实现 `_recover_stale_runs()` 在 API 启动时把**所有** `running` 的 run 标成 failed。两个实际问题：

1. **误杀执行中的 run**：API 用 `--reload` 时，改任何文件都会触发 lifespan。
   2026-10-18 实测：写文档触发 reload，worker 仍在执行的 run #25 被临时标成
   failed（跑完后又被 `_mark("done")` 覆盖）。
2. **真正的残留无法区分**：worker 失去 broker 连接后任务卡在 redis，run 永远
   `progress=0`；但在 API 不重启的情况下，旧逻辑也不会回收。

## 设计

### 两个信号

| 信号 | 写入方 | 含义 | 超时阈值 |
|---|---|---|---|
| `last_heartbeat_at` | worker 心跳线程，每 10s | 进程还活着 | `stale_run_timeout=180s` |
| `last_progress_at` | 每个样本完成时 + 开始执行时 | 还在产出结果 | `stale_run_progress_timeout=1800s` |

**只有两个信号都超时才回收**：

```python
if heartbeat_ok and progress_ok:
    continue
run.status = "failed"
```

为什么需要两个：

- 只有心跳：worker 主流程卡死（死锁/无限等待）时，心跳线程仍可能在跑，
  run 永远不会被回收；
- 只有进度：单条样本要跑「检索 + 生成 + 5 个 judge」，可能几分钟没有进度变化，
  会把活着的 run 误杀。

### 兜底

老库/新建 run 还没有心跳值时，用 `created_at` 作为两个信号的 fallback。
时间戳格式与 `models._now()` 一致（本地时间、秒级 ISO 字符串）。

### 执行位置

- 回收仍在 **API 启动的 lifespan** 里执行；阈值判定保证不会误杀。
- 心跳线程只存在于 worker 的 `execute_run` 期间，daemon 线程，`finally` 停止。

## 数据库变更

两个迁移：

1. `e5a9c1b7d2f3`：`runs.last_heartbeat_at VARCHAR NULL`
2. `f0b1c2d3e4a5`：`runs.last_progress_at VARCHAR NULL`

## 配置

| 配置 | 默认 | 说明 |
|---|---|---|
| `STALE_RUN_TIMEOUT` | 180 | 心跳超时（秒） |
| `STALE_RUN_PROGRESS_TIMEOUT` | 1800 | 进度超时（秒） |

## 验收标准

1. 心跳新鲜 + 进度新鲜 → API 重启后仍是 running。
2. 心跳过期 → failed。
3. 心跳新鲜但进度超过 30 分钟不动 → failed（覆盖「进程活着但卡死」）。
4. 没有心跳值 → 回退 created_at 判定。
5. done / failed 的 run 不受影响。
6. 端到端：run 执行期间手动调用 `_recover_stale_runs()`，run 仍为 running 并最终 done。
7. 全部后端测试通过。

## 风险与限制

- **回收只在 API 启动时触发**：API 长时间不重启时，卡住的 run 会一直显示 running，
  直到下次重启。后续可加周期性回收（如 APScheduler 或独立 watchdog）。
- **启动瞬间的排队 run**：如果 redis 队列堵塞、worker 没取到任务，run 没有心跳，
  180s 后会被判 failed。这是期望行为（说明它确实没在跑），但需要知道阈值。
- **心跳写入与评测写库并发**：SQLite 已开 WAL + busy_timeout；心跳失败只记 warning，
  下一轮重试，不影响主流程。
