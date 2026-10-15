"""Add layaway (bayana) orders table

Revision ID: a9d1e2f3b4c5
Revises: d4a7c2e19b35
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "a9d1e2f3b4c5"
down_revision = "d4a7c2e19b35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "layaway_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reference", sa.String(length=40), nullable=False
        ),
        sa.Column("party_id", sa.Integer(), nullable=True),
        sa.Column(
            "party_name", sa.String(length=160), nullable=False
        ),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column(
            "estimated_weight_grams",
            sa.Numeric(16, 4),
            nullable=False,
        ),
        sa.Column(
            "agreed_rate_per_gram", sa.Numeric(16, 4), nullable=False
        ),
        sa.Column(
            "estimated_total", sa.Numeric(16, 2), nullable=False
        ),
        sa.Column(
            "advance_amount",
            sa.Numeric(16, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("sale_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_by", sa.String(length=120), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["parties.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["transactions.id"],
        ),
    )
    op.create_index(
        "ix_layaway_orders_reference",
        "layaway_orders",
        ["reference"],
        unique=True,
    )
    op.create_index(
        "ix_layaway_orders_party_id",
        "layaway_orders",
        ["party_id"],
    )
    op.create_index(
        "ix_layaway_orders_status",
        "layaway_orders",
        ["status"],
    )
    op.create_index(
        "ix_layaway_orders_created_at",
        "layaway_orders",
        ["created_at"],
    )
    op.create_index(
        "ix_layaway_orders_status_due",
        "layaway_orders",
        ["status", "due_date"],
    )
    op.create_check_constraint(
        "ck_orders_terms",
        "layaway_orders",
        "estimated_weight_grams > 0 AND agreed_rate_per_gram > 0",
    )
    op.create_check_constraint(
        "ck_orders_advance",
        "layaway_orders",
        "estimated_total >= 0 AND advance_amount >= 0 "
        "AND advance_amount <= estimated_total",
    )
    op.create_check_constraint(
        "ck_orders_status",
        "layaway_orders",
        "status IN ('pending', 'delivered', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_orders_status", "layaway_orders", type_="check"
    )
    op.drop_constraint(
        "ck_orders_advance", "layaway_orders", type_="check"
    )
    op.drop_constraint(
        "ck_orders_terms", "layaway_orders", type_="check"
    )
    op.drop_index(
        "ix_layaway_orders_status_due", table_name="layaway_orders"
    )
    op.drop_index(
        "ix_layaway_orders_created_at", table_name="layaway_orders"
    )
    op.drop_index(
        "ix_layaway_orders_status", table_name="layaway_orders"
    )
    op.drop_index(
        "ix_layaway_orders_party_id", table_name="layaway_orders"
    )
    op.drop_index(
        "ix_layaway_orders_reference", table_name="layaway_orders"
    )
    op.drop_table("layaway_orders")
