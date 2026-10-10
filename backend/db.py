from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.models import Base

_ROOT = Path(__file__).resolve().parent.parent  # 仓库根(alembic.ini / migrations 在这)


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite 不会自动建目录,data/ 不存在时连接会炸。这里在建 engine 前先建好。"""
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):]
        if db_path and db_path != ":memory:":
            parent = Path(db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

# check_same_thread 是 SQLite 专属参数,psycopg 不认;按方言只在 SQLite 时传(Ch14 方言分支)
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)


if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, connection_record):
        """SQLite 连接初始化:外键 + WAL(读写并发)+ busy_timeout(写锁等待,防 database is locked)。

        PRAGMA 是 SQLite 专属,PostgreSQL 没有;整个事件只在 SQLite 方言下注册。
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine)


def _alembic_config() -> Config:
    """构造 alembic 配置:script_location 用绝对路径,不依赖 cwd;URL 由 env.py 直读 settings。"""
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "migrations"))
    return cfg


def init_db() -> None:
    """建表/迁移:跑 alembic upgrade head(替代 create_all + 手写 _migrate)。

    存量库兼容:老库是 create_all 建的,有表但没有 alembic_version,先 stamp head「收养」,
    否则 upgrade head 会因「表已存在」报错。幂等:已迁移过的库再跑是无操作。

    探测与迁移都走 settings.database_url(而非模块级 engine),保证一致、也便于测试指到临时库。
    """
    url = settings.database_url
    _ensure_sqlite_dir(url)
    cfg = _alembic_config()
    with create_engine(url).connect() as conn:
        tables = inspect(conn).get_table_names()
    if tables and "alembic_version" not in tables:
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
