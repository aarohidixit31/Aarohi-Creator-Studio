"""add oauth connections

Revision ID: f7a1c4d8e902
Revises: c21e7a914d04
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a1c4d8e902"
down_revision: Union[str, Sequence[str], None] = "c21e7a914d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("provider_account_id", sa.String(), nullable=True),
        sa.Column("account_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_connections_id"), "oauth_connections", ["id"], unique=False)
    op.create_index(op.f("ix_oauth_connections_provider"), "oauth_connections", ["provider"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_oauth_connections_provider"), table_name="oauth_connections")
    op.drop_index(op.f("ix_oauth_connections_id"), table_name="oauth_connections")
    op.drop_table("oauth_connections")
