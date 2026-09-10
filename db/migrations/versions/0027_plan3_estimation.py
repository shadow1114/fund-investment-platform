"""Persist Plan-3 estimation versions, runs, results, and validation.

Revision ID: 0027
Revises: 0026
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estimation_method_version",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("method_code", sa.String(64), nullable=False),
        sa.Column("version_label", sa.String(32), nullable=False),
        sa.Column("implementation_path", sa.String(255), nullable=False),
        sa.Column("specification", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "method_code",
            "version_label",
            name="uq_estimation_method_version_identity",
        ),
        schema="portfolio",
    )
    op.create_table(
        "estimation_parameter_version",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("version_label", sa.String(32), nullable=False),
        sa.Column("parameters", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("version_label", name="uq_estimation_parameter_version_label"),
        schema="portfolio",
    )
    op.create_table(
        "estimation_run",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column(
            "universe_snapshot_id",
            sa.BigInteger,
            sa.ForeignKey("evaluation.fund_universe_snapshot.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "estimation_method_version_id",
            sa.BigInteger,
            sa.ForeignKey("portfolio.estimation_method_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "estimation_parameter_version_id",
            sa.BigInteger,
            sa.ForeignKey("portfolio.estimation_parameter_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "estimation_policy_version_id",
            sa.BigInteger,
            sa.ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "validation_policy_version_id",
            sa.BigInteger,
            sa.ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "approved_for_optimization",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("input_lineage_fingerprint", sa.String(64)),
        sa.Column("error_code", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "decision_id",
            "universe_snapshot_id",
            "estimation_method_version_id",
            "estimation_parameter_version_id",
            "estimation_policy_version_id",
            "validation_policy_version_id",
            "code_version",
            name="uq_estimation_run_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', "
            "'COMPLETED_WITH_WARNING', 'REJECTED', 'FAILED')",
            name="ck_estimation_run_status",
        ),
        sa.CheckConstraint(
            "input_lineage_fingerprint IS NOT NULL "
            "OR status IN ('PENDING', 'RUNNING', 'FAILED')",
            name="ck_estimation_run_final_lineage",
        ),
        sa.CheckConstraint(
            "input_lineage_fingerprint IS NULL " "OR char_length(input_lineage_fingerprint) = 64",
            name="ck_estimation_run_lineage_fingerprint_length",
        ),
        sa.CheckConstraint(
            "approved_for_optimization = " "(status IN ('COMPLETED', 'COMPLETED_WITH_WARNING'))",
            name="ck_estimation_run_approval_status",
        ),
        schema="portfolio",
    )
    op.create_index(
        "ix_estimation_run_approved_final",
        "estimation_run",
        ["id"],
        schema="portfolio",
        postgresql_where=sa.text(
            "approved_for_optimization AND " "status IN ('COMPLETED', 'COMPLETED_WITH_WARNING')"
        ),
    )
    op.create_table(
        "return_estimate",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "run_id",
            sa.BigInteger,
            sa.ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("return_basis", sa.String(16), nullable=False),
        sa.Column(
            "share_class_id",
            sa.BigInteger,
            sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sample_mean", sa.Text, nullable=False),
        sa.Column("shrinkage_target", sa.Text, nullable=False),
        sa.Column("shrinkage_intensity", sa.Text, nullable=False),
        sa.Column("mu_before_clip", sa.Text, nullable=False),
        sa.Column("mu", sa.Text, nullable=False),
        sa.Column("mu_clipped", sa.Boolean, nullable=False),
        sa.Column("numeric_encoding_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "run_id",
            "return_basis",
            "share_class_id",
            name="uq_return_estimate_run_basis_instrument",
        ),
        sa.CheckConstraint(
            "return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_return_estimate_basis",
        ),
        schema="portfolio",
    )
    op.create_index(
        "ix_return_estimate_absolute_lookup",
        "return_estimate",
        ["run_id", "share_class_id"],
        schema="portfolio",
        postgresql_where=sa.text("return_basis = 'ABSOLUTE'"),
    )
    op.create_table(
        "risk_estimate",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "run_id",
            sa.BigInteger,
            sa.ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("return_basis", sa.String(16), nullable=False),
        sa.Column(
            "share_class_id",
            sa.BigInteger,
            sa.ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("variance", sa.Text, nullable=False),
        sa.Column("volatility", sa.Text, nullable=False),
        sa.Column("numeric_encoding_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "run_id",
            "return_basis",
            "share_class_id",
            name="uq_risk_estimate_run_basis_instrument",
        ),
        sa.CheckConstraint(
            "return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_risk_estimate_basis",
        ),
        schema="portfolio",
    )
    op.create_index(
        "ix_risk_estimate_absolute_lookup",
        "risk_estimate",
        ["run_id", "share_class_id"],
        schema="portfolio",
        postgresql_where=sa.text("return_basis = 'ABSOLUTE'"),
    )
    op.create_table(
        "covariance_estimate",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "run_id",
            sa.BigInteger,
            sa.ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("return_basis", sa.String(16), nullable=False),
        sa.Column("covariance_payload", JSONB, nullable=False),
        sa.Column("correlation_payload", JSONB, nullable=False),
        sa.Column("shrinkage_intensity", sa.Text, nullable=False),
        sa.Column("sample_min_eigenvalue", sa.Text, nullable=False),
        sa.Column("sample_max_eigenvalue", sa.Text, nullable=False),
        sa.Column("sample_condition_number", sa.Text, nullable=False),
        sa.Column("final_min_eigenvalue", sa.Text, nullable=False),
        sa.Column("final_max_eigenvalue", sa.Text, nullable=False),
        sa.Column("final_condition_number", sa.Text, nullable=False),
        sa.Column("observation_count", sa.Integer, nullable=False),
        sa.Column("instrument_count", sa.Integer, nullable=False),
        sa.Column("dropped_dates_count", sa.Integer, nullable=False),
        sa.Column("excluded_instruments", JSONB, nullable=False),
        sa.Column("input_lineage", JSONB, nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("run_id", "return_basis", name="uq_covariance_estimate_run_basis"),
        sa.CheckConstraint(
            "return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_covariance_estimate_basis",
        ),
        sa.CheckConstraint(
            "observation_count >= 0 AND instrument_count >= 0 " "AND dropped_dates_count >= 0",
            name="ck_covariance_estimate_nonnegative_counts",
        ),
        sa.CheckConstraint(
            "covariance_payload ?& ARRAY['shape', 'instrument_order', "
            "'lower_triangle', 'numeric_encoding_version', 'checksum']",
            name="ck_covariance_estimate_covariance_payload",
        ),
        sa.CheckConstraint(
            "correlation_payload ?& ARRAY['shape', 'instrument_order', "
            "'lower_triangle', 'numeric_encoding_version', 'checksum']",
            name="ck_covariance_estimate_correlation_payload",
        ),
        schema="portfolio",
    )
    op.create_index(
        "ix_covariance_estimate_absolute_lookup",
        "covariance_estimate",
        ["run_id"],
        schema="portfolio",
        postgresql_where=sa.text("return_basis = 'ABSOLUTE'"),
    )
    op.create_table(
        "estimation_validation_result",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "run_id",
            sa.BigInteger,
            sa.ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("return_basis", sa.String(16)),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("detail", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "run_id",
            "return_basis",
            "code",
            name="uq_estimation_validation_run_basis_code",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint(
            "return_basis IS NULL OR return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_estimation_validation_basis",
        ),
        sa.CheckConstraint(
            "severity IN ('REJECT', 'WARNING')",
            name="ck_estimation_validation_severity",
        ),
        sa.CheckConstraint(
            "status IN ('PASSED', 'FAILED')",
            name="ck_estimation_validation_status",
        ),
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_table("estimation_validation_result", schema="portfolio")
    op.drop_index(
        "ix_covariance_estimate_absolute_lookup",
        table_name="covariance_estimate",
        schema="portfolio",
    )
    op.drop_table("covariance_estimate", schema="portfolio")
    op.drop_index(
        "ix_risk_estimate_absolute_lookup",
        table_name="risk_estimate",
        schema="portfolio",
    )
    op.drop_table("risk_estimate", schema="portfolio")
    op.drop_index(
        "ix_return_estimate_absolute_lookup",
        table_name="return_estimate",
        schema="portfolio",
    )
    op.drop_table("return_estimate", schema="portfolio")
    op.drop_index(
        "ix_estimation_run_approved_final",
        table_name="estimation_run",
        schema="portfolio",
    )
    op.drop_table("estimation_run", schema="portfolio")
    op.drop_table("estimation_parameter_version", schema="portfolio")
    op.drop_table("estimation_method_version", schema="portfolio")
