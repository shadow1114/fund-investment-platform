"""Add per-value PIT input lineage.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "factor_value",
        sa.Column(
            "input_lineage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="factor",
    )
    op.add_column(
        "factor_value",
        sa.Column(
            "adjustment_policy_version",
            sa.String(64),
            nullable=False,
            server_default="LEGACY_UNSPECIFIED",
        ),
        schema="factor",
    )
    op.alter_column("factor_value", "input_lineage", server_default=None, schema="factor")
    op.alter_column(
        "factor_value", "adjustment_policy_version", server_default=None, schema="factor"
    )


def downgrade() -> None:
    op.drop_column("factor_value", "adjustment_policy_version", schema="factor")
    op.drop_column("factor_value", "input_lineage", schema="factor")