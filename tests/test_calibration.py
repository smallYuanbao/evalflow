from fastapi.testclient import TestClient

from backend.calibration import calibrate
from backend.db import SessionLocal, init_db
from backend.main import app
from backend.models import Dataset, DatasetItem, Run, Score, Trace

client = TestClient(app)


# —— 纯函数 ——

def test_calibrate_bias_mae_corr_n():
    # judge 系统性偏松 0.1(bias=+0.1),且与 gold 完全同序(corr=1)
    m = calibrate(
        {"faithfulness": [0.9, 0.8, 0.7]},
        {"faithfulness": [0.8, 0.7, 0.6]},
    )["faithfulness"]
    assert m["n"] == 3
    assert abs(m["bias"] - 0.1) < 1e-6
    assert abs(m["mae"] - 0.1) < 1e-6
    assert m["corr"] == 1.0  # 完全同序


def test_calibrate_empty_and_single():
    m0 = calibrate({"faithfulness": []}, {"faithfulness": []})["faithfulness"]
    assert m0["n"] == 0 and m0["bias"] is None and m0["corr"] is None

    m1 = calibrate({"faithfulness": [0.8]}, {"faithfulness": [0.9]})["faithfulness"]
    assert m1["n"] == 1 and m1["corr"] is None  # n<2 无相关系数


# —— 端点:标金标准 → 校准报告 ——

def test_calibration_endpoint():
    init_db()
    s = SessionLocal()
    ds = Dataset(name="校准", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a", bucket="护理")
    s.add(i1)
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q1", output="o", retrieved_context="c")
    s.add(t1)
    s.flush()
    s.add(Score(trace_id=t1.id, name="faithfulness", value=0.8))
    s.commit()
    did, iid, rid = ds.id, i1.id, run.id
    s.close()

    r = client.put(f"/datasets/{did}/items/{iid}/gold", json={"gold_scores": {"faithfulness": 0.9}})
    assert r.status_code == 200 and r.json()["gold_scores"]["faithfulness"] == 0.9

    rep = client.get(f"/runs/{rid}/calibration").json()
    m = rep["metrics"]["faithfulness"]
    assert m["n"] == 1
    assert abs(m["bias"] - (-0.1)) < 1e-6  # judge 0.8 − gold 0.9
    assert abs(m["mae"] - 0.1) < 1e-6
    assert m["corr"] is None  # n=1 无 corr

    assert client.put(f"/datasets/{did}/items/999999/gold",
                      json={"gold_scores": {}}).status_code == 404
    assert client.get("/runs/999999/calibration").status_code == 404
