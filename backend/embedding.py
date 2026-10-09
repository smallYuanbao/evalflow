import requests

from backend.config import settings


def embed(texts: list[str]) -> list[list[float]]:
    """调用 Ollama 的 bge-m3 生成向量(参照 baby-ai 的 get_embedding)。"""
    r = requests.post(
        f"{settings.embed_base_url}/api/embed",
        json={"model": settings.embed_model, "input": texts},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embeddings"]
