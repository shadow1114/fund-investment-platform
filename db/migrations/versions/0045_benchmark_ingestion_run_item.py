"""Persist per-index state for benchmark market-data ingestion jobs.

基准指数不是基金，fund_ingestion_run_item.fund_id 为 NOT NULL 外键，
因此为基准行情抓取单独建项级状态表。

Revision ID: 0045
Revises: 0044
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_ingestion_run_item",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "operation_id",
            sa.String(64),
            sa.ForeignKey("governance.calculation_job.execution_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "benchmark_index_id",
            sa.BigInteger,
            sa.ForeignKey("market.benchmark_index.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("result", JSONB),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "operation_id",
            "benchmark_index_id",
            name="uq_benchmark_ingestion_run_item_subject",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED', 'CANCELLED')",
            name="ck_benchmark_ingestion_run_item_status",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_benchmark_ingestion_run_item_operation_status",
        "benchmark_ingestion_run_item",
        ["operation_id", "status", "id"],
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_benchmark_ingestion_run_item_operation_status",
        table_name="benchmark_ingestion_run_item",
        schema="governance",
    )
    op.drop_table("benchmark_ingestion_run_item", schema="governance")
