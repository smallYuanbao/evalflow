import chromadb
import pytest

from backend import retriever


@pytest.fixture
def fresh_client(tmp_path, monkeypatch):
    # 每个测试用独立临时 chroma,避免真实 data/chroma 持久化数据互相污染
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    monkeypatch.setattr(retriever, "_client", client)
    return client


def _fake_embed(texts):
    # 含"发烧"的文本 -> [1,0],否则 -> [0,1];query 含"发烧"时与"发烧"块余弦相似度更高
    return [[1.0, 0.0] if "发烧" in t else [0.0, 1.0] for t in texts]


def test_retrieve_returns_topk_with_scores(fresh_client, monkeypatch):
    monkeypatch.setattr(retriever, "embed", _fake_embed)
    retriever.ingest()
    hits = retriever.retrieve_dense("宝宝发烧", top_k=2)
    assert len(hits) == 2
    assert all("text" in h and "score" in h for h in hits)
    assert "发烧" in hits[0]["text"]             # 相似度最高的应是"发烧"类
    assert hits[0]["score"] >= hits[-1]["score"]  # 按分数降序


def test_retrieve_lazy_ingests_when_empty(fresh_client, monkeypatch):
    monkeypatch.setattr(retriever, "embed", _fake_embed)
    hits = retriever.retrieve_dense("宝宝发烧", top_k=1)  # 空库自动灌库
    assert len(hits) == 1
    assert "发烧" in hits[0]["text"]
