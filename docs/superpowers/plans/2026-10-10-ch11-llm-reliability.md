# EvalFlow Ch11 实施计划:LLM 可靠性(重试 / 熔断 / judge 校准)

## 背景(对应 spec)

给 `llm.chat` / `chat_json` 装重试 + 熔断,给 `_judge` 加采样校准。核心是把「一次性脆弱调用」升级为「瞬时故障自愈 + 服务挂掉快速失败 + 分数更稳」。

**关键现状(决定实现方式)**:
- `llm.py` 的 `chat`/`chat_json` 都直接调 `_client.chat.completions.create`,抽一个 `_create_with_retry()` 统一出口即可,改动集中。
- `evaluators._judge` 单次 `chat_json`,加采样循环。
- 测试全程 mock `_client.chat.completions.create`(或 `llm.chat_json`),**不碰真实 LLM、不依赖网络**,沿用现有 monkeypatch 风格。
- 熔断器是模块级单例,测试间要能重置状态(提供 `_reset()` 或用 monkeypatch 替换单例)。

## 任务清单

### Task 1:配置 + 重试(指数退避)

- [x] `backend/config.py`:加 `chat_retries=3`、`chat_retry_base=0.5`。
- [x] `backend/llm.py`:定义可重试异常集合(`APITimeoutError`/`APIConnectionError`/`RateLimitError`/`InternalServerError`),抽 `_create_with_retry()`(循环 `chat_retries+1` 次,指数退避 + 抖动,重试耗尽抛最后一个异常),`chat`/`chat_json` 改走它。

### Task 2:熔断器(Circuit Breaker)

- [x] `backend/config.py`:加 `chat_circuit_failures=5`、`chat_circuit_cooldown=30.0`。
- [x] `backend/llm.py`:加 `CircuitOpenError` + `CircuitBreaker`(closed/open/half-open 状态机 + `before_call`/`on_success`/`on_failure` + 冷却判断 + 模块级单例 + 测试用 `_reset()`);`_create_with_retry` 里每次真实调用前过 `before_call`、成功后 `on_success`、失败后 `on_failure`。

### Task 3:judge 采样校准

- [x] `backend/config.py`:加 `judge_samples=1`。
- [x] `backend/evaluators.py`:`_judge` 采样 `judge_samples` 次取有效 score 均值(全部失败返回 None)。

### Task 4:测试 + 文档收尾

- [x] 新增 `tests/test_llm.py`:
  - 重试:第一次抛超时、第二次成功 → 返回正确且调用 2 次。
  - 不可重试(4xx)不重试:调用 1 次即抛。
  - 重试耗尽:一直抛 → 最终抛异常。
  - 熔断:连续失败达阈值 → 后续直接抛 `CircuitOpenError`(不再调 create)。
  - 冷却恢复:half-open 探测成功 → 关闭。
- [x] `tests/test_evaluators.py`:judge 采样 `judge_samples=3` 取均值;全失败返回 None。
- [x] `.env.example`:补 5 个新配置项。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 重试(指数退避) | Task 1 + 4(重试/耗尽/不可重试) |
| 熔断(连续失败短路) | Task 2 + 4(开闭/冷却恢复) |
| judge 多次采样取均值 | Task 3 + 4 |
| 降级:失败有原因不卡住 | Task 1/2(`CircuitOpenError` + 重试耗尽抛异常) |

## 本章不做

- 按模型分熔断、异步 LLM、重试总耗时预算(spec 已列)。
