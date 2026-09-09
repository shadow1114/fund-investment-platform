"""Scope universe snapshots by decision and peer-group evaluation.

Revision ID: 0024
Revises: 0023
"""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_fund_universe_snapshot_decision",
        "fund_universe_snapshot",
        schema="evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fund_universe_snapshot_decision_evaluation",
        "fund_universe_snapshot",
        ["decision_id", "evaluation_id"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_fund_universe_snapshot_decision_evaluation",
        "fund_universe_snapshot",
        schema="evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fund_universe_snapshot_decision",
        "fund_universe_snapshot",
        ["decision_id"],
        schema="evaluation",
    )