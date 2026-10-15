"""Enable correct-answer feedback for published assignments."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'z6b7c8d9e0f1'
down_revision: str | None = 'z5a6b7c8d9e0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'assignment' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('assignment')}
    if 'show_correct_answers' not in columns:
        return

    op.execute(sa.text(
        'UPDATE assignment '
        'SET show_correct_answers = TRUE '
        'WHERE published = TRUE'
    ))
    op.alter_column(
        'assignment',
        'show_correct_answers',
        existing_type=sa.Boolean(),
        existing_nullable=True,
        server_default=sa.true(),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'assignment' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('assignment')}
    if 'show_correct_answers' not in columns:
        return

    op.alter_column(
        'assignment',
        'show_correct_answers',
        existing_type=sa.Boolean(),
        existing_nullable=True,
        server_default=sa.false(),
    )
