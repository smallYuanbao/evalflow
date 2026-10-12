from backend.bm25 import BM25, _tokenize
from backend.knowledge import KNOWLEDGE


def test_tokenize_bigrams():
    assert _tokenize("发烧") == ["发烧"]
    assert "发烧" in _tokenize("宝宝发烧怎么办")
    assert _tokenize("") == []
    assert _tokenize("一") == ["一"]  # 单字退化为单字符 token


def test_bm25_keyword_match_ranks_first():
    bm = BM25(KNOWLEDGE)
    hits = bm.search("宝宝发烧怎么办", top_k=3)
    assert hits  # 有命中
    # 「发烧」命中的 chunk 排最前,且 fever-* 类在 top 里
    assert "发烧" in hits[0][1]
    assert any(i.startswith("fever") for i, _, _ in hits)


def test_bm25_no_keyword_match_empty():
    bm = BM25(KNOWLEDGE)
    hits = bm.search("区块链去中心化", top_k=3)  # 育儿语料里没有的词
    assert hits == []
