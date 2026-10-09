from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_datasets_crud():
    r = client.post("/datasets", json={"name": "t", "description": "d"})
    assert r.status_code == 200 and r.json()["name"] == "t"
    did = r.json()["id"]
    r = client.post(f"/datasets/{did}/items", json={"input": "q", "expected_output": "a/b", "bucket": "x"})
    assert r.status_code == 200
    page = client.get("/datasets").json()
    assert "items" in page and "total" in page  # 后端分页:{items, total}


def test_list_runs_and_items(monkeypatch):
    from backend import run_service

    # 走 HTTP 触发 BackgroundTask 会调真实 LLM,这里 mock 掉生成 + judge(测的是接口,不是 LLM)
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q: {"output": "答", "retrieved_context": "物理降温 就医 用药",
                   "hits": [{"text": "物理降温", "score": 0.9}]},
    )
    monkeypatch.setattr(
        run_service, "faithfulness",
        lambda o, c: {"score": 0.9, "reason": "ok"},
    )

    r = client.post("/datasets", json={"name": "t", "description": "d"})
    did = r.json()["id"]
    client.post(f"/datasets/{did}/items", json={"input": "q", "expected_output": "a/b", "bucket": "x"})

    # 用新建评测集自己的 id 断言,不依赖全局顺序/数量(共享 SQLite 会累积历史数据)
    items = client.get(f"/datasets/{did}/items").json()
    assert len(items) == 1 and items[0]["input"] == "q"

    ours = next(d for d in client.get("/datasets").json()["items"] if d["id"] == did)
    assert ours["item_count"] == 1
    assert ours["updated_at"]  # 新评测集带修改时间(排序用)
    assert client.get(f"/datasets/{did}").json()["name"] == "t"  # 详情接口

    client.post("/runs", json={"dataset_id": did, "config": "{}"})
    ours_run = next(r for r in client.get("/runs").json() if r["dataset_id"] == did)
    assert ours_run["status"] in ("running", "done", "failed")
    assert ours_run["created_at"]  # 新 run 的 created_at 已补默认时间戳
    assert ours_run["dataset_name"] == "t"  # run 列表带评测集名称
