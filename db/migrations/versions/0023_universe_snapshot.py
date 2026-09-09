"""Add auditable Plan-2 universe snapshots.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund_universe_snapshot",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column(
            "evaluation_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"),
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
        sa.UniqueConstraint("decision_id", name="uq_fund_universe_snapshot_decision"),
        schema="evaluation",
    )
    op.create_table(
        "fund_universe_member",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_universe_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "share_class_id",
            sa.BigInteger,
            sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint("snapshot_id", "share_class_id", name="uq_fund_universe_member"),
        schema="evaluation",
    )
    op.create_table(
        "selection_condition_result",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "universe_member_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_universe_member.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("condition_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("passed", sa.Boolean),
        sa.UniqueConstraint(
            "universe_member_id", "condition_id", name="uq_selection_condition_member_condition"
        ),
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_table("selection_condition_result", schema="evaluation")
    op.drop_table("fund_universe_member", schema="evaluation")
    op.drop_table("fund_universe_snapshot", schema="evaluation")
