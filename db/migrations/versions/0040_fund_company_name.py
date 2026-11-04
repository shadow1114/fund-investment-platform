"""Add nullable current management company projection to fund.

Revision ID: 0040
Revises: 0039
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fund",
        sa.Column("company_name", sa.String(length=128), nullable=True),
        schema="fund",
    )


def downgrade() -> None:
    op.drop_column("fund", "company_name", schema="fund")
