"""Record worker start and finish times for durable operations.

Revision ID: 0037
Revises: 0036
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calculation_job",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        schema="governance",
    )
    op.add_column(
        "calculation_job",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        schema="governance",
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM governance.calculation_job "
            "WHERE started_at IS NOT NULL OR finished_at IS NOT NULL"
        )
    ):
        raise RuntimeError("Worker timestamps exist; restore a verified backup")
    op.drop_column("calculation_job", "finished_at", schema="governance")
    op.drop_column("calculation_job", "started_at", schema="governance")
