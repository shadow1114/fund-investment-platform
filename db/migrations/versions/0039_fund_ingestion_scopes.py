"""Persist ingestion previews and per-subject execution state.

Revision ID: 0039
Revises: 0038
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund_ingestion_preview",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("dataset", sa.String(32), nullable=False),
        sa.Column("scope", JSONB, nullable=False),
        sa.Column("members", JSONB, nullable=False),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="governance",
    )
    op.create_table(
        "fund_ingestion_run_item",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "operation_id",
            sa.String(64),
            sa.ForeignKey("governance.calculation_job.execution_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fund_id", sa.BigInteger, sa.ForeignKey("fund.fund.id"), nullable=False),
        sa.Column("public_fund_id", sa.String(32), nullable=False),
        sa.Column("share_class_id", sa.BigInteger, sa.ForeignKey("fund.fund_share_class.id")),
        sa.Column("symbol", sa.String(128)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("result", JSONB),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "operation_id",
            "fund_id",
            "share_class_id",
            name="uq_fund_ingestion_run_item_subject",
            postgresql_nulls_not_distinct=True,
        ),
        schema="governance",
    )
    op.create_index(
        "ix_fund_ingestion_run_item_operation_status",
        "fund_ingestion_run_item",
        ["operation_id", "status", "id"],
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fund_ingestion_run_item_operation_status",
        table_name="fund_ingestion_run_item",
        schema="governance",
    )
    op.drop_table("fund_ingestion_run_item", schema="governance")
    op.drop_table("fund_ingestion_preview", schema="governance")
