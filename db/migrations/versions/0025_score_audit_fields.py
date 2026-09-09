"""Add mandatory score completeness and weight-source audit fields.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fund_score",
        sa.Column(
            "data_completeness",
            sa.Numeric(12, 8),
            nullable=False,
            server_default="0",
        ),
        schema="evaluation",
    )
    op.add_column(
        "fund_score",
        sa.Column(
            "weight_source",
            sa.String(32),
            nullable=False,
            server_default="PROFILE_FIXED_V1",
        ),
        schema="evaluation",
    )
    op.create_check_constraint(
        "ck_fund_score_data_completeness",
        "fund_score",
        "data_completeness >= 0 AND data_completeness <= 1",
        schema="evaluation",
    )
    op.alter_column("fund_score", "data_completeness", server_default=None, schema="evaluation")
    op.alter_column("fund_score", "weight_source", server_default=None, schema="evaluation")


def downgrade() -> None:
    op.drop_constraint(
        "ck_fund_score_data_completeness",
        "fund_score",
        schema="evaluation",
        type_="check",
    )
    op.drop_column("fund_score", "weight_source", schema="evaluation")
    op.drop_column("fund_score", "data_completeness", schema="evaluation")