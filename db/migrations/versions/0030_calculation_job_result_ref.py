"""Persist operation result references for API polling."""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calculation_job",
        sa.Column("result_ref", sa.String(255), nullable=True),
        schema="governance",
    )


def downgrade() -> None:
    op.drop_column("calculation_job", "result_ref", schema="governance")
