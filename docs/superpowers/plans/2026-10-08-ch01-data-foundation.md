# EvalFlow Ch01 评测数据地基 Implementation Plan

> **For agentic workers:** 按 task 顺序逐个执行。步骤用 checkbox（`- [ ]`）语法追踪进度。每个 task 完成即 commit。

**Goal:** 跑通评测平台数据地基:6 张表 + demo 管线(mock) + seed 脚本。能存数据、能查数据、管线返回结构正确。

**Architecture:** 单进程 FastAPI(:8000) + SQLite 单文件 `data/eval.db`,SQLAlchemy ORM。本章无业务接口,只有 `GET /health`;数据经 `seed.py` 直接写库。

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy, pydantic-settings, pytest。

**Spec:** `docs/superpowers/specs/2026-10-08-ch01-data-foundation-design.md`

## Global Constraints

- 技术选型定死:FastAPI + SQLAlchemy + SQLite,发现走不通停下问用户,不许换方案。
- 管线 `run_pipeline` 先 mock(返回固定 context/output),不调真实模型,**本章不需要任何密钥**。
- 数据模型 3 个硬约束(照 spec):`scores.value` 可空(NULL=没评上)、`runs.config` 存 JSON 快照、`dataset_items.bucket` 分桶。
- 后端包在 `backend/` 下,目录结构照 spec。
- 单测用 pytest,不碰真实模型。
- 每个 task 完成即 commit,message 描述清晰。
- 前端不在本章范围。

---

### Task 1: 项目脚手架与配置加载

**Files:**
- Create: `pyproject.toml`(uv init 后改)
- Create: `.gitignore`, `.env.example`
- Create: `backend/__init__.py`, `backend/config.py`
- Create: `backend/main.py`(GET /health)
- Create: `scripts/dev.sh`
- Test: `tests/test_health.py`

**Interfaces:**
- `backend/config.py`: pydantic-settings 的 `Settings`;字段 `database_url: str = "sqlite:///data/eval.db"`、`chat_model: str = ""`、`chat_base_url: str = ""`、`chat_api_key: str = ""`(这三项给空默认,第 2 章接 judge 才填);模块级单例 `settings = Settings()`。
- `backend/main.py`: FastAPI app,`GET /health` 返回 `{"status": "ok"}`。

- [ ] **Step 1: uv 初始化与依赖**

```bash
cd /Users/lidong/Desktop/workFile/evalflow
git init
uv init --python 3.12 --name evalflow --bare
uv add fastapi "uvicorn[standard]" sqlalchemy pydantic-settings
uv add --dev pytest pytest-asyncio httpx
```

`pyproject.toml` 追加:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: .gitignore 与 .env.example**

`.gitignore`:

```
.venv/
__pycache__/
*.pyc
.env
data/
.pytest_cache/
```

`.env.example`:

```
# 第 2 章接真实 judge 才填,本章留空
CHAT_MODEL=
CHAT_BASE_URL=
CHAT_API_KEY=
```

- [ ] **Step 3: config.py**

`backend/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/eval.db"
    chat_model: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 4: main.py + /health**

`backend/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="EvalFlow", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: dev.sh**

`scripts/dev.sh`:

```bash
#!/usr/bin/env bash
set -e
mkdir -p data
uv run uvicorn backend.main:app --port 8000 --reload
```

`chmod +x scripts/dev.sh`。

- [ ] **Step 6: 测试**

`tests/test_health.py`:

```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}
```

运行 `uv run pytest` 通过,commit。

---

### Task 2: 数据模型建表(6 张表)

**Files:**
- Create: `backend/db.py`(engine + session + init_db)
- Create: `backend/models.py`(6 个 ORM 模型)
- Test: `tests/test_models.py`

**Interfaces:**
- 6 个 SQLAlchemy 模型:`Dataset` / `DatasetItem` / `Run` / `Trace` / `Generation` / `Score`,字段照 spec 的数据模型表。
- `db.init_db()` 建表;`db.SessionLocal` 是 session 工厂。

**面试要点(要能复述):**
- `scores.value` 为什么可空——区分「0 分」和「judge 挂了没评上」,失败样本不污染分数。
- `runs.config` 为什么存 JSON 快照——对比「改提示词/换模型前后」需要每轮当时的配置。

- [ ] **Step 1: db.py**

```python
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.models import Base


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite 不会自动建目录,data/ 不存在时连接会炸。这里在建 engine 前先建好。"""
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):]
        if db_path and db_path != ":memory:":
            parent = Path(db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite 单文件,允许跨线程
)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    """SQLite 默认不强制外键,每个连接都要开 PRAGMA foreign_keys=ON。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)
```

- [ ] **Step 2: models.py**

```python
from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text, default="")
    created_at = Column(String)
    items = relationship("DatasetItem", back_populates="dataset")


class DatasetItem(Base):
    __tablename__ = "dataset_items"
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    input = Column(Text)
    expected_output = Column(Text)      # ground truth 要点(召回用)
    bucket = Column(String)             # 分桶标签
    dataset = relationship("Dataset", back_populates="items")


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    status = Column(String, default="running")  # running / done / failed
    config = Column(Text, default="{}")         # 配置快照 JSON
    created_at = Column(String)


class Trace(Base):
    __tablename__ = "traces"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"))
    dataset_item_id = Column(Integer, ForeignKey("dataset_items.id"))
    input = Column(Text)
    output = Column(Text)
    retrieved_context = Column(Text)   # 检索证据(忠实度要用)
    latency_ms = Column(Integer, default=0)
    created_at = Column(String)


class Generation(Base):
    __tablename__ = "generations"
    id = Column(Integer, primary_key=True)
    trace_id = Column(Integer, ForeignKey("traces.id"))
    model = Column(String)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)


class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True)
    trace_id = Column(Integer, ForeignKey("traces.id"))
    name = Column(String)                 # faithfulness / recall / ...
    value = Column(Float, nullable=True)  # NULL = 没评上(别记 0)
    comment = Column(Text, default="")
    created_at = Column(String)
```

