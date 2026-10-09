import chromadb

from backend.embedding import embed
from backend.knowledge import KNOWLEDGE

_client = chromadb.PersistentClient(path="data/chroma")


def _coll():
    # cosine:ChromaDB 默认 L2,显式配余弦;distance 越小越相似
    return _client.get_or_create_collection("knowledge", metadata={"hnsw:space": "cosine"})


def ingest() -> None:
    """把知识库嵌入并灌进 ChromaDB(幂等:upsert 按 id 覆盖)。"""
    coll = _coll()
    coll.upsert(
        ids=[k["id"] for k in KNOWLEDGE],
        embeddings=embed([k["text"] for k in KNOWLEDGE]),
        documents=[k["text"] for k in KNOWLEDGE],
        metadatas=[{"category": k["category"]} for k in KNOWLEDGE],
    )


def retrieve(query: str, top_k: int = 2) -> list[dict]:
    """真实向量检索:query 嵌入 → ChromaDB 余弦 top-k,返回 [{text, score}]。"""
    coll = _coll()
    if coll.count() == 0:
        ingest()
    res = coll.query(
        query_embeddings=[embed([query])[0]],
        n_results=top_k,
        include=["documents", "distances"],
    )
    docs = res["documents"][0]
    dists = res["distances"][0]
    # cosine distance = 1 - 余弦相似度,所以 score = 1 - distance
    return [{"text": t, "score": round(1 - d, 4)} for t, d in zip(docs, dists)]
