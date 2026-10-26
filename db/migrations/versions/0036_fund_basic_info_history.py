"""Keep immutable versioned snapshots of provider fund overview data.

Revision ID: 0036
Revises: 0035
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund_basic_info_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_payload_id", sa.BigInteger(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_quality", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version > 0", name="ck_fbih_positive_version"),
        sa.CheckConstraint(
            "availability_quality = 'INFERRED'",
            name="ck_fbih_overview_availability_quality",
        ),
        sa.ForeignKeyConstraint(["fund_id"], ["fund.fund.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raw_payload_id"], ["raw.raw_payload.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_id", "version", name="uq_fbih_fund_version"),
        schema="fund",
    )
    op.create_index(
        "ix_fbih_pit",
        "fund_basic_info_history",
        ["fund_id", "available_at", "version"],
        schema="fund",
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM fund.fund_basic_info_history")):
        raise RuntimeError(
            "Fund basic information history contains data; restore a verified backup"
        )
    op.drop_index("ix_fbih_pit", table_name="fund_basic_info_history", schema="fund")
    op.drop_table("fund_basic_info_history", schema="fund")
