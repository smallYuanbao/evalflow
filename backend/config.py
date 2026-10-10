from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/eval.db"
    chat_model: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_timeout: float = 60.0  # LLM 调用超时(秒):防 DeepSeek 卡住导致 run 永久 running
    embed_base_url: str = "http://localhost:11434"  # Ollama(embedding 模型服务)
    embed_model: str = "bge-m3"                     # 本机已下载的 embedding 模型
    chroma_host: str = ""                           # 容器化:独立 chroma 服务地址;空 = 本地 PersistentClient
    chroma_port: int = 8000                         # chroma 服务端口
    redis_url: str = "redis://localhost:6379/0"     # Celery broker/backend(评测任务队列)
    run_concurrency: int = 4                        # 单个 run 内样本并发数(LLM 是 IO 密集,线程合适)

    model_config = {"env_file": ".env"}


settings = Settings()
