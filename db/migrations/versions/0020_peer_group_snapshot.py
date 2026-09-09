"""Persist Plan-2 peer group snapshots.

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "peer_group_snapshot",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column("classification_code", sa.String(32), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("policy_version_id", sa.BigInteger, nullable=False),
        sa.Column("decision_at", sa.Date, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("member_count", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(["policy_version_id"], ["governance.policy_version.id"]),
        sa.UniqueConstraint(
            "decision_id",
            "classification_code",
            "base_currency",
            name="uq_peer_group_snapshot_decision_key",
        ),
        schema="evaluation",
    )
    op.create_table(
        "peer_group_member",
        sa.Column("snapshot_id", sa.BigInteger, nullable=False),
        sa.Column("share_class_id", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["evaluation.peer_group_snapshot.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["share_class_id"], ["fund.fund_share_class.id"]),
        sa.PrimaryKeyConstraint("snapshot_id", "share_class_id"),
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_table("peer_group_member", schema="evaluation")
    op.drop_table("peer_group_snapshot", schema="evaluation")
