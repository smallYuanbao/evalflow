"""add gold_scores to dataset_items

Revision ID: d2b407a6a412
Revises: 8c8e8985efef
Create Date: 2026-10-12 11:38:09.560612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b407a6a412'
down_revision: Union[str, None] = '8c8e8985efef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 只加 gold_scores 一列(Ch18 校准)。autogenerate 顺手带的 retrieval_hits VARCHAR→Text
    # 是历史 create_all 与模型的类型漂移,与本章无关且 SQLite 上 alter type 有风险,手动剔除。
    op.add_column('dataset_items', sa.Column('gold_scores', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('dataset_items', 'gold_scores')
