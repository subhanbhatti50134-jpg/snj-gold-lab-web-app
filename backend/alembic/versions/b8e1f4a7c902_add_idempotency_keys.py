"""Add idempotency_keys table

Revision ID: b8e1f4a7c902
Revises: f3a9c2d1e8b4
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "b8e1f4a7c902"
down_revision = "f3a9c2d1e8b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # The unique constraint is what settles concurrent duplicate requests:
    # only one of two racing inserts can win.
    op.create_index(
        op.f("ix_idempotency_keys_key"),
        "idempotency_keys",
        ["key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_idempotency_keys_user_id"),
        "idempotency_keys",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_keys_created_at"),
        "idempotency_keys",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_idempotency_keys_created_at"), table_name="idempotency_keys")
    op.drop_index(op.f("ix_idempotency_keys_user_id"), table_name="idempotency_keys")
    op.drop_index(op.f("ix_idempotency_keys_key"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
