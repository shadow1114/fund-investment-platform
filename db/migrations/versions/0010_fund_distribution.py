"""market.fund_distribution

Revision ID: 0010
Revises: 0009
"""
from alembic import op

from fip.platform.db.mixins import QUALITY_SOURCE_SQL, TIME_ORDER_SQL

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE market.fund_distribution (
            share_class_id        BIGINT       NOT NULL
                REFERENCES fund.fund_share_class(id) ON DELETE RESTRICT,
            effective_at          DATE         NOT NULL,
            version               INTEGER      NOT NULL DEFAULT 1,
            dividend_per_unit     NUMERIC(18,8) NOT NULL DEFAULT 0,
            split_ratio           NUMERIC(18,8) NOT NULL DEFAULT 1,
            raw_payload_id        BIGINT,
            available_at          TIMESTAMPTZ  NOT NULL,
            availability_quality  availability_quality_enum NOT NULL,
            published_at          TIMESTAMPTZ,
            provider_available_at TIMESTAMPTZ,
            ingested_at           TIMESTAMPTZ  NOT NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (share_class_id, effective_at, version),
            CONSTRAINT ck_fund_distribution_quality_source CHECK ({QUALITY_SOURCE_SQL}),
            CONSTRAINT ck_fund_distribution_time_order     CHECK ({TIME_ORDER_SQL}),
            CONSTRAINT ck_fund_distribution_dividend CHECK (dividend_per_unit >= 0),
            CONSTRAINT ck_fund_distribution_split    CHECK (split_ratio > 0)
        )
    """)
    op.execute(
        "CREATE INDEX ix_fund_distribution_pit ON market.fund_distribution "
        "(share_class_id, effective_at, available_at, version DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market.fund_distribution CASCADE")
