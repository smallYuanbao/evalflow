from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Generation, Run, Score, Trace
from backend.stats import aggregate_run, run_export_csv, runs_trend


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
        Score(trace_id=t1.id, name="context_precision", value=0.9),
        Score(trace_id=t2.id, name="recall", value=0.0),
        Score(trace_id=t2.id, name="faithfulness", value=None),  # judge 挂,不参与均值
    ])
    s.commit()
    rid = run.id
    s.close()

    agg = aggregate_run(rid)
    # 指标按注册表顺序,只含 present 的:recall → context_precision → faithfulness
    assert list(agg["scores"].keys()) == ["recall", "context_precision", "faithfulness"]
    assert agg["scores"]["recall"] == 0.5
    assert agg["scores"]["faithfulness"] == 1.0      # 只有 1 条非 NULL
    assert agg["scores"]["context_precision"] == 0.9  # 只有 1 条有值
    assert agg["by_bucket"]["护理"]["recall"] == 1.0
    assert agg["by_bucket"]["护理"]["count"] == 1
    assert agg["by_bucket"]["睡眠"]["recall"] == 0.0
    assert agg["by_bucket"]["睡眠"]["context_precision"] is None  # 睡眠桶没评该指标 → null
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
    assert list(agg["scores"].keys()) == ["rejection"]  # 库外题只评 rejection
    assert agg["scores"]["rejection"] == 0.5
    assert "recall" not in agg["scores"]  # 没评的指标不出现在 scores 里
    assert agg["by_bucket"]["库外"]["rejection"] == 0.5
    assert agg["by_bucket"]["库外"]["count"] == 2


def test_aggregate_cost():
    # Ch12 费用统计:run 汇总所有样本的 token 与费用
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a", bucket="护理")
    s.add(i1)
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q1", output="o1", retrieved_context="c")
    s.add(t1)
    s.flush()
    s.add_all([
        Generation(trace_id=t1.id, model="deepseek-chat",
                   input_tokens=100, output_tokens=50, cost=0.0006),
        Score(trace_id=t1.id, name="recall", value=1.0),
    ])
    s.commit()
    rid = run.id
    s.close()

    agg = aggregate_run(rid)
    assert agg["input_tokens"] == 100
    assert agg["output_tokens"] == 50
    assert agg["cost"] == 0.0006


def test_runs_trend_aggregates():
    # Ch13 趋势:批量聚合多个 run 的 per-metric 均值
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a", bucket="护理")
    i2 = DatasetItem(dataset_id=ds.id, input="q2", expected_output="a", bucket="护理")
    s.add_all([i1, i2])
    s.flush()
    r1 = Run(dataset_id=ds.id, status="done", config="{}")
    r2 = Run(dataset_id=ds.id, status="done", config="{}")
    s.add_all([r1, r2])
    s.flush()
    t1 = Trace(run_id=r1.id, dataset_item_id=i1.id, input="q1", output="o1", retrieved_context="c")
    t2 = Trace(run_id=r1.id, dataset_item_id=i2.id, input="q2", output="o2", retrieved_context="c")
    t3 = Trace(run_id=r2.id, dataset_item_id=i1.id, input="q1", output="o3", retrieved_context="c")
    s.add_all([t1, t2, t3])
    s.flush()
    s.add_all([
        Score(trace_id=t1.id, name="faithfulness", value=0.8),
        Score(trace_id=t2.id, name="faithfulness", value=1.0),
        Score(trace_id=t3.id, name="faithfulness", value=0.6),
        Score(trace_id=t2.id, name="recall", value=None),  # NULL 不参与均值
    ])
    r1_id, r2_id = r1.id, r2.id  # commit 后 ORM 对象 expire,提前取普通字段
    s.commit()
    s.close()

    trend = runs_trend()
    by_id = {r["id"]: r for r in trend}
    assert by_id[r1_id]["scores"]["faithfulness"] == 0.9  # (0.8 + 1.0) / 2
    assert by_id[r2_id]["scores"]["faithfulness"] == 0.6
    assert by_id[r1_id]["dataset_name"] == "t"


def test_run_export_csv():
    # Ch13 导出:CSV 表头 + 每 trace 一行
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a", bucket="护理")
    s.add(i1)
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q1", output="o1",
               retrieved_context="c", latency_ms=100)
    s.add(t1)
    s.flush()
    s.add_all([
        Score(trace_id=t1.id, name="recall", value=1.0),
        Score(trace_id=t1.id, name="faithfulness", value=0.9),
    ])
    rid, t1_id = run.id, t1.id  # commit 后 ORM 对象 expire,提前取普通字段
    s.commit()
    s.close()

    lines = run_export_csv(rid).strip().splitlines()
    assert lines[0].split(",") == ["trace_id", "input", "output", "latency_ms", "recall", "faithfulness"]
    assert len(lines) == 2  # 表头 + 1 行
    row = lines[1].split(",")
    assert row[0] == str(t1_id)
    assert row[1] == "q1"
    assert row[3] == "100"
    assert row[4] == "1.0"
    assert row[5] == "0.9"

    assert run_export_csv(999999) == ""  # 不存在的 run → 空串
