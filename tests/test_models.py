from sqlalchemy import inspect

from backend.db import engine, init_db


def test_tables_created():
    init_db()
    names = set(inspect(engine).get_table_names())
    assert {"datasets", "dataset_items", "runs", "traces", "generations", "scores"} <= names


def test_score_value_nullable():
    init_db()
    # 用 SQLAlchemy 反射确认 scores.value 可空
    cols = {c["name"]: c for c in inspect(engine).get_columns("scores")}
    assert cols["value"]["nullable"] is True
