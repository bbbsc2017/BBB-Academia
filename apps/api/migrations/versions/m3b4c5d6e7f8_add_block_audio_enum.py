"""add BLOCK_AUDIO to blocktypeenum

Revision ID: m3b4c5d6e7f8
Revises: l2a3b4c5d6e7
Create Date: 2026-02-11

"""
from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'm3b4c5d6e7f8'
down_revision: str | None = 'l2a3b4c5d6e7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE blocktypeenum ADD VALUE IF NOT EXISTS 'BLOCK_AUDIO'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # A full enum recreation would be needed, but is rarely worth the risk.
    pass
