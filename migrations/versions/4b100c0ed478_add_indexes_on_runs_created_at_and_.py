"""add indexes on runs.created_at and traces.run_id

Revision ID: 4b100c0ed478
Revises: d2b407a6a412
Create Date: 2026-10-12 11:57:42.388113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b100c0ed478'
down_revision: Union[str, None] = 'd2b407a6a412'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 只建两个索引(Ch19)。autogenerate 又带的 retrieval_hits 类型漂移是历史 create_all
    # 与模型的差异,与本章无关且 SQLite 上 alter type 有风险,再次手动剔除。
    op.create_index(op.f('ix_runs_created_at'), 'runs', ['created_at'], unique=False)
    op.create_index(op.f('ix_traces_run_id'), 'traces', ['run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_traces_run_id'), table_name='traces')
    op.drop_index(op.f('ix_runs_created_at'), table_name='runs')
