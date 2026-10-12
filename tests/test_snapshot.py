from backend import snapshot
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem


def test_content_hash_order_independent():
    # 内容相同、dict 内 key 顺序不同 → 同哈希
    assert snapshot.content_hash([{"a": 1, "b": 2}]) == snapshot.content_hash([{"b": 2, "a": 1}])
    # 列表内 dict 顺序不同 → 同哈希(按稳定 key 排序)
    a = [{"input": "q1"}, {"input": "q2"}]
    b = [{"input": "q2"}, {"input": "q1"}]
    assert snapshot.content_hash(a) == snapshot.content_hash(b)
    # 内容变化 → 哈希变化
    assert snapshot.content_hash([{"a": 1}]) != snapshot.content_hash([{"a": 2}])


def test_config_top_k_parse_and_fallback():
    assert snapshot.config_top_k("{}") == 2          # 缺省回退 2
    assert snapshot.config_top_k('{"top_k": 5}') == 5
    assert snapshot.config_top_k("not json") == 2    # 解析失败回退 2
    assert snapshot.config_top_k("") == 2


def test_config_retrieval_parse_and_fallback():
    assert snapshot.config_retrieval("{}") == "hybrid"                 # 缺省回退 hybrid
    assert snapshot.config_retrieval('{"retrieval": "dense"}') == "dense"
    assert snapshot.config_retrieval('{"retrieval": "bogus"}') == "hybrid"  # 非法值回退
    assert snapshot.config_retrieval("not json") == "hybrid"           # 解析失败回退


def test_build_snapshot_fields_and_dataset_hash():
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    s.add(DatasetItem(dataset_id=ds.id, input="q", expected_output="a/b", bucket="x"))
    s.commit()
    did = ds.id
    s.close()

    snap = snapshot.build_snapshot(did, top_k=3)
    assert snap["top_k"] == 3
    assert snap["retrieval"] == "hybrid"  # 默认 hybrid(Ch16)
    assert snapshot.build_snapshot(did, top_k=3, retrieval="dense")["retrieval"] == "dense"
    assert snap["knowledge_version"] == snapshot.KNOWLEDGE_VERSION
    assert snap["pipeline_prompt_version"] == snapshot.PIPELINE_PROMPT_VERSION
    assert snap["judge_prompt_version"] == snapshot.JUDGE_PROMPTS_VERSION
    assert snap["item_count"] == 1
    assert len(snap["dataset_hash"]) == 32      # md5
    assert len(snap["knowledge_hash"]) == 32

    # 加一条样本 → 数据集哈希变化
    s = SessionLocal()
    s.add(DatasetItem(dataset_id=did, input="q2", expected_output="c/d", bucket="y"))
    s.commit()
    s.close()
    assert snapshot.build_snapshot(did, top_k=3)["dataset_hash"] != snap["dataset_hash"]
