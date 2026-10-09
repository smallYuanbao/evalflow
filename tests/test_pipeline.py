from backend import pipeline


def test_run_pipeline_shape(monkeypatch):
    monkeypatch.setattr(
        pipeline, "retrieve",
        lambda q, top_k=2: [{"text": "证据A", "score": 0.9}, {"text": "证据B", "score": 0.8}],
    )
    monkeypatch.setattr(pipeline.llm, "chat", lambda msgs, **kw: "回答")
    r = pipeline.run_pipeline("测试")
    assert set(r.keys()) == {"output", "retrieved_context", "hits"}
    assert r["output"] == "回答"
    assert "证据A" in r["retrieved_context"]
    assert [h["text"] for h in r["hits"]] == ["证据A", "证据B"]
