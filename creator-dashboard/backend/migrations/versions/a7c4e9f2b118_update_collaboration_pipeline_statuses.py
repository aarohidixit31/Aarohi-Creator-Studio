"""update collaboration pipeline statuses

Revision ID: a7c4e9f2b118
Revises: e5d69d6a6de3
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a7c4e9f2b118"
down_revision: Union[str, Sequence[str], None] = "e5d69d6a6de3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE collabs SET status = 'new' WHERE status = 'new_inquiry'")
    op.execute("UPDATE collabs SET status = 'content_posted' WHERE status = 'content_live'")
    op.execute("UPDATE collabs SET status = 'agreement_invoice' WHERE status = 'invoiced'")
    op.execute("UPDATE collabs SET status = 'payment_received' WHERE status = 'paid'")


def downgrade() -> None:
    op.execute("UPDATE collabs SET status = 'new_inquiry' WHERE status = 'new'")
    op.execute("UPDATE collabs SET status = 'content_live' WHERE status = 'content_posted'")
    op.execute("UPDATE collabs SET status = 'invoiced' WHERE status = 'agreement_invoice'")
    op.execute("UPDATE collabs SET status = 'paid' WHERE status = 'payment_received'")
    op.execute("UPDATE collabs SET status = 'confirmed' WHERE status IN ('script_approved', 'shoot_done', 'draft_submitted')")
