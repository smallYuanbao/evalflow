# EvalFlow Ch12 实施计划:安全与成本(鉴权 / 限流 / 费用统计)

## 背景(对应 spec)

给平台加「访问鉴权 + 防刷限流 + 费用统计」三件套。核心是把「能烧钱但没数」变成「有钥匙才进、有限流兜底、花了多少一目了然」。

**关键现状(决定实现方式)**:
- `Generation` 表 Ch01 就建好了(`trace_id`/`model`/`input_tokens`/`output_tokens`/`cost`),一直没写入,Ch12 直接填充即可,无迁移。
- `llm.py` 的 `_create_with_retry` 是统一出口,在这里埋 token 计量,`chat`/`chat_json` 签名不变。
- `_process_item` 每样本一个线程(Ch10),线程局部累计器天然隔离。
- 前端 `client.ts` 已有 axios 拦截器,注入 key 加在 request 拦截器即可。

## 任务清单

### Task 1:API Key 鉴权

- [x] `backend/config.py`:加 `app_api_key: str = ""`(空 = 不启用,向后兼容 dev/测试)。
- [x] `backend/main.py`:加 `@app.middleware("http")` 鉴权——豁免 `/health` 与 `OPTIONS`,非空 key 时校验 `Authorization: Bearer <key>`,错/缺返回 401。
- [x] 前端:密钥存 localStorage,`client.ts` 请求拦截器注入 header;加一个密钥输入入口(Header 简单 Modal/Input)。
- [x] 测试:`test_api.py` 加「无 key 401 / 带 key 200 / health 豁免」。

### Task 2:限流(防刷)

- [x] `backend/config.py`:加 `rate_limit_runs_per_minute: int = 10`。
- [x] `backend/ratelimit.py`(新):滑动窗口限流器(`allow() -> bool`,窗口 60s)。
- [x] `backend/main.py`:`create_run` 开头调用限流,超限返回 429。
- [x] 测试:连续调用超限 → 429。

### Task 3:费用统计

- [x] `backend/config.py`:加 `chat_price_input_per_1m` / `chat_price_output_per_1m`(元/百万 token)。
- [x] `backend/llm.py`:线程局部 token 计量——`reset_usage()` / `get_usage()` / 在 `_create_with_retry` 成功时 `_add_usage(r.usage)`。
- [x] `backend/run_service.py`:`_process_item` 开头 reset、写 Trace 后取 usage 写 `Generation`(cost 按价格表算)。
- [x] `backend/stats.py`:`aggregate_run` 汇总该 run 的 input/output tokens 与 cost。
- [x] 前端 RunDetail:展示总 token + 总费用。
- [x] 测试:mock usage → Generation 写入正确;run 汇总 cost 正确。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 无 key 无法调用 | Task 1(中间件 + 测试) |
| 每次 run 能看到费用 | Task 3(Generation + 汇总 + 前端) |
| 防刷限流 | Task 2(create_run 429) |

## 本章不做

- 多租户/角色、分布式限流、真实计费系统(spec 已列)。
