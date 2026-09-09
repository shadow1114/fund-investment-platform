"""Add immutable Plan-2 factor pipeline storage.

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factor_definition",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("factor_id", sa.String(32), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("usage", sa.String(16), nullable=False),
        schema="factor",
    )
    op.create_table(
        "factor_version",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "factor_definition_id",
            sa.BigInteger,
            sa.ForeignKey("factor.factor_definition.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(32), nullable=False),
        sa.Column("parameters", JSONB, nullable=False),
        sa.UniqueConstraint(
            "factor_definition_id", "version_label", name="uq_factor_version_definition_label"
        ),
        schema="factor",
    )
    op.create_table(
        "factor_run",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column(
            "peer_group_snapshot_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "metric_version_id",
            sa.BigInteger,
            sa.ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_policy_version_id",
            sa.BigInteger,
            sa.ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
        ),
        sa.Column("input_quality_summary", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "decision_id",
            "peer_group_snapshot_id",
            "metric_version_id",
            name="uq_factor_run_idempotency",
        ),
        schema="factor",
    )
    op.create_table(
        "factor_value",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "factor_run_id",
            sa.BigInteger,
            sa.ForeignKey("factor.factor_run.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "share_class_id",
            sa.BigInteger,
            sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "factor_version_id",
            sa.BigInteger,
            sa.ForeignKey("factor.factor_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("window", sa.String(32), nullable=False),
        sa.Column("effective_at", sa.Date, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64)),
        sa.Column("raw_value", sa.Numeric(24, 16)),
        sa.Column("normalized_value", sa.Numeric(24, 16)),
        sa.Column(
            "evaluation_policy_version_id",
            sa.BigInteger,
            sa.ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
        ),
        sa.UniqueConstraint(
            "share_class_id",
            "factor_version_id",
            "window",
            "effective_at",
            "version",
            "evaluation_policy_version_id",
            name="uq_factor_value_versioned",
        ),
        schema="factor",
    )
    op.create_table(
        "factor_effectiveness",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "factor_version_id",
            sa.BigInteger,
            sa.ForeignKey("factor.factor_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "peer_group_snapshot_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("evaluation_window", sa.String(32), nullable=False),
        sa.Column("sample_split", sa.String(32), nullable=False),
        sa.Column(
            "validation_policy_version_id",
            sa.BigInteger,
            sa.ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("detail", JSONB, nullable=False),
        sa.UniqueConstraint(
            "factor_version_id",
            "peer_group_snapshot_id",
            "evaluation_window",
            "sample_split",
            "validation_policy_version_id",
            name="uq_factor_effectiveness_versioned",
        ),
        schema="factor",
    )


def downgrade() -> None:
    op.drop_table("factor_effectiveness", schema="factor")
    op.drop_table("factor_value", schema="factor")
    op.drop_table("factor_run", schema="factor")
    op.drop_table("factor_version", schema="factor")
    op.drop_table("factor_definition", schema="factor")
