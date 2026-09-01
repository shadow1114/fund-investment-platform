"""market.fund_nav 分区表

Revision ID: 0008
Revises: 0007
"""
from alembic import op

from fip.platform.db.mixins import QUALITY_SOURCE_SQL

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# 【已冻结的字面量】迁移是不可编辑的历史，它产出的 DDL 必须与当初执行时
# 逐字相同。此前这里 import 的是 mixins.py 里的共享常量/生成器，于是
# fix round 2 修改 mixins 时，这支【旧】迁移在一次全新的 upgrade 里会产出
# 【新】定义 —— 迁移历史被追溯性地改写，downgrade 也再无法还原当初的形状。
# 因此把当时的 SQL 原样固化在这里；今后的语义变更一律由新迁移承担。
_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= effective_at) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= effective_at)"
)

FIRST_YEAR, LAST_YEAR = 2000, 2030


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE market.fund_nav (
            share_class_id        BIGINT       NOT NULL
                REFERENCES fund.fund_share_class(id) ON DELETE RESTRICT,
            effective_at          DATE         NOT NULL,
            version               INTEGER      NOT NULL DEFAULT 1,
            unit_nav              NUMERIC(18,8) NOT NULL,
            adjusted_nav          NUMERIC(18,8),
            raw_payload_id        BIGINT,
            available_at          TIMESTAMPTZ  NOT NULL,
            availability_quality  availability_quality_enum NOT NULL,
            published_at          TIMESTAMPTZ,
            provider_available_at TIMESTAMPTZ,
            ingested_at           TIMESTAMPTZ  NOT NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (share_class_id, effective_at, version),
            CONSTRAINT ck_fund_nav_quality_source CHECK ({QUALITY_SOURCE_SQL}),
            CONSTRAINT ck_fund_nav_time_order     CHECK ({_TIME_ORDER_SQL}),
            CONSTRAINT ck_fund_nav_positive       CHECK (unit_nav > 0)
        ) PARTITION BY RANGE (effective_at)
    """)
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        op.execute(
            f"CREATE TABLE market.fund_nav_{year} PARTITION OF market.fund_nav "
            f"FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01')"
        )
    # PIT 版本解析的支撑索引：按 available_at 过滤后取每个 effective_at 的最大 version
    op.execute(
        "CREATE INDEX ix_fund_nav_pit ON market.fund_nav "
        "(share_class_id, effective_at, available_at, version DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market.fund_nav CASCADE")
