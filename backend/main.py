from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace
from backend.run_service import execute_run
from backend.stats import aggregate_run


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="EvalFlow", version="0.2.0", lifespan=lifespan)


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
    s.commit()
    s.refresh(it)
    s.close()
    return {"id": it.id, "input": it.input, "bucket": it.bucket}


@app.get("/datasets")
def list_datasets():
    s = SessionLocal()
    ds = s.query(Dataset).all()
    s.close()
    return [{"id": d.id, "name": d.name, "description": d.description} for d in ds]


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
                    "latency_ms": tr.latency_ms, "scores": scs})
    s.close()
    return out
