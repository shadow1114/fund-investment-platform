"""Add immutable Plan-2 evaluation result storage.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund_evaluation",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column(
            "peer_group_snapshot_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "factor_run_id",
            sa.BigInteger,
            sa.ForeignKey("factor.factor_run.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "policy_version_id",
            sa.BigInteger,
            sa.ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "decision_id", "peer_group_snapshot_id", name="uq_fund_evaluation_decision_group"
        ),
        schema="evaluation",
    )
    op.create_table(
        "fund_score",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "share_class_id",
            sa.BigInteger,
            sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("value", sa.Numeric(24, 16)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64)),
        sa.UniqueConstraint(
            "evaluation_id", "share_class_id", name="uq_fund_score_evaluation_share_class"
        ),
        schema="evaluation",
    )
    op.create_table(
        "fund_score_attribution",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "fund_score_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_score.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_id", sa.String(32), nullable=False),
        sa.Column("detail", JSONB, nullable=False),
        sa.UniqueConstraint("fund_score_id", "metric_id", name="uq_fund_score_attribution_metric"),
        schema="evaluation",
    )
    op.create_table(
        "fund_ranking",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "share_class_id",
            sa.BigInteger,
            sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rank", sa.Numeric(12, 4)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.UniqueConstraint(
            "evaluation_id", "share_class_id", name="uq_fund_ranking_evaluation_share_class"
        ),
        schema="evaluation",
    )
    op.create_table(
        "fund_tier",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "share_class_id",
            sa.BigInteger,
            sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tier", sa.String(8)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.UniqueConstraint(
            "evaluation_id", "share_class_id", name="uq_fund_tier_evaluation_share_class"
        ),
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_table("fund_tier", schema="evaluation")
    op.drop_table("fund_ranking", schema="evaluation")
    op.drop_table("fund_score_attribution", schema="evaluation")
    op.drop_table("fund_score", schema="evaluation")
    op.drop_table("fund_evaluation", schema="evaluation")
