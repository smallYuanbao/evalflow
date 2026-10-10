"""Alembic 迁移环境:URL 直读 backend.config.settings(而非 ini 写死)。

把仓库根加进 sys.path,让 `from backend...` 在任意 cwd(本地 / Docker / 部署机)都能导入。
"""
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

# 仓库根(本文件在 migrations/ 下,再上一级就是仓库根)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.config import settings  # noqa: E402
from backend.models import Base       # noqa: E402

config = context.config

# alembic autogenerate / upgrade 都用这套模型元数据做「目标 schema」
target_metadata = Base.metadata


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite 不会自动建目录;独立跑 alembic 时(不经 app 的 init_db)也要保证 data/ 存在。"""
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):]
        if db_path and db_path != ":memory:":
            parent = Path(db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    """离线模式:不连库,把迁移渲染成 SQL 文本(审阅 / 交给 DBA 执行)。"""
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式:连库执行迁移。"""
    url = settings.database_url
    _ensure_sqlite_dir(url)
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
