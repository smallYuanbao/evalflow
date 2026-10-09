import json
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func

from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace, _now
from backend.run_service import execute_run
from backend.stats import aggregate_run


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="EvalFlow", version="0.2.0", lifespan=lifespan)

# 前端 dev 在 5173,前后端分离要显式开 CORS(真实项目这是必答题)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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


@app.get("/datasets/{dataset_id}/items")
def list_items(dataset_id: int):
    s = SessionLocal()
    items = s.query(DatasetItem).filter(DatasetItem.dataset_id == dataset_id).all()
    s.close()
    return [{"id": it.id, "input": it.input, "expected_output": it.expected_output,
             "bucket": it.bucket} for it in items]


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
def create_run(body: RunIn, background: BackgroundTasks):
    s = SessionLocal()
    run = Run(dataset_id=body.dataset_id, status="running", config=body.config)
    s.add(run)
    s.commit()
    s.refresh(run)
    rid = run.id
    s.close()
    background.add_task(execute_run, rid)
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
             "created_at": r.created_at} for r in runs]


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    return aggregate_run(run_id)


@app.get("/runs/{run_id}/traces")
def list_traces(run_id: int):
    s = SessionLocal()
    out = []
    for tr in s.query(Trace).filter(Trace.run_id == run_id):
        scs = [{"name": sc.name, "value": sc.value}
               for sc in s.query(Score).filter(Score.trace_id == tr.id)]
        out.append({"trace_id": tr.id, "input": tr.input, "output": tr.output,
                    "retrieved_context": tr.retrieved_context,
                    "retrieval_hits": json.loads(tr.retrieval_hits or "[]"),
                    "latency_ms": tr.latency_ms, "scores": scs})
    s.close()
    return out


@app.get("/knowledge/map")
def knowledge_map():
    """知识库可视化:知识块拟合 PCA 基底,样本问题投影到同一 2D 坐标系。"""
    from backend.embedding import embed
    from backend.knowledge import KNOWLEDGE
    from backend.pca import fit_pca, project

    s = SessionLocal()
    inputs = [it.input for it in s.query(DatasetItem).all()]
    s.close()

    chunk_texts = [k["text"] for k in KNOWLEDGE]
    chunk_vecs = embed(chunk_texts)
    mean, basis = fit_pca(chunk_vecs)
    chunk_pts = project(chunk_vecs, mean, basis)
    query_pts = project(embed(inputs), mean, basis) if inputs else []

    chunks = [{"id": KNOWLEDGE[i]["id"], "text": KNOWLEDGE[i]["text"],
               "category": KNOWLEDGE[i]["category"],
               "x": round(chunk_pts[i][0], 4), "y": round(chunk_pts[i][1], 4)}
              for i in range(len(chunk_texts))]
    queries = [{"input": inputs[j],
                "x": round(query_pts[j][0], 4), "y": round(query_pts[j][1], 4)}
               for j in range(len(inputs))]
    return {"chunks": chunks, "queries": queries}
