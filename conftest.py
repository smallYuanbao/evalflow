"""pytest 全局配置(根 conftest,最先加载)。

Ch22 测试隔离:测试用独立数据库,绝不污染 dev 的 data/eval.db。

**必须在任何 backend import 之前设置**——`backend.db` 在 import 时按
`settings.database_url` 建好 engine,之后再改就晚了。根 conftest 由 pytest 最先加载,
这里就是设它的正确位置(放 tests/conftest.py 会晚一步,因为根 conftest 先执行)。
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///data/test.db")

import pytest  # noqa: E402

from backend.db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ensure_tables():
    init_db()
