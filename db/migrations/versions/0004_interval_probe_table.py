"""interval 探针表：验证 IntervalMixin 的三组约束（quality/source、
anchor=valid_from 的 time_order、interval）

修复：Task 3 fix round 2, item 2 —— IntervalMixin / interval_check /
INTERVAL_SQL 此前完全没有测试覆盖，也没有任何迁移曾以 anchor="valid_from"
实例化 time_order 约束。这正是 fix round 2 item 1 那个 Critical
（TIME_ORDER_SQL 硬编码 effective_at，无法套用到 IntervalMixin 表）
一直未被发现的原因。

governance.interval_probe 与 governance.mixin_probe 平行：把 VersionedMixin
的 effective_at + version 换成 IntervalMixin 的 valid_from + valid_to，
time_order 约束改用 anchor="valid_from"，并额外带上 interval_check。

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

from fip.platform.db.mixins import (
    INTERVAL_SQL,
    QUALITY_SOURCE_SQL,
    availability_quality_enum,
    time_order_sql,
)

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interval_probe",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "availability_quality",
            availability_quality_enum,
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(QUALITY_SOURCE_SQL, name="ck_interval_probe_quality_source"),
        sa.CheckConstraint(
            time_order_sql("valid_from"), name="ck_interval_probe_time_order"
        ),
        sa.CheckConstraint(INTERVAL_SQL, name="ck_interval_probe_interval"),
        schema="governance",
    )


def downgrade() -> None:
    op.drop_table("interval_probe", schema="governance")
