"""add calendar notes

Revision ID: b84d2f06a731
Revises: f7a1c4d8e902
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b84d2f06a731"
down_revision: Union[str, Sequence[str], None] = "f7a1c4d8e902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_calendar_notes_id"), "calendar_notes", ["id"], unique=False)
    op.create_index(op.f("ix_calendar_notes_note_date"), "calendar_notes", ["note_date"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_calendar_notes_note_date"), table_name="calendar_notes")
    op.drop_index(op.f("ix_calendar_notes_id"), table_name="calendar_notes")
    op.drop_table("calendar_notes")
