# EvalFlow Ch12 设计:安全与成本(鉴权 + 限流 + 费用统计)

## 目标

Ch11 解决了「LLM 调用的可靠性」,但平台现在**任何人只要连上端口就能发起评测烧真金白银**,而且**跑了多少次、花了多少钱完全没数**。

Ch12 补上三块:API Key 鉴权(无 key 拒绝)、限流(防刷评测)、费用统计(每样本 token/成本 → run 汇总)。

## 现状问题

| 问题 | 现状 | 后果 |
|---|---|---|
| 无鉴权 | `main.py` 所有路由裸奔 | 匿名用户可无限发起评测,烧 DeepSeek API 费用 |
| 无限流 | `create_run` 无频率限制 | 脚本可瞬间刷 N 个 run,账单爆炸 |
| 无费用统计 | `Generation` 表建了但从未写入 | 不知道每次 run 花多少 token、多少钱 |

## 设计

### 1. API Key 鉴权

- **配置**:`app_api_key: str = ""`。空 = 不启用鉴权(本地 dev / 测试向后兼容);非空 = 强制鉴权。
- **方式**:HTTP 中间件校验 `Authorization: Bearer <key>`,与调 DeepSeek 的 `CHAT_API_KEY` 是两回事(一个是「访问平台」的钥匙,一个是「平台调 LLM」的钥匙)。
- **豁免**:`/health`(健康检查)与 `OPTIONS`(CORS 预检)不鉴权。
- **前端**:密钥存 `localStorage`,axios 请求拦截器统一注入 header;提供一个密钥输入入口。

### 2. 限流(防刷)

- **范围**:只限 `create_run`(唯一的烧钱操作),只读接口不限。
- **实现**:内存滑动窗口(`backend/ratelimit.py`),单进程内存即可——`create_run` 只在 FastAPI 进程处理,不涉及 Celery worker。
- **配置**:`rate_limit_runs_per_minute: int = 10`(每分钟最多 10 次发起评测),超限返回 429。

### 3. 费用统计

- **计量**:`llm.py` 用**线程局部累计器**记每次调用的 token(`usage.prompt_tokens` / `completion_tokens`)。因为 Ch10 已把每个样本丢进独立线程,线程局部天然隔离、互不干扰。
- **写入**:`_process_item` 开头 `reset_usage()`,跑完「生成 + 5 judge」后 `get_usage()` 取本样本累计 token,写一条 `Generation`(model + input/output tokens + cost)。
- **价格**:可配 `chat_price_input_per_1m` / `chat_price_output_per_1m`(元/百万 token),默认给 deepseek-chat 参考价(实际以官方为准)。
- **汇总**:`aggregate_run` 累加该 run 所有 Generation 的 token/cost,前端 RunDetail 展示总费用 + 总 token。

## 关键决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 鉴权粒度 | 单用户单 key(`app_api_key`) | roadmap 明确 Ch12 只做单用户,先解决「防匿名烧钱」,多租户/角色不做 |
| key 传递 | `Authorization: Bearer` + localStorage | 标准做法,前端拦截器统一注入,不用每个请求手写 |
| 限流对象 | 只限 `create_run` | 烧钱的是发评测;只读接口限流无意义 |
| 限流实现 | 内存滑动窗口 | 单进程够用;Redis 分布式限流是 Ch14 之后的事 |
| token 计量 | 线程局部累计器 | `chat`/`chat_json` 签名不变,调用方零改动;线程局部契合 Ch10 每样本一线程 |
| 价格表 | 可配,默认 deepseek 参考价 | 价格会变,且换模型价格不同,必须可配不硬编码 |

## 需要改动(实现时细化)

1. `backend/config.py`:加 `app_api_key`、`rate_limit_runs_per_minute`、`chat_price_input_per_1m`、`chat_price_output_per_1m`。
2. `backend/main.py`:加鉴权中间件;`create_run` 接入限流。
3. `backend/ratelimit.py`(新):滑动窗口限流器。
4. `backend/llm.py`:加线程局部 token 计量(`reset_usage`/`get_usage`/`_add_usage`)。
5. `backend/run_service.py`:`_process_item` 写 `Generation`。
6. `backend/stats.py`:`aggregate_run` 汇总 token/cost。
7. 前端:密钥入口 + 请求注入 header + RunDetail 展示费用。
8. 测试:鉴权 401/200、限流 429、费用写入与汇总。

## 本章不做

- 多租户 / 角色权限(单用户够)。
- 分布式限流(Redis)、按用户/IP 的差异化限额。
- 真实计费/账单系统(只做统计展示,不接支付)。
