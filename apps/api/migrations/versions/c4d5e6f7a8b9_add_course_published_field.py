"""Add course published field

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2025-01-28 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: str | None = 'b3c4d5e6f7a8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add published column to course table with default value of False
    op.add_column('course', sa.Column('published', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('course', 'published')
