"""Complete the Plan-2 share-class and interval contracts.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fund_share_class",
        sa.Column("base_currency", sa.String(length=8), nullable=True),
        schema="fund",
    )
    op.execute(
        "UPDATE fund.fund_share_class SET base_currency = 'CNY' "
        "WHERE base_currency IS NULL"
    )
    op.alter_column(
        "fund_share_class", "base_currency", nullable=False, schema="fund"
    )

    op.execute(
        "ALTER TABLE fund.fund_manager_assignment "
        "RENAME CONSTRAINT ex_fma_no_overlap "
        "TO ex_fma_same_manager_non_overlapping"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_fch_open_interval "
        "ON fund.fund_classification_history (fund_id, classification_scheme) "
        "WHERE valid_to IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX fund.uq_fch_open_interval")
    op.execute(
        "ALTER TABLE fund.fund_manager_assignment "
        "RENAME CONSTRAINT ex_fma_same_manager_non_overlapping "
        "TO ex_fma_no_overlap"
    )
    op.drop_column("fund_share_class", "base_currency", schema="fund")
