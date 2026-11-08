"""add last_progress_at to runs

心跳只能证明 worker 进程活着;进程卡死时心跳线程仍可能继续跑。
再加一个「最近一次样本完成」的时间,两个信号都超时才回收。

Revision ID: f0b1c2d3e4a5
Revises: e5a9c1b7d2f3
Create Date: 2026-10-19 00:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0b1c2d3e4a5'
down_revision: Union[str, None] = 'e5a9c1b7d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("last_progress_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "last_progress_at")
