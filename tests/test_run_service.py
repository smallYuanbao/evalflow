import json

from backend import run_service
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace


def _seed_run(monkeypatch):
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q: {"output": f"答:{q}", "retrieved_context": "物理降温 就医 用药",
                   "hits": [{"text": "物理降温", "score": 0.9}]},
    )
    monkeypatch.setattr(
        run_service, "faithfulness",
        lambda o, c: {"score": 0.9, "reason": "ok"},
    )
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
    assert names == {"recall", "faithfulness"}
    hits = json.loads(tr.retrieval_hits)          # 检索命中已落库(JSON)
    assert hits == [{"text": "物理降温", "score": 0.9, "rank": 1}]
    s.close()


def test_execute_run_failed(monkeypatch):
    rid = _seed_run(monkeypatch)

    def _boom(q):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_service, "run_pipeline", _boom)
    run_service.execute_run(rid)
    s = SessionLocal()
    assert s.get(Run, rid).status == "failed"
    s.close()


def test_execute_run_absent_bucket(monkeypatch):
    # 库外题只评 rejection(不评 recall/faithfulness);普通题评 recall/faithfulness
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q: {"output": "不清楚，没有相关证据。", "retrieved_context": "(无证据)",
                   "hits": []},
    )
    monkeypatch.setattr(
        run_service, "faithfulness",
        lambda o, c: {"score": 0.9, "reason": "ok"},
    )
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
        scores = s.query(Score).filter(Score.trace_id == tr.id).all()
        names = {sc.name for sc in scores}
        if item.bucket == "库外":
            assert names == {"rejection"}
            assert scores[0].value == 1.0
        else:
            assert names == {"recall", "faithfulness"}
    s.close()
