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
