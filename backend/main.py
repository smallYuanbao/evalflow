import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import func

from backend.celery_app import run_task
from backend.config import settings
from backend.db import SessionLocal, init_db
from backend.logging_config import setup_logging
from backend.models import Dataset, DatasetItem, Run, Score, Trace, _now
from backend.ratelimit import run_limiter
from backend.snapshot import build_snapshot, config_retrieval, config_top_k
from backend.stats import aggregate_run, run_export_csv, runs_trend
from backend.gate import evaluate_gate
from backend.calibration import calibration_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()  # API 进程也走结构化日志(Ch13)
    init_db()
    _recover_stale_runs()  # 重启后把残留 running 的 run 标记 failed(Ch10 兜底)
    yield


def _recover_stale_runs() -> None:
    """进程重启后,残留 running 的 run 视为中断,标记 failed,避免永久卡 running。"""
    s = SessionLocal()
    for r in s.query(Run).filter(Run.status == "running"):
        r.status = "failed"
    s.commit()
    s.close()


app = FastAPI(title="EvalFlow", version="0.2.0", lifespan=lifespan)


# 鉴权中间件(Ch12):校验 Authorization: Bearer <app_api_key>。
# 先注册 = 在 CORS 之内,这样 401 响应也带 CORS 头,前端能正确读到错误码(而非 CORS 报错)。
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if settings.app_api_key and request.url.path != "/health" and request.method != "OPTIONS":
        auth = request.headers.get("Authorization", "")
        token = auth[len("Bearer "):].strip() if auth.startswith("Bearer ") else ""
        if token != settings.app_api_key:
            return JSONResponse(status_code=401, content={"detail": "无效或缺失的 API Key"})
    return await call_next(request)


# 前端 dev 在 5173,e2e 用 5174(docker 前端容器占 5173),都要显式开 CORS(真实项目这是必答题)。
# 最后注册 = 最外层,让所有响应(含 401)都过一遍 CORS 加头。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DatasetIn(BaseModel):
    name: str
    description: str = ""


class ItemIn(BaseModel):
    input: str
    expected_output: str
    bucket: str = ""


class GoldIn(BaseModel):
    gold_scores: dict[str, float]  # metric -> 金标准分数(0~1),Ch18 校准


class RunIn(BaseModel):
    dataset_id: int
    config: str = "{}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/datasets")
def create_dataset(body: DatasetIn):
    s = SessionLocal()
    ds = Dataset(name=body.name, description=body.description)
    s.add(ds)
    s.commit()
    s.refresh(ds)
    s.close()
    return {"id": ds.id, "name": ds.name, "description": ds.description}


@app.post("/datasets/{dataset_id}/items")
def add_item(dataset_id: int, body: ItemIn):
    s = SessionLocal()
    it = DatasetItem(dataset_id=dataset_id, input=body.input,
                     expected_output=body.expected_output, bucket=body.bucket)
    s.add(it)
    ds = s.get(Dataset, dataset_id)
    if ds is not None:  # 加样本视为「修改」,刷新 updated_at 让列表按修改时间倒序
        ds.updated_at = _now()
    s.commit()
    s.refresh(it)
    s.close()
    return {"id": it.id, "input": it.input, "bucket": it.bucket}


