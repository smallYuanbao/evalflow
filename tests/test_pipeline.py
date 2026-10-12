from backend import pipeline


def _assert_shape(r):
    assert set(r.keys()) == {"output", "retrieved_context", "hits"}
    assert r["output"] == "回答"
    assert "证据A" in r["retrieved_context"]
    assert [h["text"] for h in r["hits"]] == ["证据A", "证据B"]


def test_run_pipeline_default_hybrid(monkeypatch):
    # 默认 retrieval=hybrid → 走 hybrid_retrieve
    monkeypatch.setattr(
        pipeline, "hybrid_retrieve",
        lambda q, top_k=2: [{"text": "证据A", "score": 0.03}, {"text": "证据B", "score": 0.02}],
    )
    monkeypatch.setattr(pipeline.llm, "chat", lambda msgs, **kw: "回答")
    _assert_shape(pipeline.run_pipeline("测试"))


def test_run_pipeline_dense_mode(monkeypatch):
    # retrieval=dense → 走 retrieve_dense,不碰 hybrid
    monkeypatch.setattr(
        pipeline, "retrieve_dense",
        lambda q, top_k=2: [{"text": "证据A", "score": 0.9}, {"text": "证据B", "score": 0.8}],
    )
    monkeypatch.setattr(pipeline.llm, "chat", lambda msgs, **kw: "回答")
    _assert_shape(pipeline.run_pipeline("测试", retrieval="dense"))
