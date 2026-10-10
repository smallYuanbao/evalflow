from sqlalchemy import create_engine, inspect

from backend.config import settings
from backend.db import init_db
from backend.models import Base

# 迁移应该建出的 6 张业务表 + alembic 版本表
ALL_TABLES = {"datasets", "dataset_items", "runs", "traces", "generations", "scores", "alembic_version"}


def _tables(url: str) -> set[str]:
    return set(inspect(create_engine(url)).get_table_names())


def test_init_db_creates_schema_on_fresh_db(tmp_path, monkeypatch):
    # 全新 SQLite:init_db 应跑 alembic 建出全部表 + 版本表
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    monkeypatch.setattr(settings, "database_url", url)

    init_db()

    assert ALL_TABLES <= _tables(url)


def test_init_db_adopts_existing_db(tmp_path, monkeypatch):
    # 模拟老库:create_all 建了表但没有 alembic_version;init_db 应 stamp 收养而非报「表已存在」
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    Base.metadata.create_all(create_engine(url))  # 老 create_all 产物,无版本表

    init_db()  # 不抛异常即通过

    tables = _tables(url)
    assert ALL_TABLES <= tables  # 老表保留 + 版本表补上