def _parse_gold(raw: str | None) -> dict | None:
    """gold_scores 列(JSON 字符串)解析成 dict;空/坏数据返回 None。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@app.get("/datasets/{dataset_id}/items")
def list_items(dataset_id: int):
    s = SessionLocal()
    items = s.query(DatasetItem).filter(DatasetItem.dataset_id == dataset_id).all()
    s.close()
    return [{"id": it.id, "input": it.input, "expected_output": it.expected_output,
             "bucket": it.bucket, "gold_scores": _parse_gold(it.gold_scores)} for it in items]


@app.put("/datasets/{dataset_id}/items/{item_id}/gold")
def set_item_gold(dataset_id: int, item_id: int, body: GoldIn):
    """标金标准(Ch18 校准):给某条样本写人工分数 {"faithfulness": 0.9, ...}。"""
    s = SessionLocal()
    item = s.get(DatasetItem, item_id)
    if item is None or item.dataset_id != dataset_id:
        s.close()
        raise HTTPException(status_code=404, detail="样本不存在")
    item.gold_scores = json.dumps(body.gold_scores, ensure_ascii=False)
    s.commit()
    s.close()
    return {"id": item_id, "gold_scores": body.gold_scores}


@app.get("/datasets")
def list_datasets(page: int = 1, page_size: int = 10, search: str = ""):
    """评测集列表(后端分页)。search 按名称模糊过滤,供「发起评测」下拉远程搜索。"""
    s = SessionLocal()
    q = s.query(Dataset)
    if search:
        q = q.filter(Dataset.name.contains(search))
    total = q.count()
    ds = q.order_by(Dataset.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # 一次 GROUP BY 聚合样本数,避免逐条 count 的 N+1
    counts = dict(
        s.query(DatasetItem.dataset_id, func.count(DatasetItem.id))
         .filter(DatasetItem.dataset_id.in_([d.id for d in ds]))
         .group_by(DatasetItem.dataset_id).all()
    ) if ds else {}
    items = [{"id": d.id, "name": d.name, "description": d.description,
              "item_count": counts.get(d.id, 0), "updated_at": d.updated_at}
             for d in ds]
    s.close()
    return {"items": items, "total": total}


@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int):
    s = SessionLocal()
    d = s.get(Dataset, dataset_id)
    if d is None:
        s.close()
        raise HTTPException(status_code=404, detail="评测集不存在")
    count = s.query(DatasetItem).filter(DatasetItem.dataset_id == dataset_id).count()
    s.close()
    return {"id": d.id, "name": d.name, "description": d.description, "item_count": count}


@app.post("/runs")
def create_run(body: RunIn):
    # 限流(Ch12 防刷):发起评测烧钱,限频率,超限 429
    if not run_limiter.allow():
        raise HTTPException(status_code=429, detail="发起评测过于频繁,请稍后再试")
    # 复现上下文:发起时快照 top_k + retrieval + 知识库/prompt 版本 + 模型 + 数据集哈希,存进 config(Ch09/Ch16)
    config = build_snapshot(body.dataset_id, config_top_k(body.config), config_retrieval(body.config))
    s = SessionLocal()
    run = Run(dataset_id=body.dataset_id, status="running",
              config=json.dumps(config, ensure_ascii=False))
    s.add(run)
    s.commit()
    s.refresh(run)
    rid = run.id
    s.close()
    if settings.e2e_mock:
        # E2E 下同步执行,不走 celery/redis(Ch14):发完即 done,测试无需起 worker
        from backend.run_service import execute_run
        execute_run(rid)
    else:
        run_task.delay(rid)  # 入队由 Celery worker 消费(Ch10),不再用进程内 BackgroundTasks
    return {"id": rid, "status": "running"}


@app.get("/runs")
def list_runs():
    s = SessionLocal()
    runs = s.query(Run).order_by(Run.id.desc()).all()
    names = {}
    if runs:
        names = dict(s.query(Dataset.id, Dataset.name).filter(
            Dataset.id.in_({r.dataset_id for r in runs})))
    s.close()
    return [{"id": r.id, "dataset_id": r.dataset_id,
             "dataset_name": names.get(r.dataset_id),
             "status": r.status, "config": r.config,
             "progress": r.progress,
             "created_at": r.created_at} for r in runs]


@app.get("/runs/trend")
def get_runs_trend(limit: int = 50):
    """历史指标趋势:批量返回最近 N 个 run 的 per-metric 均值(Ch13)。

    注意:必须注册在 /runs/{run_id} 之前,否则 trend 会被当成 run_id 解析成 422。
    """
    return runs_trend(limit)


@app.get("/runs/model-comparison")
def model_comparison():
    """模型性价比(Ch19):按 chat_model 分组 done run,返回每模型 run 数/平均分/平均成本。

    同样必须注册在 /runs/{run_id} 之前(静态段会被动态段抢)。
    """
    s = SessionLocal()
    runs = s.query(Run).filter(Run.status == "done").all()
    s.close()

    by_model: dict[str, dict] = {}
    for r in runs:
        try:
            model = json.loads(r.config or "{}").get("chat_model") or "unknown"
        except (TypeError, json.JSONDecodeError):
            model = "unknown"
        d = by_model.setdefault(model, {"runs": [], "costs": [], "items": [], "scores": {}})
        agg = aggregate_run(r.id)
        d["runs"].append(r.id)
        d["costs"].append(agg["cost"])
        d["items"].append(agg["item_count"])
        for m, v in agg["scores"].items():
            if v is not None:
                d["scores"].setdefault(m, []).append(v)

    models = []
    for model, d in by_model.items():
        n = len(d["runs"])
        avg_cost = round(sum(d["costs"]) / n, 6) if n else 0.0
        avg_items = sum(d["items"]) / n if n else 0
        models.append({
            "model": model,
            "run_count": n,
            "avg_cost": avg_cost,
            "avg_cost_per_item": round(avg_cost / avg_items, 8) if avg_items else 0.0,
            "avg_scores": {m: round(sum(v) / len(v), 4) for m, v in d["scores"].items()},
        })
    return {"models": models}


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    return aggregate_run(run_id)


@app.get("/runs/{run_id}/gate")
def get_run_gate(run_id: int, baseline_run_id: int | None = None):
    """回归门禁(Ch15):对 run 聚合指标套规则,给 PASS/FAIL;可选基线 run 做相对回归。

    读时计算、不落库;baseline 不存在返回 404(「和谁比」由调用方显式指定)。
    """
    s = SessionLocal()
    run_exists = s.get(Run, run_id) is not None
    baseline_exists = baseline_run_id is None or s.get(Run, baseline_run_id) is not None
    s.close()
    if not run_exists:
        raise HTTPException(status_code=404, detail="run 不存在")
    if not baseline_exists:
        raise HTTPException(status_code=404, detail="基线 run 不存在")

    scores = aggregate_run(run_id)["scores"]
    baseline_scores = aggregate_run(baseline_run_id)["scores"] if baseline_run_id is not None else None
    return {
        **evaluate_gate(scores, baseline_scores),
        "run_id": run_id,
        "baseline_run_id": baseline_run_id,
    }


@app.get("/runs/{run_id}/bucket-attribution")
def bucket_attribution(run_id: int, baseline_run_id: int):
    """分桶归因(Ch19):和基线比,每个 bucket 的逐指标 delta,定位「哪个桶拖后腿」。"""
    s = SessionLocal()
    run_ok = s.get(Run, run_id) is not None
    base_ok = s.get(Run, baseline_run_id) is not None
    s.close()
    if not run_ok or not base_ok:
        raise HTTPException(status_code=404, detail="run 不存在")

    agg = aggregate_run(run_id)
    base = aggregate_run(baseline_run_id)
    metrics = list(agg["scores"].keys())  # 指标按注册表顺序
    a, b = agg["by_bucket"], base["by_bucket"]
    buckets = []
    for bucket in sorted(set(a) | set(b)):
        deltas = {}
        for m in metrics:
            av = a.get(bucket, {}).get(m)
            bv = b.get(bucket, {}).get(m)
            if av is not None and bv is not None:
                deltas[m] = round(av - bv, 4)
        buckets.append({"bucket": bucket, "count": a.get(bucket, {}).get("count"), "deltas": deltas})
    return {"run_id": run_id, "baseline_run_id": baseline_run_id, "buckets": buckets}


@app.get("/runs/{run_a_id}/diff/{run_b_id}")
def diff_runs(run_a_id: int, run_b_id: int):
    """逐条 diff(Ch18):按 dataset_item_id 匹配两条 run 的 trace,返回并排 + 逐指标 delta。

    用 dataset_item_id 而非 input:input 文本不唯一(重复样本会错配),item_id 才是同一条样本的身份。
    两 run 不同数据集时返回 different_datasets 标记,前端提示「逐条对比无意义」,不静默错配。
    """
    s = SessionLocal()
    run_a = s.get(Run, run_a_id)
    run_b = s.get(Run, run_b_id)
    if run_a is None or run_b is None:
        s.close()
        raise HTTPException(status_code=404, detail="run 不存在")
    different = run_a.dataset_id != run_b.dataset_id

    def _traces(run_id: int) -> dict[int, dict]:
        traces = s.query(Trace).filter(Trace.run_id == run_id).all()
        tids = [t.id for t in traces]
        scores_by_trace: dict[int, dict] = {}
        if tids:
            for sc in s.query(Score).filter(Score.trace_id.in_(tids)):
                scores_by_trace.setdefault(sc.trace_id, {})[sc.name] = sc.value
        out = {}
        for tr in traces:
            out[tr.dataset_item_id] = {
                "trace_id": tr.id,
                "output": tr.output,
                "retrieved_context": tr.retrieved_context,
                "retrieval_hits": json.loads(tr.retrieval_hits or "[]"),
                "scores": scores_by_trace.get(tr.id, {}),
            }
        return out

    ta = _traces(run_a_id)
    tb = _traces(run_b_id)
    item_ids = set(ta) | set(tb)
    inputs = dict(s.query(DatasetItem.id, DatasetItem.input)
                  .filter(DatasetItem.id.in_(item_ids))) if item_ids else {}
    s.close()

    pairs = []
    for iid in sorted(item_ids):
        a, b = ta.get(iid), tb.get(iid)
        deltas = {}
        if a and b:
            for m in set(a["scores"]) | set(b["scores"]):
                av, bv = a["scores"].get(m), b["scores"].get(m)
                if av is not None and bv is not None:
                    deltas[m] = round(bv - av, 4)
        pairs.append({
            "item_id": iid,
            "input": inputs.get(iid),
            "a": a,
            "b": b,
            "deltas": deltas,
        })

    return {
        "run_a_id": run_a_id,
        "run_b_id": run_b_id,
        "different_datasets": different,
        "pairs": pairs,
    }


@app.get("/runs/{run_id}/calibration")
def get_run_calibration(run_id: int):
    """校准报告(Ch18):比对 run 的 judge 分 vs 样本金标准,算 bias/MAE/Pearson/n。"""
    report = calibration_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    return report


@app.get("/runs/{run_id}/export")
def export_run(run_id: int):
    """导出某 run 的逐 trace 明细为 CSV(Ch13 供外部分析)。"""
    csv_text = run_export_csv(run_id)
    if not csv_text:
        raise HTTPException(status_code=404, detail="run 不存在或没有明细")
    # BOM:让 Excel 正确识别 UTF-8,中文不乱码
    return Response(
        content="﻿" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}.csv"},
    )


@app.get("/runs/{run_id}/traces")
def list_traces(run_id: int):
    s = SessionLocal()
    out = []
    for tr in s.query(Trace).filter(Trace.run_id == run_id):
        scs = [{"name": sc.name, "value": sc.value, "comment": sc.comment, "variance": sc.variance}
               for sc in s.query(Score).filter(Score.trace_id == tr.id)]
        out.append({"trace_id": tr.id, "input": tr.input, "output": tr.output,
                    "retrieved_context": tr.retrieved_context,
                    "retrieval_hits": json.loads(tr.retrieval_hits or "[]"),
                    "latency_ms": tr.latency_ms, "scores": scs})
    s.close()
    return out


@app.get("/knowledge/map")
def knowledge_map():
    """知识库可视化:知识块拟合 PCA 基底,样本问题投影到同一 2D 坐标系(Ch04)。

    实现见 backend/knowledge_map.py:知识库部分缓存、样本部分有界(Ch21 性能修复)。
    """
    from backend.knowledge_map import knowledge_map as _build

    return _build()
