from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace
from backend.stats import aggregate_run


def test_aggregate_by_bucket():
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a/b", bucket="护理")
    i2 = DatasetItem(dataset_id=ds.id, input="q2", expected_output="a/b", bucket="睡眠")
    s.add_all([i1, i2])
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q1", output="o1", retrieved_context="c")
    t2 = Trace(run_id=run.id, dataset_item_id=i2.id, input="q2", output="o2", retrieved_context="c")
    s.add_all([t1, t2])
    s.flush()
    s.add_all([
        Score(trace_id=t1.id, name="recall", value=1.0),
        Score(trace_id=t1.id, name="faithfulness", value=1.0),
        Score(trace_id=t2.id, name="recall", value=0.0),
        Score(trace_id=t2.id, name="faithfulness", value=None),  # judge 挂,不参与均值
    ])
    s.commit()
    rid = run.id
    s.close()

    agg = aggregate_run(rid)
    assert agg["scores"]["recall_avg"] == 0.5
    assert agg["scores"]["faithfulness_avg"] == 1.0  # 只有 1 条非 NULL
    assert agg["by_bucket"]["护理"]["recall_avg"] == 1.0
    assert agg["by_bucket"]["护理"]["count"] == 1
    assert agg["by_bucket"]["睡眠"]["recall_avg"] == 0.0
    assert agg["by_bucket"]["睡眠"]["count"] == 1


def test_aggregate_rejection():
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="", bucket="库外")
    i2 = DatasetItem(dataset_id=ds.id, input="q2", expected_output="", bucket="库外")
    s.add_all([i1, i2])
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q1", output="不清楚", retrieved_context="(无证据)")
    t2 = Trace(run_id=run.id, dataset_item_id=i2.id, input="q2", output="宝宝可以这样处理", retrieved_context="(无证据)")
    s.add_all([t1, t2])
    s.flush()
    s.add_all([
        Score(trace_id=t1.id, name="rejection", value=1.0),
        Score(trace_id=t2.id, name="rejection", value=0.0),
    ])
    s.commit()
    rid = run.id
    s.close()

    agg = aggregate_run(rid)
    assert agg["scores"]["rejection_rate"] == 0.5
    assert agg["scores"]["recall_avg"] is None  # 库外题不评 recall
    assert agg["by_bucket"]["库外"]["rejection_rate"] == 0.5
    assert agg["by_bucket"]["库外"]["count"] == 2
