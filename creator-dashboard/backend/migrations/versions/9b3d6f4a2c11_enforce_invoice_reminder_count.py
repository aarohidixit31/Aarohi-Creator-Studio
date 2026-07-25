"""enforce invoice reminder count

Revision ID: 9b3d6f4a2c11
Revises: e260ea97b054
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b3d6f4a2c11"
down_revision: Union[str, Sequence[str], None] = "e260ea97b054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE invoices SET reminder_count = 0 WHERE reminder_count IS NULL")
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.alter_column(
            "reminder_count",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.alter_column(
            "reminder_count",
            existing_type=sa.Integer(),
            nullable=True,
        )
