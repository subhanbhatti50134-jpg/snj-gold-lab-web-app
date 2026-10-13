"""Add DB check constraints and report indexes

Revision ID: f3a9c2d1e8b4
Revises: c7e8f9a0b1c2
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "f3a9c2d1e8b4"
down_revision = "c7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- transactions -------------------------------------------------
    op.create_check_constraint(
        "ck_transactions_weights",
        "transactions",
        "quantity_grams > 0 AND gross_weight_grams > 0 "
        "AND net_weight_grams > 0 AND deduction_grams >= 0",
    )
    op.create_check_constraint(
        "ck_transactions_purity",
        "transactions",
        "purity >= 0 AND purity <= 100",
    )
    op.create_check_constraint(
        "ck_transactions_amounts",
        "transactions",
        "rate_per_gram >= 0 AND charges >= 0 "
        "AND total_amount >= 0 AND amount_paid >= 0 "
        "AND amount_paid <= total_amount",
    )

    # --- payments -----------------------------------------------------
    # Positive = money received, negative = refund on cancel. Zero is
    # never a meaningful ledger entry.
    op.create_check_constraint(
        "ck_payments_amount_nonzero",
        "payments",
        "amount <> 0",
    )

    # --- metal rates --------------------------------------------------
    op.create_check_constraint(
        "ck_metal_rates_purity",
        "metal_rates",
        "purity >= 0 AND purity <= 100",
    )
    op.create_check_constraint(
        "ck_metal_rates_rate",
        "metal_rates",
        "rate_per_gram > 0 AND entered_rate >= 0",
    )

    # --- products -----------------------------------------------------
    op.create_check_constraint(
        "ck_products_purity",
        "products",
        "purity >= 0 AND purity <= 100",
    )

    # --- stock movements ----------------------------------------------
    op.create_check_constraint(
        "ck_stock_movements_delta_nonzero",
        "stock_movements",
        "quantity_delta_grams <> 0",
    )

    # --- report indexes ------------------------------------------------
    # Reports filter on kind + status + transaction_date together.
    op.create_index(
        "ix_transactions_kind_status_date",
        "transactions",
        ["kind", "status", "transaction_date"],
    )
    # Party ledger filters on party_id + date range.
    op.create_index(
        "ix_transactions_party_date",
        "transactions",
        ["party_id", "transaction_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transactions_party_date", table_name="transactions"
    )
    op.drop_index(
        "ix_transactions_kind_status_date", table_name="transactions"
    )
    op.drop_constraint(
        "ck_stock_movements_delta_nonzero",
        "stock_movements",
        type_="check",
    )
    op.drop_constraint(
        "ck_products_purity", "products", type_="check"
    )
    op.drop_constraint(
        "ck_metal_rates_rate", "metal_rates", type_="check"
    )
    op.drop_constraint(
        "ck_metal_rates_purity", "metal_rates", type_="check"
    )
    op.drop_constraint(
        "ck_payments_amount_nonzero", "payments", type_="check"
    )
    op.drop_constraint(
        "ck_transactions_amounts", "transactions", type_="check"
    )
    op.drop_constraint(
        "ck_transactions_purity", "transactions", type_="check"
    )
    op.drop_constraint(
        "ck_transactions_weights", "transactions", type_="check"
    )
