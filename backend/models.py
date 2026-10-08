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
