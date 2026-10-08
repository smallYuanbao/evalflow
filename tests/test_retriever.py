from backend.retriever import retrieve


def test_retrieve_fever():
    texts = retrieve("宝宝发烧38度怎么办")
    assert any("物理降温" in t for t in texts)


def test_retrieve_no_match_returns_empty():
    assert retrieve("今天天气怎么样") == []
