import json

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
    from backend import main, run_service

    # create_run 现在入队 run_task.delay;测试不依赖 redis,把 delay mock 成同步执行
    class _FakeTask:
        @staticmethod
        def delay(run_id):
            run_service.execute_run(run_id)

    monkeypatch.setattr(main, "run_task", _FakeTask)

    # 走 HTTP 触发 run 执行会调真实 LLM,这里 mock 掉生成 + judge(测的是接口,不是 LLM)
    monkeypatch.setattr(
        run_service, "run_pipeline",
        lambda q, top_k=2: {"output": "答", "retrieved_context": "物理降温 就医 用药",
                            "hits": [{"text": "物理降温", "score": 0.9}]},
    )
    # 库内题现在评 5 个 LLM judge,全部 mock(走 HTTP 会调真实 LLM,测的是接口不是 LLM)
    monkeypatch.setattr(run_service, "faithfulness", lambda o, c: {"score": 0.9, "reason": "ok"})
    monkeypatch.setattr(run_service, "context_precision", lambda q, c: {"score": 0.8, "reason": "ok"})
    monkeypatch.setattr(run_service, "context_recall", lambda q, e, c: {"score": 0.7, "reason": "ok"})
    monkeypatch.setattr(run_service, "answer_relevance", lambda q, o: {"score": 0.6, "reason": "ok"})
    monkeypatch.setattr(run_service, "answer_correctness", lambda q, e, o: {"score": 0.5, "reason": "ok"})

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

    client.post("/runs", json={"dataset_id": did, "config": '{"top_k": 3}'})
    ours_run = next(r for r in client.get("/runs").json() if r["dataset_id"] == did)
    assert ours_run["status"] in ("running", "done", "failed")
    assert ours_run["created_at"]  # 新 run 的 created_at 已补默认时间戳
    assert ours_run["dataset_name"] == "t"  # run 列表带评测集名称
    cfg = json.loads(ours_run["config"])  # 列表回看复现上下文快照(Ch09)
    assert cfg["top_k"] == 3
    assert cfg["knowledge_version"] and cfg["prompt_version"]
    assert cfg["dataset_hash"] and cfg["item_count"] == 1


def test_recover_stale_runs():
    from backend import main
    from backend.db import SessionLocal, init_db
    from backend.models import Dataset, Run

    # 造一个残留 running 的 run,直接调 _recover_stale_runs 验证被标 failed(Ch10 兜底)
    init_db()
    s = SessionLocal()
    ds = Dataset(name="t", description="")
    s.add(ds)
    s.flush()
    run = Run(dataset_id=ds.id, status="running", config="{}")
    s.add(run)
    s.commit()
    rid = run.id
    s.close()

    main._recover_stale_runs()

    s = SessionLocal()
    assert s.get(Run, rid).status == "failed"
    s.close()