- [ ] **Step 3: 测试**

`tests/test_models.py`:

```python
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.db import SessionLocal, engine, init_db
from backend.models import DatasetItem


def test_tables_created():
    init_db()
    names = set(inspect(engine).get_table_names())
    assert {"datasets", "dataset_items", "runs", "traces", "generations", "scores"} <= names


def test_score_value_nullable():
    init_db()
    # 用 SQLAlchemy 反射确认 scores.value 可空
    cols = {c["name"]: c for c in inspect(engine).get_columns("scores")}
    assert cols["value"]["nullable"] is True


def test_foreign_key_enforced():
    init_db()
    s = SessionLocal()
    # dataset_id=99999 不存在,开 PRAGMA 后这条插入应当被外键拦住
    s.add(DatasetItem(dataset_id=99999, input="孤儿样本", expected_output="", bucket="x"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
    s.close()
```

运行 `uv run pytest` 通过,commit。

---

### Task 3: demo 管线(run_pipeline, mock)

**Files:**
- Create: `backend/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- `run_pipeline(question: str) -> dict`:返回 `{"output": str, "retrieved_context": str}`。Ch01 是 mock,不调真实检索/模型;第 2 章换成真实管线(签名不变)。

**面试要点(要能复述):**
- 为什么先 mock——先跑通「数据能存」这条流,别一上来卡在检索管线;签名固定,第 2 章只换实现不换调用方。

- [ ] **Step 1: pipeline.py**

```python
def run_pipeline(question: str) -> dict:
    """检索 + 生成。Ch01 mock:返回固定结构,第 2 章换真实实现(签名不变)。"""
    return {
        "output": f"(mock)对「{question}」的回答",
        "retrieved_context": "(mock)检索到的证据片段",
    }
```

- [ ] **Step 2: 测试**

`tests/test_pipeline.py`:

```python
from backend.pipeline import run_pipeline


def test_run_pipeline_shape():
    r = run_pipeline("测试")
    assert set(r.keys()) == {"output", "retrieved_context"}
    assert isinstance(r["output"], str) and isinstance(r["retrieved_context"], str)
```

运行 `uv run pytest` 通过,commit。

---

### Task 4: seed 脚本 + 打通插数据

**Files:**
- Create: `backend/seed.py`

**Interfaces:**
- `seed()`:插入 1 个 dataset + 3 条 item(带 bucket)+ 1 个 run + 2 条 trace + 几个 score(含一个 `value=None` 验证可空)。
- 作为入口 `python -m backend.seed` 运行。

- [ ] **Step 1: seed.py**

```python
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace
from backend.pipeline import run_pipeline


def seed() -> None:
    init_db()
    s = SessionLocal()
    ds = Dataset(name="育儿-常见病", description="示例评测集")
    s.add(ds)
    s.flush()

    items = [
        DatasetItem(dataset_id=ds.id, input="宝宝发烧38度怎么办",
                    expected_output="物理降温/就医指征/用药", bucket="护理"),
        DatasetItem(dataset_id=ds.id, input="6个月能加辅食吗",
                    expected_output="月龄标准/首选食物", bucket="喂养"),
        DatasetItem(dataset_id=ds.id, input="宝宝晚上总醒怎么回事",
                    expected_output="睡眠倒退/出牙/环境", bucket="睡眠"),
    ]
    s.add_all(items)
    s.flush()

    run = Run(dataset_id=ds.id, status="done", config='{"model": "mock"}')
    s.add(run)
    s.flush()

    for i, it in enumerate(items[:2]):
        out = run_pipeline(it.input)
        tr = Trace(run_id=run.id, dataset_item_id=it.id,
                   input=it.input, output=out["output"],
                   retrieved_context=out["retrieved_context"], latency_ms=100)
        s.add(tr)
        s.flush()
        s.add(Score(trace_id=tr.id, name="faithfulness", value=4.5, comment="mock"))
        if i == 0:
            # 验证 scores.value 可空:这条 judge 挂了,记 NULL 不记 0
            s.add(Score(trace_id=tr.id, name="recall", value=None, comment="judge 未评上"))

    s.commit()
    s.close()


if __name__ == "__main__":
    seed()
```

- [ ] **Step 2: 验证**

```bash
uv run python -m backend.seed
uv run python -c "
from backend.db import SessionLocal
from backend.models import Dataset, DatasetItem, Run, Trace, Score
s = SessionLocal()
print('datasets/items/runs/traces/scores:',
      s.query(Dataset).count(), s.query(DatasetItem).count(), s.query(Run).count(),
      s.query(Trace).count(), s.query(Score).count())
print('null-value scores:', s.query(Score).filter(Score.value.is_(None)).count())
s.close()
"
```

用 SQL 确认:1 个 dataset、3 条 item、1 个 run、2 条 trace、score 关联正确,且有一条 `value IS NULL` 的 score。commit。
