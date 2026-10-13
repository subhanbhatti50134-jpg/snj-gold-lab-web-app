"""Add transaction_date column

Revision ID: c7e8f9a0b1c2
Revises: 3d913738a277
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "c7e8f9a0b1c2"
down_revision = "3d913738a277"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("transaction_date", sa.Date(), nullable=True),
    )
    # Backfill from the row-creation timestamp so existing history keeps
    # sensible business dates.
    op.execute(
        "UPDATE transactions "
        "SET transaction_date = (created_at AT TIME ZONE 'UTC')::date"
    )
    op.alter_column(
        "transactions",
        "transaction_date",
        nullable=False,
        server_default=sa.text("'2026-01-01'::date"),
    )
    op.create_index(
        op.f("ix_transactions_transaction_date"),
        "transactions",
        ["transaction_date"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transactions_transaction_date"),
        table_name="transactions",
    )
    op.drop_column("transactions", "transaction_date")
