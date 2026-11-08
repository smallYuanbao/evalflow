import json

from backend import run_service
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Generation, Run, Score, Trace

# 5 个 LLM judge 都要 mock(走 HTTP 会调真实 LLM)
JUDGES = {
    "faithfulness": lambda o, c: {"score": 0.9, "reason": "ok"},
    "context_precision": lambda q, c: {"score": 0.8, "reason": "ok"},
    "context_recall": lambda q, e, c: {"score": 0.7, "reason": "ok"},
    "answer_relevance": lambda q, o: {"score": 0.6, "reason": "ok"},
    "answer_correctness": lambda q, e, o: {"score": 0.5, "reason": "ok"},
}

INBUCKET = set(JUDGES) | {"recall", "hit_at_k", "mrr"}  # 有检索上下文:机械指标 + 5 个 judge
NO_CONTEXT = {"recall", "hit_at_k", "mrr", "answer_relevance", "answer_correctness"}
ABSENT = {"rejection"}               # 库外题:只评拒答


def _mock_judges(monkeypatch):
    for name, fn in JUDGES.items():
        monkeypatch.setattr(run_service, name, fn)


def _seed_run(monkeypatch):
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q, top_k=2, retrieval="hybrid": {"output": f"答:{q}", "retrieved_context": "物理降温 就医 用药",
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
    assert run.last_heartbeat_at is not None  # 执行期间写过心跳
    assert s.query(Trace).filter(Trace.run_id == rid).count() == 1
    tr = s.query(Trace).filter(Trace.run_id == rid).first()
    names = {sc.name for sc in s.query(Score).filter(Score.trace_id == tr.id)}
    assert names == INBUCKET  # 库内题:6 个指标
    hits = json.loads(tr.retrieval_hits)          # 检索命中已落库(JSON)
    assert hits == [{"text": "物理降温", "score": 0.9, "rank": 1}]
    gens = s.query(Generation).filter(Generation.trace_id == tr.id).all()
    assert len(gens) == 1 and gens[0].input_tokens == 0  # judge/pipeline 全 mock,无真实 token(Ch12)
    s.close()


def test_generation_records_cost(monkeypatch):
    # 计量到 token 后,Generation 要写对 token 与费用(Ch12 费用统计)
    from backend import llm

    rid = _seed_run(monkeypatch)
    monkeypatch.setattr(llm, "get_usage", lambda: (1000, 500))  # 模拟计量到 1000 输入 / 500 输出
    run_service.execute_run(rid)
    s = SessionLocal()
    gens = s.query(Generation).filter(Generation.trace_id.in_(
        [tr.id for tr in s.query(Trace).filter(Trace.run_id == rid)])).all()
    assert len(gens) == 1
    assert gens[0].input_tokens == 1000
    assert gens[0].output_tokens == 500
    assert gens[0].cost == round(llm.compute_cost(1000, 500), 6)
    s.close()


def test_execute_run_failed(monkeypatch):
    rid = _seed_run(monkeypatch)

    def _boom(q, top_k=2, retrieval="hybrid"):
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
        lambda q, top_k=2, retrieval="hybrid": {"output": "不清楚，没有相关证据。", "retrieved_context": "(无证据)", "hits": []},
    )
    _mock_judges(monkeypatch)
    # 拒答双信号里的 judge 也要 mock(否则会走真实 LLM)
    monkeypatch.setattr(run_service, "rejection_dual", lambda q, o: (1.0, "mock 双信号"))
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
            # 非库外但检索上下文为 "(无证据)"：跳过 context/faithfulness，
            # 机械指标记 NULL。
            assert names == NO_CONTEXT
            values = {
                sc.name: sc.value
                for sc in s.query(Score).filter(Score.trace_id == tr.id)
            }
            assert values["recall"] is None
            assert values["hit_at_k"] is None
            assert values["mrr"] is None
    s.close()


def test_execute_run_passes_top_k_from_config(monkeypatch):
    # config 里的 top_k / retrieval 要真正流到 run_pipeline(不同配置检索行为不同)
    seen = {}

    def _capture(q, top_k=2, retrieval="hybrid"):
        seen["top_k"] = top_k
        seen["retrieval"] = retrieval
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
    assert seen["retrieval"] == "hybrid"  # config 没写 retrieval → 默认 hybrid
