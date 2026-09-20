"""Add durable worker lease columns to calculation jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("calculation_job", sa.Column("claimed_by", sa.String(128), nullable=True), schema="governance")
    op.add_column(
        "calculation_job",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="governance",
    )
    op.add_column(
        "calculation_job",
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        schema="governance",
    )
    op.create_index(
        "ix_calculation_job_claimable",
        "calculation_job",
        ["status", "lease_expires_at", "created_at"],
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index("ix_calculation_job_claimable", table_name="calculation_job", schema="governance")
    op.drop_column("calculation_job", "last_error_at", schema="governance")
    op.drop_column("calculation_job", "lease_expires_at", schema="governance")
    op.drop_column("calculation_job", "claimed_by", schema="governance")
