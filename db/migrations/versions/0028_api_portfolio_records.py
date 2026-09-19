"""Persist API portfolio, optimization, and decision read records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("portfolio_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("portfolio_version", sa.String(64), nullable=False),
        sa.Column("risk_profile", sa.String(64), nullable=False),
        sa.Column("benchmark", JSONB, nullable=False),
        sa.Column("portfolio_rule_version", sa.String(64), nullable=False),
        sa.Column("owner_user_id", sa.String(128), nullable=False),
        sa.Column("viewer_user_ids", JSONB, nullable=False),
        schema="portfolio",
    )
    op.create_table(
        "optimization",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "portfolio_id", sa.String(64), sa.ForeignKey("portfolio.portfolio.id"), nullable=False
        ),
        sa.Column("payload", JSONB, nullable=False),
        schema="portfolio",
    )
    op.create_table(
        "decision",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "portfolio_id", sa.String(64), sa.ForeignKey("portfolio.portfolio.id"), nullable=False
        ),
        sa.Column("optimization_id", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_table("decision", schema="portfolio")
    op.drop_table("optimization", schema="portfolio")
    op.drop_table("portfolio", schema="portfolio")
