from fastapi.testclient import TestClient

from backend.db import SessionLocal, init_db
from backend.gate import GATE_RULES, evaluate_gate
from backend.main import app
from backend.models import Dataset, DatasetItem, Run, Score, Trace

client = TestClient(app)


def _make_run(scores: dict[str, float | None]) -> int:
    """建一个 done run + 单样本,给指定指标打分,返回 run_id。"""
    init_db()
    s = SessionLocal()
    ds = Dataset(name="g", description="")
    s.add(ds)
    s.flush()
    it = DatasetItem(dataset_id=ds.id, input="q", expected_output="a", bucket="护理")
    s.add(it)
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    tr = Trace(run_id=run.id, dataset_item_id=it.id, input="q", output="o", retrieved_context="c")
    s.add(tr)
    s.flush()
    s.add_all([Score(trace_id=tr.id, name=k, value=v) for k, v in scores.items()])
    s.commit()
    rid = run.id
    s.close()
    return rid


# —— 纯函数:四类边界 ——

def test_gate_all_pass():
    res = evaluate_gate({m: 0.85 for m in GATE_RULES})
    assert res["passed"] is True
    assert all(c["passed"] for c in res["checks"])


def test_gate_exactly_threshold():
    # 刚好等于下限:>= 是边界,算过
    res = evaluate_gate({m: GATE_RULES[m]["min"] for m in GATE_RULES})
    assert res["passed"] is True


def test_gate_below_threshold():
    res = evaluate_gate({m: GATE_RULES[m]["min"] - 0.01 for m in GATE_RULES})
    assert res["passed"] is False
    assert all(c["note"] == "低于阈值" for c in res["checks"])


def test_gate_null_metric_fails():
    # 指标没评上(judge 挂):不通过,且不是「低于阈值」而是「未评」
    scores = {m: 0.85 for m in GATE_RULES}
    scores["faithfulness"] = None
    res = evaluate_gate(scores)
    assert res["passed"] is False
    ff = next(c for c in res["checks"] if c["metric"] == "faithfulness")
    assert ff["passed"] is False and ff["note"] == "未评"


def test_gate_regression_vs_baseline():
    # 这次 0.85、基线 0.95:掉 0.10 > 容忍 0.05,即便绝对线过了也 FAIL
    res = evaluate_gate({m: 0.85 for m in GATE_RULES}, {m: 0.95 for m in GATE_RULES})
    assert res["passed"] is False
    assert all(c["note"] == "较基线下降超过容忍度" for c in res["checks"])


def test_gate_ok_vs_baseline():
    # 掉 0.02 < 容忍 0.05,且都过绝对线:过
    res = evaluate_gate({m: 0.90 for m in GATE_RULES}, {m: 0.92 for m in GATE_RULES})
    assert res["passed"] is True


# —— 端点 ——

def test_gate_endpoint():
    good = _make_run({m: 0.85 for m in GATE_RULES})
    res = client.get(f"/runs/{good}/gate").json()
    assert res["passed"] is True
    assert res["run_id"] == good
    assert res["baseline_run_id"] is None
    assert len(res["checks"]) == len(GATE_RULES)


def test_gate_endpoint_with_baseline():
    # 基线 0.95、本次 0.85 → 相对回归 FAIL
    base = _make_run({m: 0.95 for m in GATE_RULES})
    cur = _make_run({m: 0.85 for m in GATE_RULES})
    res = client.get(f"/runs/{cur}/gate", params={"baseline_run_id": base}).json()
    assert res["passed"] is False
    assert res["baseline_run_id"] == base


def test_gate_endpoint_baseline_404():
    good = _make_run({m: 0.85 for m in GATE_RULES})
    r = client.get(f"/runs/{good}/gate", params={"baseline_run_id": 999999})
    assert r.status_code == 404
