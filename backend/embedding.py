import requests

from backend.config import settings


def embed(texts: list[str]) -> list[list[float]]:
    """调用 Ollama 的 bge-m3 生成向量(参照 baby-ai 的 get_embedding)。

    超时可配(默认 120s):Ollama 冷启动要先把模型载入内存,批量文本也要时间,
    60s 在「冷启动 + 大批量」时会误报超时(Ch21)。
    """
    r = requests.post(
        f"{settings.embed_base_url}/api/embed",
        json={"model": settings.embed_model, "input": texts},
        timeout=settings.embed_timeout,
    )
    r.raise_for_status()
    return r.json()["embeddings"]
