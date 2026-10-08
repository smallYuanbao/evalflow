import pytest

from backend.db import init_db


@pytest.fixture(scope="session", autouse=True)
def _ensure_tables():
    init_db()
