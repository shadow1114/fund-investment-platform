"""investment_eligibility 改为三时点 + version（VersionedMixin）

Task 17 fix round 1，Important 1：docs/11-database/04-database-design.md
§6.4 与 03-erd §15.1 明确 investment_eligibility 属于「三时点 + version」
的事实型模式（PK (share_class_id, effective_at, version)），不在 §15.1
的状态型清单里（Manager Assignment / Classification History / Status
History / Benchmark Mapping / Fee / Subscription Status）。0012 误建成
了 IntervalMixin（valid_from / valid_to）表。

§6.4.1：eligibility 虽是派生值，但派生规则本身会被修订，version 记录
的正是「这条结论出自哪一版规则」——区间模型没有地方安放「同一份修订
后的结论」，只能覆盖或用第二段区间部分遮盖第一段，两者都丢失了「当时
相信的是什么」。

0012 已上线且不可编辑，本迁移是新的一步。修复前已确认 dev / test 两库
该表均为 0 行，因此这里整表 DROP + 重建而非逐列 ALTER —— 没有数据需要
迁移，且 PK 与 CHECK 约束的锚点都要变，逐列 ALTER 反而更难看清正确性。

Revision ID: 0013
Revises: 0012
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from fip.platform.db.mixins import (
    INTERVAL_SQL,
    QUALITY_SOURCE_SQL,
    TIME_ORDER_SQL,
    time_order_sql,
)

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_SCHEMA = "fund"
_TABLE = "investment_eligibility"

_QUALITY_ENUM = postgresql.ENUM(
    "EXACT", "DERIVED", "INFERRED",
    name="availability_quality_enum",
    create_type=False,
)


def _time_source_columns() -> list[sa.Column]:
    return [
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_quality", _QUALITY_ENUM, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    ]


def upgrade() -> None:
    op.drop_table(_TABLE, schema=_SCHEMA)

    op.create_table(
        _TABLE,
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("eligibility_status", sa.String(length=32), nullable=False),
        *_time_source_columns(),
        sa.CheckConstraint(QUALITY_SOURCE_SQL, name=f"ck_{_TABLE}_quality_source"),
        sa.CheckConstraint(TIME_ORDER_SQL, name=f"ck_{_TABLE}_time_order"),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("share_class_id", "effective_at", "version"),
        schema=_SCHEMA,
    )
    # PIT 版本解析的支撑索引（04-database-design §6.4：
    # (share_class_id, available_at, version DESC)）。
    op.create_index(
        "ix_investment_eligibility_pit",
        _TABLE,
        ["share_class_id", "available_at", sa.text("version DESC")],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_investment_eligibility_pit", table_name=_TABLE, schema=_SCHEMA)
    op.drop_table(_TABLE, schema=_SCHEMA)

    # 还原为 0012 引入时的 IntervalMixin 形状。
    op.create_table(
        _TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("eligibility_status", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        *_time_source_columns(),
        sa.CheckConstraint(QUALITY_SOURCE_SQL, name=f"ck_{_TABLE}_quality_source"),
        sa.CheckConstraint(
            time_order_sql("valid_from"), name=f"ck_{_TABLE}_time_order"
        ),
        sa.CheckConstraint(INTERVAL_SQL, name=f"ck_{_TABLE}_interval"),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
