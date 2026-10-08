from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
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
    _migrate(engine)


def _migrate(engine) -> None:
    """SQLite 的 create_all 不会给已存在的表加新列,这里补历史库缺的 updated_at。"""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("datasets")}
        if "updated_at" not in cols:
            conn.execute(text("ALTER TABLE datasets ADD COLUMN updated_at VARCHAR"))
            conn.execute(text("UPDATE datasets SET updated_at = created_at WHERE updated_at IS NULL"))
