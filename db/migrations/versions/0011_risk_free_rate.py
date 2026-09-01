"""market.risk_free_rate

Revision ID: 0011
Revises: 0010
"""
from alembic import op

from fip.platform.db.mixins import QUALITY_SOURCE_SQL, TIME_ORDER_SQL

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE market.risk_free_rate (
            curve_code            VARCHAR(64)  NOT NULL,
            currency              VARCHAR(8)   NOT NULL,
            tenor                 VARCHAR(8)   NOT NULL,
            effective_at          DATE         NOT NULL,
            version               INTEGER      NOT NULL DEFAULT 1,
            rate                  NUMERIC(12,8) NOT NULL,
            raw_payload_id        BIGINT,
            available_at          TIMESTAMPTZ  NOT NULL,
            availability_quality  availability_quality_enum NOT NULL,
            published_at          TIMESTAMPTZ,
            provider_available_at TIMESTAMPTZ,
            ingested_at           TIMESTAMPTZ  NOT NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (curve_code, currency, tenor, effective_at, version),
            CONSTRAINT ck_risk_free_rate_quality_source CHECK ({QUALITY_SOURCE_SQL}),
            CONSTRAINT ck_risk_free_rate_time_order     CHECK ({TIME_ORDER_SQL})
        )
    """)
    op.execute(
        "CREATE INDEX ix_risk_free_rate_pit ON market.risk_free_rate "
        "(currency, tenor, effective_at, available_at, version DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market.risk_free_rate CASCADE")
