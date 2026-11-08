"""残留 run 回收:按心跳/创建时间超时判定,不再一启动就清空 running。

背景:API 用 `--reload` 时,改任何文件都会触发 lifespan;旧实现会把 worker
仍在执行的 run 标成 failed(2026-10-18 实测)。现在只回收没有心跳的。
"""

from datetime import datetime, timedelta

from backend.db import SessionLocal
from backend.main import _recover_stale_runs
from backend.models import Dataset, Run


def _mk_run(status: str = "running", heartbeat: str | None = None,
            progress_at: str | None = None, created: str | None = None) -> int:
    s = SessionLocal()
    ds = Dataset(name="stale-test", description="")
    s.add(ds)
    s.flush()
    r = Run(
        dataset_id=ds.id,
        status=status,
        config="{}",
        last_heartbeat_at=heartbeat,
        last_progress_at=progress_at,
        created_at=created or datetime.now().isoformat(timespec="seconds"),
    )
    s.add(r)
    s.commit()
    rid = r.id
    s.close()
    return rid


def _status(rid: int) -> str:
    s = SessionLocal()
    value = s.get(Run, rid).status
    s.close()
    return value


def test_fresh_heartbeat_survives_api_restart():
    """worker 还在跑(心跳新鲜)→ API 重启不能把它标 failed。"""
    rid = _mk_run(heartbeat=datetime.now().isoformat(timespec="seconds"))
    _recover_stale_runs()
    assert _status(rid) == "running"


def test_fresh_heartbeat_but_stale_progress_marked_failed():
    """进程活着但主流程卡死:心跳还在跳,进度超过 progress_timeout 不动 → 回收。"""
    now = datetime.now()
    rid = _mk_run(
        heartbeat=now.isoformat(timespec="seconds"),
        progress_at=(now - timedelta(minutes=40)).isoformat(timespec="seconds"),
    )
    _recover_stale_runs()
    assert _status(rid) == "failed"


def test_stale_heartbeat_marked_failed():
    """超过 stale_run_timeout 没心跳 → 视为残留。"""
    old = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
    rid = _mk_run(heartbeat=old)
    _recover_stale_runs()
    assert _status(rid) == "failed"


def test_missing_heartbeat_falls_back_to_created_at():
    """老库没有心跳字段值:用 created_at 兜底。"""
    old = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
    fresh = datetime.now().isoformat(timespec="seconds")
    old_rid = _mk_run(heartbeat=None, created=old)
    fresh_rid = _mk_run(heartbeat=None, created=fresh)

    _recover_stale_runs()

    assert _status(old_rid) == "failed"
    assert _status(fresh_rid) == "running"


def test_finished_runs_untouched():
    old = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
    rid = _mk_run(status="done", heartbeat=old)
    _recover_stale_runs()
    assert _status(rid) == "done"
