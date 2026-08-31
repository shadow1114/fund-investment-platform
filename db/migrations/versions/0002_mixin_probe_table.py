"""mixin 探针表：验证版本化标准列的两组 CHECK 约束

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

from fip.platform.db.mixins import (
    QUALITY_SOURCE_SQL,
    TIME_ORDER_SQL,
    availability_quality_enum,
)

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# 复用 mixins.py 中的 postgresql.ENUM（create_type=False 才会真正生效）——
# 通用的 sa.Enum(..., create_type=False) 不认得 create_type 这个方言专属参数，
# 会被静默忽略，导致 CREATE TYPE 重复执行并在 0001 已建的类型上报错。


def upgrade() -> None:
    op.create_table(
        "mixin_probe",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("effective_at", sa.Date, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "availability_quality",
            availability_quality_enum,
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(QUALITY_SOURCE_SQL, name="ck_mixin_probe_quality_source"),
        sa.CheckConstraint(TIME_ORDER_SQL, name="ck_mixin_probe_time_order"),
        schema="governance",
    )


def downgrade() -> None:
    op.drop_table("mixin_probe", schema="governance")
