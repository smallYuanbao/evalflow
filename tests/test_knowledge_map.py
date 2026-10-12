from backend import knowledge_map as km
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem


def _fake_embed(texts):
    return [[1.0, 0.0, float(i)] for i, _ in enumerate(texts)]


def test_chunk_layout_cached_across_calls(monkeypatch):
    # Ch21:知识块只嵌入一次,第二次调用命中缓存(不再 embed)
    km._chunk_cache = None
    calls: list[list[str]] = []

    def _counting_embed(texts):
        calls.append(list(texts))
        return _fake_embed(texts)

    monkeypatch.setattr(km, "embed", _counting_embed)
    monkeypatch.setattr(km, "_recent_unique_inputs", lambda limit: [])  # 不牵涉 DB

    km.knowledge_map()
    after_first = len(calls)
    km.knowledge_map()
    assert len(calls) == after_first  # 第二次没有再嵌入知识块
    assert after_first == 1            # 只有知识块那一次
    km._chunk_cache = None


def test_recent_unique_inputs_dedupes_and_limits():
    init_db()
    s = SessionLocal()
    ds = Dataset(name="km-test", description="")
    s.add(ds)
    s.flush()
    for t in ["km-a", "km-a", "km-b", "km-c"]:
        s.add(DatasetItem(dataset_id=ds.id, input=t, expected_output="a", bucket="b"))
    s.commit()
    s.close()

    out = km._recent_unique_inputs(3)
    assert len(out) == 3                # 上限生效
    assert len(out) == len(set(out))    # 去重
    assert out[0] == "km-c"             # 最新的排最前(id desc)


def test_knowledge_map_shape(monkeypatch):
    km._chunk_cache = None
    monkeypatch.setattr(km, "embed", _fake_embed)
    monkeypatch.setattr(km, "_recent_unique_inputs", lambda limit: ["q1"])
    data = km.knowledge_map()
    assert len(data["chunks"]) == len(km.KNOWLEDGE)
    assert all({"id", "text", "category", "x", "y"} <= set(c) for c in data["chunks"])
    assert data["queries"] == [{"input": "q1", "x": data["queries"][0]["x"], "y": data["queries"][0]["y"]}]
    km._chunk_cache = None
