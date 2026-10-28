"""Use one classification scheme while retaining historical result payloads.

Revision ID: 0038
Revises: 0037
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE fund.fund_classification_revision "
        "SET scheme = 'FIP_CLASSIFICATION' "
        "WHERE scheme = 'FIP_CLASSIFICATION_V1'"
    )
    op.execute(
        "UPDATE fund.fund_classification_history "
        "SET classification_scheme = 'FIP_CLASSIFICATION' "
        "WHERE classification_scheme = 'FIP_CLASSIFICATION_V1'"
    )
    op.drop_column("fund_classification_revision", "rule_version", schema="fund")
    op.drop_column("fund_classification_revision", "enum_version", schema="fund")


def downgrade() -> None:
    op.add_column(
        "fund_classification_revision",
        sa.Column("enum_version", sa.String(32), nullable=False, server_default="CURRENT"),
        schema="fund",
    )
    op.add_column(
        "fund_classification_revision",
        sa.Column("rule_version", sa.String(32), nullable=False, server_default="CURRENT"),
        schema="fund",
    )
    op.execute(
        "UPDATE fund.fund_classification_history "
        "SET classification_scheme = 'FIP_CLASSIFICATION_V1' "
        "WHERE classification_scheme = 'FIP_CLASSIFICATION'"
    )
    op.execute(
        "UPDATE fund.fund_classification_revision "
        "SET scheme = 'FIP_CLASSIFICATION_V1' "
        "WHERE scheme = 'FIP_CLASSIFICATION'"
    )
