"""Add Stage 9 Live Portfolio and Stage 10 Rebalancing tables.

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_portfolio",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "portfolio_id", sa.String(64), sa.ForeignKey("portfolio.portfolio.id"), nullable=False
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("cash_balance", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("total_equity", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("has_pending_execution", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_rebalanced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        schema="portfolio",
    )
    op.create_index(
        "ix_live_portfolio_portfolio_id",
        "live_portfolio",
        ["portfolio_id"],
        schema="portfolio",
    )

    op.create_table(
        "portfolio_position",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "live_portfolio_id",
            sa.String(64),
            sa.ForeignKey("portfolio.live_portfolio.id"),
            nullable=False,
        ),
        sa.Column("fund_id", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),  # ACTUAL, TARGET, PENDING
        sa.Column("shares", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("cost_basis", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("market_price", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("market_value", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("holding_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        schema="portfolio",
    )
    op.create_index(
        "ix_portfolio_position_live_state",
        "portfolio_position",
        ["live_portfolio_id", "state", "fund_id"],
        schema="portfolio",
    )

    op.create_table(
        "execution_report",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "live_portfolio_id",
            sa.String(64),
            sa.ForeignKey("portfolio.live_portfolio.id"),
            nullable=False,
        ),
        sa.Column("rebalance_id", sa.String(64), nullable=True),
        sa.Column("fund_id", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("requested_shares", sa.Numeric(20, 4), nullable=False),
        sa.Column("filled_shares", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("filled_price", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("fee", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "reported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        schema="portfolio",
    )
    op.create_index(
        "ix_execution_report_live_status",
        "execution_report",
        ["live_portfolio_id", "status"],
        schema="portfolio",
    )

    op.create_table(
        "rebalance_event",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "live_portfolio_id",
            sa.String(64),
            sa.ForeignKey("portfolio.live_portfolio.id"),
            nullable=False,
        ),
        sa.Column("decision_at", sa.Date(), nullable=False),
        sa.Column("trigger_types", JSONB, nullable=False),
        sa.Column("primary_trigger", sa.String(32), nullable=False),
        sa.Column("trigger_reasons", JSONB, nullable=False),
        sa.Column("recompute_scope", sa.String(32), nullable=False),
        sa.Column("decision_outcome", sa.String(32), nullable=False),
        sa.Column("turnover", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_improvement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("details", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        schema="portfolio",
    )
    op.create_index(
        "ix_rebalance_event_live_date",
        "rebalance_event",
        ["live_portfolio_id", "decision_at"],
        schema="portfolio",
    )

    op.create_table(
        "rebalance_trade",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "rebalance_id",
            sa.String(64),
            sa.ForeignKey("portfolio.rebalance_event.id"),
            nullable=False,
        ),
        sa.Column("fund_id", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("current_weight", sa.Float(), nullable=False),
        sa.Column("weight_delta", sa.Float(), nullable=False),
        sa.Column("target_shares", sa.Float(), nullable=False),
        sa.Column("delta_shares", sa.Float(), nullable=False),
        sa.Column("estimated_amount", sa.Float(), nullable=False),
        sa.Column("eligibility_status", sa.String(32), nullable=False),
        sa.Column("is_filtered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("unachieved_reason", sa.String(255), nullable=True),
        schema="portfolio",
    )
    op.create_index(
        "ix_rebalance_trade_rebalance_id",
        "rebalance_trade",
        ["rebalance_id"],
        schema="portfolio",
    )

    op.create_table(
        "rebalance_policy",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("policy_version", sa.String(64), unique=True, nullable=False),
        sa.Column("weight_drift_threshold", sa.Float(), nullable=False, server_default="0.03"),
        sa.Column("category_drift_threshold", sa.Float(), nullable=False, server_default="0.05"),
        sa.Column("min_trade_threshold", sa.Float(), nullable=False, server_default="0.005"),
        sa.Column("turnover_threshold", sa.Float(), nullable=False, server_default="0.30"),
        sa.Column("cost_benefit_multiplier", sa.Float(), nullable=False, server_default="1.5"),
        sa.Column("pending_timeout_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_table("rebalance_policy", schema="portfolio")
    op.drop_table("rebalance_trade", schema="portfolio")
    op.drop_table("rebalance_event", schema="portfolio")
    op.drop_table("execution_report", schema="portfolio")
    op.drop_table("portfolio_position", schema="portfolio")
    op.drop_table("live_portfolio", schema="portfolio")
