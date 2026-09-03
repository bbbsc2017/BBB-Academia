"""add CODE to assignmenttasktypeenum

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2026-04-12

"""
from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'w2x3y4z5a6b7'
down_revision: str | None = 'v1w2x3y4z5a6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE assignmenttasktypeenum ADD VALUE IF NOT EXISTS 'CODE'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    pass
