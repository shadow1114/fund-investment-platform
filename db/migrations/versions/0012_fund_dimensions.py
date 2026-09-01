"""fund 维度与历史表、Investment Eligibility

Investment Eligibility 是客观事实（基金能不能被交易），归 data-service；
Eligibility Rules 是策略规则（本策略要什么样的基金），归 fund-service。
两者名称相近但性质不同，前者是后者的输入之一，不是同义词
（01-system-architecture §6.5）。

新增 5 张区间型表（fund_manager_assignment / fund_classification_history /
fund_status_history / fund_fee / investment_eligibility）均携带
IntervalMixin 的完整时序列集合，anchor 显式传 "valid_from" ——
这些表没有 effective_at，缺省 anchor 会在迁移期报
UndefinedColumn: effective_at。

Revision ID: 0012
Revises: 0011
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from fip.platform.db.mixins import INTERVAL_SQL, QUALITY_SOURCE_SQL, time_order_sql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_SCHEMA = "fund"

_quality_source = QUALITY_SOURCE_SQL
_time_order_valid_from = time_order_sql("valid_from")


def _temporal_columns() -> list[sa.Column]:
    """IntervalMixin 的完整时序列集合（04-database-design §4.4.1）。"""
    return [
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "availability_quality",
            postgresql.ENUM(
                "EXACT", "DERIVED", "INFERRED",
                name="availability_quality_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    ]


def _temporal_check_constraints(table: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(_quality_source, name=f"ck_{table}_quality_source"),
        sa.CheckConstraint(_time_order_valid_from, name=f"ck_{table}_time_order"),
        sa.CheckConstraint(INTERVAL_SQL, name=f"ck_{table}_interval"),
    ]


def upgrade() -> None:
    op.create_table(
        "fund_management_company",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_code", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_code"),
        schema=_SCHEMA,
    )

    op.create_table(
        "fund_manager",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("manager_code", sa.String(length=32), nullable=False),
        sa.Column("manager_name", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manager_code"),
        schema=_SCHEMA,
    )

    op.create_table(
        "fund_manager_assignment",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_id", sa.BigInteger(), nullable=False),
        sa.Column("manager_id", sa.BigInteger(), nullable=False),
        *_temporal_columns(),
        *_temporal_check_constraints("fund_manager_assignment"),
        sa.ForeignKeyConstraint(["fund_id"], ["fund.fund.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["manager_id"], ["fund.fund_manager.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )

    op.create_table(
        "fund_classification_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_id", sa.BigInteger(), nullable=False),
        sa.Column("classification_scheme", sa.String(length=32), nullable=False),
        sa.Column("classification_code", sa.String(length=32), nullable=False),
        *_temporal_columns(),
        *_temporal_check_constraints("fund_classification_history"),
        sa.ForeignKeyConstraint(["fund_id"], ["fund.fund.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )

    op.create_table(
        "fund_status_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("subscription_open", sa.Boolean(), nullable=False),
        sa.Column("redemption_open", sa.Boolean(), nullable=False),
        *_temporal_columns(),
        *_temporal_check_constraints("fund_status_history"),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )

    op.create_table(
        "fund_fee",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("fee_type", sa.String(length=32), nullable=False),
        sa.Column("rate", sa.Numeric(precision=12, scale=8), nullable=False),
        *_temporal_columns(),
        *_temporal_check_constraints("fund_fee"),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )

    op.create_table(
        "investment_eligibility",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("eligibility_status", sa.String(length=32), nullable=False),
        *_temporal_columns(),
        *_temporal_check_constraints("investment_eligibility"),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("investment_eligibility", schema=_SCHEMA)
    op.drop_table("fund_fee", schema=_SCHEMA)
    op.drop_table("fund_status_history", schema=_SCHEMA)
    op.drop_table("fund_classification_history", schema=_SCHEMA)
    op.drop_table("fund_manager_assignment", schema=_SCHEMA)
    op.drop_table("fund_manager", schema=_SCHEMA)
    op.drop_table("fund_management_company", schema=_SCHEMA)
