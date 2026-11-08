# 残留 run 回收（心跳 + 进度）实施计划

## 背景(对应 spec)

`docs/superpowers/specs/2026-10-19-stale-run-recovery-design.md`

## 任务清单

### Task 1:数据模型与迁移

- [x] `Run.last_heartbeat_at`、`Run.last_progress_at`（均 String，可空）。
- [x] 迁移 `e5a9c1b7d2f3`（heartbeat）、`f0b1c2d3e4a5`（progress）。
- [x] `init_db()` 启动时自动 upgrade；dev 库已验证到 head。

### Task 2:worker 心跳

- [x] `_RunHeartbeat`：daemon 线程，每 10s 原子更新 `last_heartbeat_at`。
- [x] `execute_run` 开始即写一次心跳（覆盖启动窗口），`finally` 停止线程。
- [x] 开始时写 `last_progress_at`；每次 `_bump_progress` 同时刷新两个时间。
- [x] 心跳写失败只记 warning，不影响评测主流程。

### Task 3:回收判定

- [x] `_recover_stale_runs()`：心跳和进度**都**超时才标 failed。
- [x] 老库回退 `created_at`。
- [x] 配置 `STALE_RUN_TIMEOUT=180`、`STALE_RUN_PROGRESS_TIMEOUT=1800`。

### Task 4:测试

- [x] 新增 `tests/test_stale_runs.py`：新鲜心跳存活、心跳过期、心跳新鲜但进度过期、
      无心跳回退 created_at、done 不受影响。
- [x] 更新 `test_recover_stale_runs`（旧语义）与 `test_execute_run_done`（断言心跳写入）。
- [x] `pytest -q`：**116 passed**。

### Task 5:端到端验证

- [x] run #26（知识缺口）：执行期间手动调用 `_recover_stale_runs()`，run 保持 running，
      最终 done；心跳时间已落库。
- [x] run #28（v3 全量）：同样在运行中调用回收，run 保持 running（验证双信号）。
- [ ] run #28 跑完后记录最终状态（本轮收尾）。

### Task 6:文档同步

- [x] spec / plan 落盘。
- [x] 旧 plan（`2026-10-18-rejection-dual-signal-and-gold.md`）的「已知问题」标记为已解决。

## 验收对照

| spec 验收项 | 结果 |
|---|---|
| 心跳 + 进度新鲜 → 存活 | ✅ 单测 + run #26/#28 实测 |
| 心跳过期 → failed | ✅ |
| 心跳新鲜但进度过期 → failed | ✅ |
| 无心跳回退 created_at | ✅ |
| done/failed 不受影响 | ✅ |
| 端到端运行中回收不误杀 | ✅ |
| 后端测试全绿 | ✅ 116 passed |

## 限制

- 回收只在 API 启动时执行；API 长期不重启时卡住的 run 不会被自动回收，
  后续可加周期性 watchdog。
