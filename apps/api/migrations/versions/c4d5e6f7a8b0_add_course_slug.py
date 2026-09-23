"""Add slug to course

Human-readable course URLs (``/course/<slug>``). Existing rows are backfilled
on API startup (see ``backfill_course_slugs``).

Revision ID: c4d5e6f7a8b0
Revises: b367728d01e0
Create Date: 2026-09-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b0'
down_revision: str | Sequence[str] | None = 'b367728d01e0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('course', sa.Column('slug', sa.String(), nullable=True))
    op.create_index('ix_course_slug', 'course', ['slug'])


def downgrade() -> None:
    op.drop_index('ix_course_slug', table_name='course')
    op.drop_column('course', 'slug')
