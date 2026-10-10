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


# —— Ch12 鉴权 + 限流 ——

def test_auth_required(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "app_api_key", "secret-123")
    assert client.get("/datasets").status_code == 401                       # 无 key 拒绝
    assert client.get("/datasets", headers={"Authorization": "Bearer wrong"}).status_code == 401  # 错 key 拒绝
    assert client.get("/datasets", headers={"Authorization": "Bearer secret-123"}).status_code == 200  # 对 key 放行
    assert client.get("/health").status_code == 200                         # health 豁免


def test_create_run_rate_limited(monkeypatch):
    from backend import main

    class _FakeTask:
        @staticmethod
        def delay(run_id):
            pass

    monkeypatch.setattr(main, "run_task", _FakeTask)
    monkeypatch.setattr(main.run_limiter, "max_requests", 2)
    main.run_limiter._reset()

    did = client.post("/datasets", json={"name": "限流", "description": ""}).json()["id"]
    assert client.post("/runs", json={"dataset_id": did, "config": "{}"}).status_code == 200
    assert client.post("/runs", json={"dataset_id": did, "config": "{}"}).status_code == 200
    assert client.post("/runs", json={"dataset_id": did, "config": "{}"}).status_code == 429  # 超限


# —— Ch13 可观测性 ——

def test_runs_trend_route():
    # 关键:证明 /runs/trend 注册在 /runs/{run_id} 之前(顺序反了会 422)
    r = client.get("/runs/trend")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_run_export_route():
    from backend.db import SessionLocal, init_db
    from backend.models import Dataset, DatasetItem, Run, Score, Trace

    init_db()
    s = SessionLocal()
    ds = Dataset(name="导出", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q", expected_output="a", bucket="护理")
    s.add(i1)
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q", output="o", retrieved_context="c")
    s.add(t1)
    s.flush()
    s.add(Score(trace_id=t1.id, name="recall", value=1.0))
    s.commit()
    rid = run.id
    s.close()

    r = client.get(f"/runs/{rid}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "trace_id" in r.text

    assert client.get("/runs/999999/export").status_code == 404  # 无明细 → 404
