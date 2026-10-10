# EvalFlow Ch11 设计:LLM 调用可靠性(重试 + 熔断 + judge 校准)

## 目标

Ch10 解决了「执行模型」(队列化 + 并发),但每一次 LLM 调用本身还是脆的:DeepSeek 偶发超时 / 429 限流 / 5xx,当前 `chat()` / `chat_json()` 都是一次性调用,挂了就挂。

Ch11 给 LLM 调用装上可靠性三件套:**重试**(瞬时故障自愈)、**熔断**(服务挂了快速失败、别烧钱)、**judge 校准**(多次采样让分数更稳),并明确**降级**语义(LLM 不可用时 run 失败得有原因,不卡住)。

## 现状问题

| 问题 | 现状 | 后果 |
|---|---|---|
| 无重试 | `llm.chat`/`chat_json` 单次调用 | 一次超时/429 → 该样本直接失败,run 置 failed |
| 无熔断 | 每次请求都真实打到 DeepSeek | LLM 持续故障时,每个 run 都反复重试、烧钱、雪上加霜 |
| judge 单次打分 | `_judge` 只调一次 `chat_json` | 偶发输出异常 → judge 记 NULL,分数抖动 |
| 失败无原因 | 异常一路往上抛/被吞 | 排查不知道是超时、限流还是鉴权错 |

## 设计

### 1. 重试(指数退避 + 抖动)

`llm.py` 底层加一个 `_create_with_retry()` 统一出口,`chat` / `chat_json` 都走它。

- **可重试**:网络层异常(超时 `APITimeoutError`、连接 `APIConnectionError`)+ 服务端瞬时错误(429 限流、5xx)。
- **不可重试**:4xx(鉴权/参数错)——重试一万次也没用,直接抛。
- **退避**:`base * 2^attempt` + 随机抖动,避免多个并发请求同时重试的「惊群」。
- **次数**:`chat_retries=3`(最多 4 次尝试)。

### 2. 熔断(Circuit Breaker)

`llm.py` 里一个 `CircuitBreaker` 状态机 + 模块级单例,所有 LLM 调用共享:

```
closed ──连续失败达阈值──▶ open ──冷却时间到──▶ half-open ──探测成功──▶ closed
                              │                        │
                              │                   探测失败
                              └────────重新 open◀──────┘
```

- **closed**:正常调用,记录连续成功/失败。
- **open**:直接抛 `CircuitOpenError`(快速失败,不打 LLM),冷却 `chat_circuit_cooldown=30s`。
- **half-open**:放一个探测请求,成功 → closed(重置计数),失败 → 重新 open。
- **阈值**:连续失败 `chat_circuit_failures=5` 次触发。

**熔断 vs 重试的关系**:重试在熔断**之内**——每次真正调 LLM 前先过熔断闸门,失败记入熔断器。单个请求自身重试 3 次(4 次失败)还不到阈值 5,所以熔断是「**多个请求连续失败**」的累计触发,不是单请求重试触发。

### 3. judge 校准(多次采样取均值)

`_judge` 里采样 `judge_samples` 次(默认 **1**,可调 3),取有效 score 的均值,reason 取第一次有效结果。

- 采样是「多次独立打分取平均」,对抗偶发输出抖动;**单次调用失败的重试**由第 1 节的重试机制覆盖——两层各管各的。
- 默认 1 保持成本不变;需要更稳时调 `judge_samples=3`(用钱换稳定性)。
- 全部采样失败 → 返回 None → 记 NULL(延续 Ch02「judge 挂记 NULL 不记 0」)。

### 4. 降级语义

- **生成 `chat()` 失败**(重试耗尽 / 熔断打开)→ 异常上抛 → `execute_run` 捕获 → run **failed**,`logging.exception` 已记录具体原因(Ch10 修过)。
- **judge `chat_json()` 失败** → `_judge` 捕获 → 返回 None → 该条 score 记 NULL,**不拖垮 run**(延续 Ch02 语义)。
- **熔断打开** → 抛 `CircuitOpenError`,调用方立刻失败、明确原因,而不是干等超时。

## 关键决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 重试范围 | 只重试网络异常 + 429 + 5xx;4xx(除 429)不重试 | 4xx 是请求本身错,重试无意义;429/5xx 是服务端瞬时问题 |
| 重试策略 | 指数退避 + 抖动,base 0.5s,max 3 次 | 抖动错峰,避免并发重试惊群 |
| 熔断粒度 | 全局单例(所有 LLM 调用共享) | 只有一个 chat 模型/endpoint,全局合理;按模型分熔断是过度设计 |
| 熔断触发 | 连续失败 5 次,冷却 30s,half-open 探测 | 防止 LLM 挂后持续打、烧钱;half-open 自动恢复 |
| judge 校准 | `judge_samples` 采样取均值,默认 1 | 默认 1 保持成本;可调 3 换稳定性 |
| 降级 | chat 失败→run failed;chat_json 失败→judge NULL | 生成必须成功,judge 可缺失(延续 Ch02) |

## 需要改动(实现时细化)

1. `backend/config.py`:加 `chat_retries` / `chat_retry_base` / `chat_circuit_failures` / `chat_circuit_cooldown` / `judge_samples`。
2. `backend/llm.py`:加可重试异常集合、`CircuitBreaker`、`CircuitOpenError`、`_create_with_retry()`;`chat`/`chat_json` 改走它。
3. `backend/evaluators.py`:`_judge` 加 `judge_samples` 采样取均值。
4. 测试:新增 `tests/test_llm.py`(重试/不可重试不重试/熔断开闭/冷却恢复)+ judge 采样测试。
5. `.env.example`:补新配置项。

## 本章不做

- 按模型/endpoint 分熔断器(单模型不需要)。
- 重试的「最大总耗时」预算、更精细的抖动算法(当前 base+抖动够用)。
- 异步 LLM 调用(IO 线程池已够,不在本章范围)。
