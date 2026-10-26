"""Store requests and results for durable fund data ingestion jobs.

Revision ID: 0035
Revises: 0034
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calculation_job",
        sa.Column("job_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="governance",
    )
    op.add_column(
        "calculation_job",
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="governance",
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM governance.calculation_job "
            "WHERE job_type IN ('fund_basic_info_ingest', 'fund_nav_ingest') "
            "AND (job_payload IS NOT NULL OR result_payload IS NOT NULL)"
        )
    ):
        raise RuntimeError(
            "Fund ingestion jobs contain request or result data; restore a verified backup"
        )
    op.drop_column("calculation_job", "result_payload", schema="governance")
    op.drop_column("calculation_job", "job_payload", schema="governance")
