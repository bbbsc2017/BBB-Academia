"""Add is_active to userorganization (and merge open heads)

Adds ``userorganization.is_active`` (default True) so an org admin can
deactivate a member's access without deleting their membership or account —
used by the bbbsc participant-import feature to let staff pause a student's
course access without losing their enrollment/group history.

The migration tree had multiple open heads when this was authored; this
revision also merges them (like the prior merge migrations in this project)
so ``alembic upgrade head`` resolves to a single head again.

Revision ID: b367728d01e0
Revises: (merges both open heads — see down_revision tuple)
Create Date: 2026-09-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b367728d01e0'
down_revision: str | Sequence[str] | None = (
    'p8q9r0s1t2u3',
    'r5s6t7u8v9w0',
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'userorganization',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('userorganization', 'is_active')
