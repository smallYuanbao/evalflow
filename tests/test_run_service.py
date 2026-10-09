import json

from backend import run_service
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace

# 5 个 LLM judge 都要 mock(走 HTTP 会调真实 LLM)
JUDGES = {
    "faithfulness": lambda o, c: {"score": 0.9, "reason": "ok"},
    "context_precision": lambda q, c: {"score": 0.8, "reason": "ok"},
    "context_recall": lambda q, e, c: {"score": 0.7, "reason": "ok"},
    "answer_relevance": lambda q, o: {"score": 0.6, "reason": "ok"},
    "answer_correctness": lambda q, e, o: {"score": 0.5, "reason": "ok"},
}

INBUCKET = set(JUDGES) | {"recall"}  # 库内题:机械 recall + 5 个 judge
ABSENT = {"rejection"}               # 库外题:只评拒答


def _mock_judges(monkeypatch):
    for name, fn in JUDGES.items():
        monkeypatch.setattr(run_service, name, fn)


def _seed_run(monkeypatch):
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q, top_k=2: {"output": f"答:{q}", "retrieved_context": "物理降温 就医 用药",
                            "hits": [{"text": "物理降温", "score": 0.9}]},
    )
    _mock_judges(monkeypatch)
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    s.add(DatasetItem(dataset_id=ds.id, input="q1", expected_output="物理降温/就医/用药", bucket="a"))
    run = Run(dataset_id=ds.id, status="running", config="{}")
    s.add(run)
    s.commit()
    rid = run.id
    s.close()
    return rid


def test_execute_run_done(monkeypatch):
    rid = _seed_run(monkeypatch)
    run_service.execute_run(rid)
    s = SessionLocal()
    run = s.get(Run, rid)
    assert run.status == "done"
    assert s.query(Trace).filter(Trace.run_id == rid).count() == 1
    tr = s.query(Trace).filter(Trace.run_id == rid).first()
    names = {sc.name for sc in s.query(Score).filter(Score.trace_id == tr.id)}
    assert names == INBUCKET  # 库内题:6 个指标
    hits = json.loads(tr.retrieval_hits)          # 检索命中已落库(JSON)
    assert hits == [{"text": "物理降温", "score": 0.9, "rank": 1}]
    s.close()


def test_execute_run_failed(monkeypatch):
    rid = _seed_run(monkeypatch)

    def _boom(q, top_k=2):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_service, "run_pipeline", _boom)
    run_service.execute_run(rid)
    s = SessionLocal()
    assert s.get(Run, rid).status == "failed"
    s.close()


def test_execute_run_absent_bucket(monkeypatch):
    # 库外题只评 rejection;普通题评 recall + 5 个 judge
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q, top_k=2: {"output": "不清楚，没有相关证据。", "retrieved_context": "(无证据)", "hits": []},
    )
    _mock_judges(monkeypatch)
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    s.add_all([
        DatasetItem(dataset_id=ds.id, input="q1", expected_output="物理降温/就医/用药", bucket="护理"),
        DatasetItem(dataset_id=ds.id, input="q2", expected_output="", bucket="库外"),
    ])
    run = Run(dataset_id=ds.id, status="running", config="{}")
    s.add(run)
    s.commit()
    rid = run.id
    s.close()

    run_service.execute_run(rid)

    s = SessionLocal()
    for tr in s.query(Trace).filter(Trace.run_id == rid):
        item = s.get(DatasetItem, tr.dataset_item_id)
        names = {sc.name for sc in s.query(Score).filter(Score.trace_id == tr.id)}
        if item.bucket == "库外":
            assert names == ABSENT
            assert s.query(Score).filter(Score.trace_id == tr.id).first().value == 1.0
        else:
            assert names == INBUCKET
    s.close()


def test_execute_run_passes_top_k_from_config(monkeypatch):
    # config 里的 top_k 要真正流到 run_pipeline(不同 top_k 检索命中数不同)
    seen = {}

    def _capture(q, top_k=2):
        seen["top_k"] = top_k
        return {"output": "答", "retrieved_context": "c", "hits": []}

    monkeypatch.setattr(run_service, "run_pipeline", _capture)
    _mock_judges(monkeypatch)
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    s.add(DatasetItem(dataset_id=ds.id, input="q", expected_output="a/b", bucket="a"))
    run = Run(dataset_id=ds.id, status="running", config='{"top_k": 5}')
    s.add(run)
    s.commit()
    rid = run.id
    s.close()

    run_service.execute_run(rid)
    assert seen["top_k"] == 5
