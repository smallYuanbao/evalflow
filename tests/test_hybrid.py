from backend import retriever


def test_hybrid_rrf_ranks_both_hit_first(monkeypatch):
    """两路都命中的 chunk 应排最前(RRF 排名累加)。dense 命中 A、B;sparse 命中 B、C → B 第一。"""
    monkeypatch.setattr(
        retriever, "_dense_hits",
        lambda q, top_k: [("A", "文本A", 0.9), ("B", "文本B", 0.8)],
    )
    monkeypatch.setattr(
        retriever._bm25, "search",
        lambda q, top_k: [("B", "文本B", 5.0), ("C", "文本C", 3.0)],
    )
    hits = retriever.hybrid_retrieve("q", top_k=3)
    assert [h["text"] for h in hits][0] == "文本B"  # 双路命中 → RRF 最高
    assert len(hits) == 3
    assert all("text" in h and "score" in h for h in hits)
    # RRF 分数是 1/(60+rank) 累加:双路第一 = 2/61
    assert abs(hits[0]["score"] - 2 / 61) < 1e-3


def test_hybrid_dedupes_same_doc_across_channels(monkeypatch):
    """同一 chunk 在两路都命中,不重复出现,RRF 分数叠加。"""
    monkeypatch.setattr(
        retriever, "_dense_hits",
        lambda q, top_k: [("A", "文本A", 0.9)],
    )
    monkeypatch.setattr(
        retriever._bm25, "search",
        lambda q, top_k: [("A", "文本A", 5.0)],
    )
    hits = retriever.hybrid_retrieve("q", top_k=2)
    assert len(hits) == 1  # 去重后只剩 A 一条
    assert hits[0]["text"] == "文本A"
