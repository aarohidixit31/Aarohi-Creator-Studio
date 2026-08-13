"""add collaboration archiving

Revision ID: c21e7a914d04
Revises: a7c4e9f2b118
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c21e7a914d04"
down_revision: Union[str, Sequence[str], None] = "a7c4e9f2b118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("collabs", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("collabs", "archived_at")
