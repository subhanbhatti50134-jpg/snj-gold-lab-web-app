"""Add making charge columns to transactions

Revision ID: d4a7c2e19b35
Revises: f3a9c2d1e8b4
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "d4a7c2e19b35"
down_revision = "b8e1f4a7c902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "making_charge_type",
            sa.String(length=10),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "making_charge_value",
            sa.Numeric(16, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "making_amount",
            sa.Numeric(16, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_transactions_making",
        "transactions",
        "making_charge_value >= 0 AND making_amount >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_transactions_making", "transactions", type_="check"
    )
    op.drop_column("transactions", "making_amount")
    op.drop_column("transactions", "making_charge_value")
    op.drop_column("transactions", "making_charge_type")
