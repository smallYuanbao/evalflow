"""add last_heartbeat_at to runs

残留 run 回收改为心跳判定:worker 每 10s 刷新一次,API 启动时只回收
超过 stale_run_timeout 没有心跳的 run,避免把执行中的 run 误标 failed。

Revision ID: e5a9c1b7d2f3
Revises: ba738b3d7cb4
Create Date: 2026-10-19 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a9c1b7d2f3'
down_revision: Union[str, None] = 'ba738b3d7cb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("last_heartbeat_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "last_heartbeat_at")
