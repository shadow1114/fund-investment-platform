"""Add management and custody fee rates to fund.

Revision ID: 0043
Revises: 0042
"""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fund",
        sa.Column("fund_management_fee", sa.Numeric(12, 8), nullable=True),
        schema="fund",
    )
    op.add_column(
        "fund",
        sa.Column("fund_custody_fee", sa.Numeric(12, 8), nullable=True),
        schema="fund",
    )


def downgrade() -> None:
    op.drop_column("fund", "fund_custody_fee", schema="fund")
    op.drop_column("fund", "fund_management_fee", schema="fund")
