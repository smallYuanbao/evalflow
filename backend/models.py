from datetime import datetime

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


def _now() -> str:
    """created_at 默认时间戳:列表要按先后显示,不依赖 DB 端函数。"""
    return datetime.now().isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text, default="")
    created_at = Column(String, default=_now)
    updated_at = Column(String, default=_now)  # 修改时间:加样本时刷新,列表按它倒序
    items = relationship("DatasetItem", back_populates="dataset")


class DatasetItem(Base):
    __tablename__ = "dataset_items"
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    input = Column(Text)
    expected_output = Column(Text)      # ground truth 要点(召回用)
    bucket = Column(String)             # 分桶标签
    gold_scores = Column(Text, default=None)  # Ch18:人工金标准 JSON,如 {"faithfulness": 0.9}(校准用)
    dataset = relationship("Dataset", back_populates="items")


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    status = Column(String, default="running")  # running / done / failed
    config = Column(Text, default="{}")         # 配置快照 JSON
    progress = Column(Integer, default=0)       # 已完成样本数(进度,Ch10)
    created_at = Column(String, default=_now)


class Trace(Base):
    __tablename__ = "traces"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"))
    dataset_item_id = Column(Integer, ForeignKey("dataset_items.id"))
    input = Column(Text)
    output = Column(Text)
    retrieved_context = Column(Text)   # 检索证据(忠实度要用)
    retrieval_hits = Column(Text, default="[]")  # 检索命中 JSON:[{text, score, rank}]
    latency_ms = Column(Integer, default=0)
    created_at = Column(String, default=_now)


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
    created_at = Column(String, default=_now)
