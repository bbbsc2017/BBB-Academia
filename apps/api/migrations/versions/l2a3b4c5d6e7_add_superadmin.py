"""add superadmin field to user

Revision ID: l2a3b4c5d6e7
Revises: k1f2a3b4c5d6
Create Date: 2026-02-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'l2a3b4c5d6e7'
down_revision: str | None = 'k1f2a3b4c5d6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('user', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('user', 'is_superadmin')
