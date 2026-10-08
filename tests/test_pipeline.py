from backend.pipeline import run_pipeline


def test_run_pipeline_shape():
    r = run_pipeline("测试")
    assert set(r.keys()) == {"output", "retrieved_context"}
    assert isinstance(r["output"], str) and isinstance(r["retrieved_context"], str)
