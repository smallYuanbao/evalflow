from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/eval.db"
    chat_model: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_timeout: float = 60.0  # LLM 调用超时(秒):防 DeepSeek 卡住导致 run 永久 running
    embed_base_url: str = "http://localhost:11434"  # Ollama(embedding 模型服务)
    embed_model: str = "bge-m3"                     # 本机已下载的 embedding 模型
    embed_timeout: int = 120                        # embedding 请求超时(秒);冷启动 + 批量时留足余量
    chroma_host: str = ""                           # 容器化:独立 chroma 服务地址;空 = 本地 PersistentClient
    chroma_port: int = 8000                         # chroma 服务端口
    redis_url: str = "redis://localhost:6379/0"     # Celery broker/backend(评测任务队列)
    run_concurrency: int = 4                        # 单个 run 内样本并发数(LLM 是 IO 密集,线程合适)
    # —— Ch11 LLM 可靠性 ——
    chat_retries: int = 3                 # 可重试错误(超时/429/5xx)的重试次数,最多 4 次尝试
    chat_retry_base: float = 0.5          # 指数退避基数(秒):0.5/1/2/4... + 抖动
    chat_circuit_failures: int = 5        # 熔断阈值:连续失败 N 次打开熔断
    chat_circuit_cooldown: float = 30.0   # 熔断冷却(秒):冷却后 half-open 探测
    judge_samples: int = 1                # judge 采样次数(>1 取均值更稳,成本×N)
    # —— Ch12 安全与成本 ——
    app_api_key: str = ""                 # 平台访问密钥(空 = 不鉴权,本地 dev/测试兼容)
    rate_limit_runs_per_minute: int = 10  # create_run 限流:每分钟最多发起评测次数(防刷烧钱)
    chat_price_input_per_1m: float = 2.0  # 输入价(元/百万 token)。deepseek-chat 参考价,按官方实际调
    chat_price_output_per_1m: float = 8.0 # 输出价(元/百万 token)。deepseek-chat 参考价,按官方实际调
    # —— Ch14 交付硬化 ——
    e2e_mock: bool = False  # E2E 开关:替换 run_pipeline/judge 为确定性假实现,并同步执行(不走 celery)
    # —— Ch26 评测外部系统 ——
    eval_target: str = "local"                      # local=自己的 toy pipeline;babyai=HTTP 调 baby-ai
    babyai_base_url: str = "http://localhost:3001"  # baby-ai 的 python-server 地址
    babyai_timeout: int = 120                       # baby-ai 单次问答超时(秒);它要跑检索+精排+生成,给足
    babyai_max_rpm: int = 8                         # 自我限流:每分钟最多打多少次(被测系统是 10/min,留余量)
    # —— Ch30 裁判独立配置 ——
    # 留空 = 回退到 CHAT_*(兼容旧行为)。**单独配裁判是为了能做 A/B 和交叉验证**:
    # Ch28 实测「换裁判让 context_recall 差 0.31,而门禁容忍度只有 0.05」——
    # 裁判模型本身就是个变量,必须能单独换、并且记进快照。
    judge_base_url: str = ""
    judge_api_key: str = ""
    judge_model: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
