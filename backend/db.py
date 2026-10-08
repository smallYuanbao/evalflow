from pathlib import Path

from sqlalchemy import create_engine
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
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)
