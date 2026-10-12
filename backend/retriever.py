import chromadb

from backend.bm25 import BM25
from backend.config import settings
from backend.embedding import embed
from backend.knowledge import KNOWLEDGE


def _make_client():
    """容器化:设 CHROMA_HOST 走独立 chroma 服务(HttpClient);否则本地用文件(PersistentClient)。"""
    if settings.chroma_host:
        return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return chromadb.PersistentClient(path="data/chroma")


_client = _make_client()

# BM25 稀疏索引(Ch16):对同一份知识库建内存倒排,与 chroma dense 一路并列
_bm25 = BM25(KNOWLEDGE)


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


def _dense_hits(query: str, top_k: int) -> list[tuple[str, str, float]]:
    """dense 检索:query 嵌入 → ChromaDB 余弦 top-k,返回 [(id, text, 余弦相似度)]。"""
    coll = _coll()
    if coll.count() == 0:
        ingest()
    res = coll.query(
        query_embeddings=[embed([query])[0]],
        n_results=top_k,
        include=["documents", "distances"],  # ids 始终返回,不用 include
    )
    ids = res["ids"][0]
    docs = res["documents"][0]
    dists = res["distances"][0]
    # cosine distance = 1 - 余弦相似度,所以 score = 1 - distance
    return [(i, t, 1 - d) for i, t, d in zip(ids, docs, dists)]


def retrieve_dense(query: str, top_k: int = 2) -> list[dict]:
    """纯向量检索(dense-only):返回 [{text, score}],score 是余弦相似度。"""
    return [{"text": t, "score": round(s, 4)} for _, t, s in _dense_hits(query, top_k)]


def hybrid_retrieve(query: str, top_k: int = 2) -> list[dict]:
    """混合检索(Ch16):dense(语义)+ BM25(关键词)两路 RRF 融合,取 top-k。

    RRF(倒数排名融合):各通道按「排名」贡献 1/(k+rank),k=60。用排名而非原始分数,
    因为余弦(0~1)和 BM25(无上界)尺度不同、不能直接相加——这是尺度无关的融合法。
    """
    rrf: dict[str, float] = {}
    text_by_id: dict[str, str] = {}

    for rank, (cid, text, _s) in enumerate(_dense_hits(query, top_k), 1):
        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (60 + rank)
        text_by_id[cid] = text
    for rank, (cid, text, _s) in enumerate(_bm25.search(query, top_k), 1):
        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (60 + rank)
        text_by_id[cid] = text

    ranked = sorted(rrf.items(), key=lambda kv: -kv[1])[:top_k]
    return [{"text": text_by_id[cid], "score": round(s, 4)} for cid, s in ranked]
