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
    assert cfg["knowledge_version"] and cfg["pipeline_prompt_version"] and cfg["judge_prompt_version"]
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
    assert "样本ID" in r.text  # 表头中文(Ch24)

    assert client.get("/runs/999999/export").status_code == 404  # 无明细 → 404


def test_list_traces_includes_comment():
    # Ch18:Judge reason 存在 Score.comment,list_traces 要露出给前端
    from backend.db import SessionLocal, init_db
    from backend.models import Dataset, DatasetItem, Run, Score, Trace

    init_db()
    s = SessionLocal()
    ds = Dataset(name="明细", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q", expected_output="a", bucket="护理")
    s.add(i1)
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    t1 = Trace(run_id=run.id, dataset_item_id=i1.id, input="q", output="o",
               retrieved_context="证据", retrieval_hits='[{"text":"e","score":0.9,"rank":1}]')
    s.add(t1)
    s.flush()
    s.add(Score(trace_id=t1.id, name="faithfulness", value=0.8, comment="回答忠于证据"))
    s.commit()
    rid = run.id
    s.close()

    traces = client.get(f"/runs/{rid}/traces").json()
    assert len(traces) == 1
    sc = next(x for x in traces[0]["scores"] if x["name"] == "faithfulness")
    assert sc["comment"] == "回答忠于证据"


def test_run_diff_matches_by_item_and_delta():
    # Ch18:按 dataset_item_id 匹配两条 run 的 trace,算逐指标 delta;跨数据集标记;404
    from backend.db import SessionLocal, init_db
    from backend.models import Dataset, DatasetItem, Run, Score, Trace

    init_db()
    s = SessionLocal()
    ds = Dataset(name="diff", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a", bucket="护理")
    s.add(i1)
    s.flush()

    ra = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(ra)
    s.flush()
    ta = Trace(run_id=ra.id, dataset_item_id=i1.id, input="q1", output="o1",
               retrieved_context="证据A", retrieval_hits='[{"text":"e","score":0.9,"rank":1}]')
    s.add(ta)
    s.flush()
    s.add(Score(trace_id=ta.id, name="faithfulness", value=0.7))

    rb = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(rb)
    s.flush()
    tb = Trace(run_id=rb.id, dataset_item_id=i1.id, input="q1", output="o1",
               retrieved_context="证据B", retrieval_hits='[{"text":"e2","score":0.95,"rank":1}]')
    s.add(tb)
    s.flush()
    s.add(Score(trace_id=tb.id, name="faithfulness", value=0.85))
    s.commit()
    ra_id, rb_id = ra.id, rb.id
    s.close()

    data = client.get(f"/runs/{ra_id}/diff/{rb_id}").json()
    assert data["different_datasets"] is False
    assert len(data["pairs"]) == 1
    p = data["pairs"][0]
    assert p["input"] == "q1"
    assert p["a"]["retrieved_context"] == "证据A"
    assert p["b"]["retrieved_context"] == "证据B"
    assert abs(p["deltas"]["faithfulness"] - 0.15) < 1e-6  # 0.85 - 0.7

    assert client.get(f"/runs/{ra_id}/diff/999999").status_code == 404


def test_bucket_attribution_deltas():
    # Ch19:分桶归因 = 和基线比,每个 bucket 的逐指标 delta
    from backend.db import SessionLocal, init_db
    from backend.models import Dataset, DatasetItem, Run, Score, Trace

    init_db()
    s = SessionLocal()
    ds = Dataset(name="归因", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a", bucket="护理")
    i2 = DatasetItem(dataset_id=ds.id, input="q2", expected_output="b", bucket="睡眠")
    s.add_all([i1, i2])
    s.flush()

    def _run(ff: float, f2: float):
        r = Run(dataset_id=ds.id, status="done", config="{}")
        s.add(r)
        s.flush()
        t1 = Trace(run_id=r.id, dataset_item_id=i1.id, input="q1", output="o", retrieved_context="c")
        t2 = Trace(run_id=r.id, dataset_item_id=i2.id, input="q2", output="o", retrieved_context="c")
        s.add_all([t1, t2])
        s.flush()
        s.add_all([Score(trace_id=t1.id, name="faithfulness", value=ff),
                   Score(trace_id=t2.id, name="faithfulness", value=f2)])
        return r.id

    ra = _run(0.7, 0.8)  # 护理 0.7 / 睡眠 0.8
    rb = _run(0.8, 0.75)  # 护理 0.8 / 睡眠 0.75
    s.commit()
    s.close()

    data = client.get(f"/runs/{ra}/bucket-attribution", params={"baseline_run_id": rb}).json()
    by_bucket = {b["bucket"]: b["deltas"]["faithfulness"] for b in data["buckets"]}
    assert abs(by_bucket["护理"] - (-0.1)) < 1e-6  # 0.7 - 0.8
    assert abs(by_bucket["睡眠"] - 0.05) < 1e-6     # 0.8 - 0.75

    assert client.get(f"/runs/{ra}/bucket-attribution", params={"baseline_run_id": 999999}).status_code == 404


def test_model_comparison():
    # Ch19:按 chat_model 分组 done run;模型名带时间戳,避免共享库跨测试运行累积
    import time
    from backend.db import SessionLocal, init_db
    from backend.models import Dataset, DatasetItem, Run, Score, Trace

    init_db()
    s = SessionLocal()
    ds = Dataset(name="模型", description="")
    s.add(ds)
    s.flush()
    i1 = DatasetItem(dataset_id=ds.id, input="q1", expected_output="a", bucket="护理")
    s.add(i1)
    s.flush()

    def _run(model: str, score: float):
        r = Run(dataset_id=ds.id, status="done", config=json.dumps({"chat_model": model}))
        s.add(r)
        s.flush()
        t = Trace(run_id=r.id, dataset_item_id=i1.id, input="q1", output="o", retrieved_context="c")
        s.add(t)
        s.flush()
        s.add(Score(trace_id=t.id, name="faithfulness", value=score))

    ma = f"model-a-{time.time_ns()}"
    mb = f"model-b-{time.time_ns()}"
    _run(ma, 0.8)
    _run(ma, 0.9)
    _run(mb, 0.95)
    s.commit()
    s.close()

    data = client.get("/runs/model-comparison").json()
    by_model = {m["model"]: m for m in data["models"]}
    assert by_model[ma]["run_count"] == 2
    assert abs(by_model[ma]["avg_scores"]["faithfulness"] - 0.85) < 1e-6
    assert by_model[mb]["run_count"] == 1
    assert abs(by_model[mb]["avg_scores"]["faithfulness"] - 0.95) < 1e-6
    assert by_model[ma]["avg_cost"] == 0.0  # 无 generation 计量,成本为 0
