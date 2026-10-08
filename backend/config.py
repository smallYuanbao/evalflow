from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/eval.db"
    chat_model: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
