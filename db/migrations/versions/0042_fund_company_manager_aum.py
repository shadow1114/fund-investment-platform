"""Rename fund.company_name to fund_company; add fund_manager, asset_type, fund_aum.

Revision ID: 0042
Revises: 0041
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("fund", "company_name", new_column_name="fund_company", schema="fund")
    op.add_column(
        "fund",
        sa.Column("fund_manager", sa.String(length=256), nullable=True),
        schema="fund",
    )
    op.add_column(
        "fund",
        sa.Column("asset_type", sa.String(length=32), nullable=True),
        schema="fund",
    )
    op.add_column(
        "fund",
        sa.Column("fund_aum", sa.Numeric(24, 2), nullable=True),
        schema="fund",
    )


def downgrade() -> None:
    op.drop_column("fund", "fund_aum", schema="fund")
    op.drop_column("fund", "asset_type", schema="fund")
    op.drop_column("fund", "fund_manager", schema="fund")
    op.alter_column("fund", "fund_company", new_column_name="company_name", schema="fund")
