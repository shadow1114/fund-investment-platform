"""Add Plan-2 benchmark contracts and immutable policy versions.

Revision ID: 0019
Revises: 0018
"""
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def _times() -> list[sa.Column]:
    return [
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "availability_quality",
            ENUM(
                "EXACT", "DERIVED", "INFERRED",
                name="availability_quality_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("provider_available_at", sa.DateTime(timezone=True)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table("benchmark_definition", sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("benchmark_code", sa.String(64), nullable=False, unique=True), sa.Column("display_name", sa.String(128), nullable=False), schema="market")
    op.create_table("benchmark_index", sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("provider_code", sa.String(64), nullable=False), sa.Column("provider_symbol", sa.String(128), nullable=False), sa.Column("display_name", sa.String(128), nullable=False), sa.Column("currency", sa.String(8), nullable=False), sa.Column("index_type", sa.String(32), nullable=False), sa.CheckConstraint("index_type IN ('PRICE', 'TOTAL_RETURN', 'FULL_PRICE')", name="ck_benchmark_index_type"), sa.UniqueConstraint("provider_code", "provider_symbol", "index_type", name="uq_benchmark_index_provider_symbol_type"), schema="market")
    op.create_table("benchmark_component", sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("benchmark_id", sa.BigInteger, sa.ForeignKey("market.benchmark_definition.id", ondelete="RESTRICT"), nullable=False), sa.Column("index_id", sa.BigInteger, sa.ForeignKey("market.benchmark_index.id", ondelete="RESTRICT"), nullable=False), sa.Column("weight", sa.Numeric(12, 8), nullable=False), sa.CheckConstraint("weight > 0 AND weight <= 1", name="ck_benchmark_component_weight"), sa.UniqueConstraint("benchmark_id", "index_id", name="uq_benchmark_component_index"), schema="market")
    op.create_table("benchmark_mapping", sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("benchmark_id", sa.BigInteger, sa.ForeignKey("market.benchmark_definition.id", ondelete="RESTRICT"), nullable=False), sa.Column("share_class_id", sa.BigInteger, sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT")), sa.Column("classification_code", sa.String(32)), sa.Column("mapping_source", sa.String(32), nullable=False), sa.Column("mapping_version", sa.String(32), nullable=False), sa.Column("valid_from", sa.Date, nullable=False), sa.Column("valid_to", sa.Date), *_times(), sa.CheckConstraint("valid_to IS NULL OR valid_from < valid_to", name="ck_benchmark_mapping_interval"), sa.CheckConstraint("(share_class_id IS NOT NULL) <> (classification_code IS NOT NULL)", name="ck_benchmark_mapping_scope"), sa.CheckConstraint("(availability_quality = 'EXACT' AND provider_available_at IS NOT NULL) OR (availability_quality = 'DERIVED' AND provider_available_at IS NULL AND published_at IS NOT NULL) OR (availability_quality = 'INFERRED' AND provider_available_at IS NULL AND published_at IS NULL)", name="ck_benchmark_mapping_quality_source"), sa.CheckConstraint("(provider_available_at IS NULL OR published_at IS NULL OR provider_available_at >= published_at) AND (ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND (available_at >= COALESCE(provider_available_at, published_at))", name="ck_benchmark_mapping_time_order"), schema="market")
    op.create_table("benchmark_index_value", sa.Column("index_id", sa.BigInteger, sa.ForeignKey("market.benchmark_index.id", ondelete="RESTRICT"), primary_key=True), sa.Column("effective_at", sa.Date, primary_key=True), sa.Column("version", sa.Integer, primary_key=True), sa.Column("value", sa.Numeric(18, 8), nullable=False), *_times(), sa.CheckConstraint("value > 0", name="ck_benchmark_index_value_positive"), sa.CheckConstraint("(availability_quality = 'EXACT' AND provider_available_at IS NOT NULL) OR (availability_quality = 'DERIVED' AND provider_available_at IS NULL AND published_at IS NOT NULL) OR (availability_quality = 'INFERRED' AND provider_available_at IS NULL AND published_at IS NULL)", name="ck_benchmark_index_value_quality_source"), sa.CheckConstraint("(published_at IS NULL OR published_at >= (effective_at::timestamp AT TIME ZONE 'UTC')) AND (provider_available_at IS NULL OR published_at IS NULL OR provider_available_at >= published_at) AND (ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND (available_at >= (effective_at::timestamp AT TIME ZONE 'UTC')) AND (available_at >= COALESCE(provider_available_at, published_at))", name="ck_benchmark_index_value_time_order"), schema="market")
    op.create_index("ix_benchmark_mapping_fund_pit", "benchmark_mapping", ["share_class_id", "valid_from", "available_at"], schema="market")
    op.create_index("ix_benchmark_mapping_class_pit", "benchmark_mapping", ["classification_code", "valid_from", "available_at"], schema="market")
    op.create_index("ix_benchmark_index_value_pit", "benchmark_index_value", ["index_id", "effective_at", "available_at", sa.text("version DESC")], schema="market")
    op.create_unique_constraint("uq_policy_version_kind_label", "policy_version", ["policy_kind", "version_label"], schema="governance")


def downgrade() -> None:
    op.drop_constraint("uq_policy_version_kind_label", "policy_version", schema="governance", type_="unique")
    op.drop_table("benchmark_index_value", schema="market")
    op.drop_table("benchmark_mapping", schema="market")
    op.drop_table("benchmark_component", schema="market")
    op.drop_table("benchmark_index", schema="market")
    op.drop_table("benchmark_definition", schema="market")
