# EvalFlow 踩坑记录总览

> 前端转 AI 应用工程师路上的真实踩坑合集。每条按「现象 → 根因 → 修法 → 原理」记,对应到具体章节和代码,遇到同类问题回来查。

## 按章节

- [Ch01 数据地基](ch01-data-foundation.md) —— SQLite 外键默认关 / 不自动建目录 / 跨线程 / NULL vs 0
- [Ch02 评测主流程](ch02-evaluation-run.md) —— judge 温度 0 / NULL 语义 / recall 措辞对齐 / 库外题
- [Ch03 前端](ch03-frontend.md) —— Node 版本 / jsdom stub / N+1 / LLM 超时 / 迁移 / StrictMode / 测试 type-check
- [Ch04 向量检索](ch04-vector-retrieval.md) —— onnxruntime 版本 pin / cosine / Ollama 依赖
- [Ch05-07 指标·对比·前端增强](ch05-ch07-metrics-frontend.md) —— NULL 聚合 / config 回退
- [Ch08 部署](ch08-deployment.md) —— 模块级 mock 约束 / host.docker.internal / 密钥不进镜像
- [Ch09 可复现](ch09-reproducibility.md) —— 老 run 向后兼容
- [Ch10 任务队列](ch10-task-queue.md) —— 写锁跨 LLM / DetachedInstanceError / uv / worker 热重载 / 吞异常
- [Ch11 LLM 可靠性](ch11-llm-reliability.md) —— openai 异常构造 / before_call 放 try 外 / 4xx 不算故障 / 熔断 vs 重试 / 测试 mock 时钟
- [Ch12 安全与成本](ch12-security-cost.md) —— 中间件顺序(401 带 CORS) / 线程复用要 reset / usage 空值兜底 / 滑动窗口语义 / import 固化配置
- [Ch13 可观测性](ch13-observability.md) —— 路由顺序(静态 vs 动态) / DetachedInstanceError 复发 / CSV 要 BOM / setup_logging 幂等
- [Ch14 交付硬化](ch14-delivery-hardening.md) —— e2e 端口隔离 / antd Select placeholder / 空态隐藏按钮 / vitest 误拾取 / nginx 启动期解析
- [Ch21 接口性能](ch21-performance.md) —— 请求内全表扫描 + 无缓存致超时 / 函数内改全局忘写 global
- [Ch25 数据规模与流式](ch25-scale-and-streaming.md) —— 两端各缓冲 2~3 份 / 绕开浏览器原生下载
- [Ch27 机械启发式的脆性](ch27-heuristic-brittleness.md) —— 关键词表在自己的数据上完美 / 失效静默

## 按主题速查

| 主题 | 章节 |
|---|---|
| SQLite / 数据库 | Ch01、Ch03(迁移)、Ch10(写锁竞争) |
| SQLAlchemy ORM | Ch10(DetachedInstanceError)、Ch13(复发) |
| LLM 调用 | Ch02(温度/NULL)、Ch03(超时)、Ch10(写锁跨 LLM)、Ch11(重试/熔断)、Ch12(usage 计量) |
| 前端测试 jsdom | Ch03(matchMedia / ResizeObserver) |
| React 陷阱 | Ch03(StrictMode 双跑)、Ch14(空态提前 return 藏按钮) |
| 依赖 / 环境 | Ch03(Node 版本)、Ch04(onnxruntime)、Ch10(uv 无 pip) |
| Docker 部署 | Ch08、Ch14(nginx 静态 upstream 启动期解析) |
| e2e / Playwright | Ch14(端口隔离 / reuseExistingServer / antd Select placeholder) |
| 测试工具边界 | Ch14(vitest 误拾取 e2e 用例) |
| 鉴权 / 限流 / 费用 | Ch12(中间件顺序 / 滑动窗口 / token 计量) |
| 可观测性 / 路由 / 编码 | Ch13(路由顺序 / CSV BOM / 日志幂等) |
| 性能 / 缓存 | Ch21(全表扫描 / 静态数据缓存 / 有界查询) |
| 数据规模 / 流式 | Ch25(整份缓冲 / 绕开浏览器原生下载) |
| 评测指标本身 | Ch27(机械启发式对措辞脆 / 自测自欺) |
| Python 作用域 | Ch21(函数内改模块级变量要 global) |

## 几条反复出现的底层规律

1. **事务要短**——IO/LLM 调用绝不能放进 DB 事务里(Ch10 坑 1 的根)。
2. **进程/线程边界**——跨 session 只传普通值、改代码重启 worker、catch 必 log(Ch10 坑 2/4/5)。
3. **「没评上」≠「零分」**——用 NULL 区分,聚合时跳过,别让失败样本污染均值(Ch01/Ch02)。
4. **确定性任务关随机性**——judge 温度 0、拒答用机械关键词,能机械的就别上 LLM(Ch02)。
5. **环境/版本要显式**——依赖 pin 版本、Node 选对版本、onnxruntime 按架构 pin(Ch03/Ch04)。
6. **测试/部署上下文要隔离**——e2e 别复用旧服务、两套测试框架划清边界、容器反代只在 compose 网络里成立(Ch14)。
7. **不变的量算一次就够**——静态数据缓存住、可视化别喂全量、性能先量后猜(Ch21)。
8. **规模不受控就别「攒齐再交付」**——导出/批量/大列表一律流式,平台给的原生能力别绕开(Ch25)。
9. **别用自己的数据测自己的规则**——规则与数据同源就测不出覆盖不足;启发式失效往往静默,要人工抽查或换数据源(Ch27)。
