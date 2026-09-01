"""provider_fund_identity 补齐 IntervalMixin 的时序列

Fix round 1（Task 11 code review，Important）：04-database-design §6.2 与
03-erd R-4 要求每个标记为 Temporal 的实体携带完整的时序列集合；
0007 只写了 valid_from / valid_to / created_at，漏掉了 available_at 等
五列与对应的三组 CHECK 约束。没有 available_at，「某个时点我们知道的
Provider 映射是哪一条」这个问题在本表里无法回答 —— 会静默退化成读
当前映射（前视偏差），而本表存在的唯一理由就是 Provider 可能重新
分配同一个 (provider_id, provider_fund_id) 指向不同的 Share Class
（§6.2.1）。

0007 已上线且不可编辑，因此这里用 ALTER TABLE 补列/补约束，不重建表。

补列前已确认 dev / test 两个库该表均为空（0 行），因此五个新列可以
直接以 NOT NULL 加入，无需「先允许 NULL、回填、再收紧」的两步走。

同时把唯一约束改名为文档要求的 uq_pfi_provider_key（原名
uq_provider_identity），并新增 idx_pfi_share_class 索引 —— 均与
04-database-design §6.2 对齐，ORM 侧同步更新，避免 autogenerate
把 ORM 与 DDL 的差异当成新的迁移操作。

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

from fip.platform.db.mixins import (
    INTERVAL_SQL,
    QUALITY_SOURCE_SQL,
    availability_quality_enum,
    time_order_sql,
)

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_TABLE = "provider_fund_identity"
_SCHEMA = "fund"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("availability_quality", availability_quality_enum, nullable=False),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} "
        "RENAME CONSTRAINT uq_provider_identity TO uq_pfi_provider_key"
    )

    op.create_check_constraint(
        "ck_provider_fund_identity_quality_source",
        _TABLE,
        QUALITY_SOURCE_SQL,
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "ck_provider_fund_identity_time_order",
        _TABLE,
        time_order_sql("valid_from"),
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "ck_provider_fund_identity_interval",
        _TABLE,
        INTERVAL_SQL,
        schema=_SCHEMA,
    )

    op.create_index(
        "idx_pfi_share_class", _TABLE, ["share_class_id"], schema=_SCHEMA
    )


def downgrade() -> None:
    op.drop_index("idx_pfi_share_class", table_name=_TABLE, schema=_SCHEMA)

    op.drop_constraint(
        "ck_provider_fund_identity_interval", _TABLE, schema=_SCHEMA, type_="check"
    )
    op.drop_constraint(
        "ck_provider_fund_identity_time_order", _TABLE, schema=_SCHEMA, type_="check"
    )
    op.drop_constraint(
        "ck_provider_fund_identity_quality_source", _TABLE, schema=_SCHEMA, type_="check"
    )

    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} "
        "RENAME CONSTRAINT uq_pfi_provider_key TO uq_provider_identity"
    )

    op.drop_column(_TABLE, "ingested_at", schema=_SCHEMA)
    op.drop_column(_TABLE, "provider_available_at", schema=_SCHEMA)
    op.drop_column(_TABLE, "published_at", schema=_SCHEMA)
    op.drop_column(_TABLE, "availability_quality", schema=_SCHEMA)
    op.drop_column(_TABLE, "available_at", schema=_SCHEMA)
