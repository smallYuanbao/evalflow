from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/eval.db"
    chat_model: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_timeout: float = 60.0  # LLM 调用超时(秒):防 DeepSeek 卡住导致 run 永久 running
    embed_base_url: str = "http://localhost:11434"  # Ollama(embedding 模型服务)
    embed_model: str = "bge-m3"                     # 本机已下载的 embedding 模型

    model_config = {"env_file": ".env"}


settings = Settings()
