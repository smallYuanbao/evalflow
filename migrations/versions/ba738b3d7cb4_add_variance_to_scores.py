"""add variance to scores

Revision ID: ba738b3d7cb4
Revises: 4b100c0ed478
Create Date: 2026-10-12 15:28:14.274373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba738b3d7cb4'
down_revision: Union[str, None] = '4b100c0ed478'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 只加 scores.variance(Ch20)。retrieval_hits 类型漂移是历史 create_all 遗留,再次剔除。
    op.add_column('scores', sa.Column('variance', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('scores', 'variance')
