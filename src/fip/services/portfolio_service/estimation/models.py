"""Immutable persistence models for Plan-3 return and risk estimation."""

import datetime as dt
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base

RUN_STATUSES = (
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "COMPLETED_WITH_WARNING",
    "REJECTED",
    "FAILED",
)
FINAL_BUSINESS_STATUSES = ("COMPLETED", "COMPLETED_WITH_WARNING", "REJECTED")
RETURN_BASES = ("ABSOLUTE", "EXCESS")


class EstimationMethodVersion(Base):
    __tablename__ = "estimation_method_version"
    __table_args__ = (
        UniqueConstraint(
            "method_code",
            "version_label",
            name="uq_estimation_method_version_identity",
        ),
        {"schema": "portfolio"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    method_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    implementation_path: Mapped[str] = mapped_column(String(255), nullable=False)
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EstimationParameterVersion(Base):
    __tablename__ = "estimation_parameter_version"
    __table_args__ = (
        UniqueConstraint("version_label", name="uq_estimation_parameter_version_label"),
        {"schema": "portfolio"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EstimationRun(Base):
    __tablename__ = "estimation_run"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "universe_snapshot_id",
            "estimation_method_version_id",
            "estimation_parameter_version_id",
            "estimation_policy_version_id",
            "validation_policy_version_id",
            "code_version",
            name="uq_estimation_run_idempotency",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', "
            "'COMPLETED_WITH_WARNING', 'REJECTED', 'FAILED')",
            name="ck_estimation_run_status",
        ),
        CheckConstraint(
            "input_lineage_fingerprint IS NOT NULL "
            "OR status IN ('PENDING', 'RUNNING', 'FAILED')",
            name="ck_estimation_run_final_lineage",
        ),
        CheckConstraint(
            "input_lineage_fingerprint IS NULL " "OR char_length(input_lineage_fingerprint) = 64",
            name="ck_estimation_run_lineage_fingerprint_length",
        ),
        CheckConstraint(
            "approved_for_optimization = " "(status IN ('COMPLETED', 'COMPLETED_WITH_WARNING'))",
            name="ck_estimation_run_approval_status",
        ),
        Index(
            "ix_estimation_run_approved_final",
            "id",
            postgresql_where=text(
                "approved_for_optimization AND " "status IN ('COMPLETED', 'COMPLETED_WITH_WARNING')"
            ),
        ),
        {"schema": "portfolio"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    universe_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_universe_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    estimation_method_version_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.estimation_method_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    estimation_parameter_version_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.estimation_parameter_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    estimation_policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    validation_policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_for_optimization: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    input_lineage_fingerprint: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ReturnEstimate(Base):
    __tablename__ = "return_estimate"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "return_basis",
            "share_class_id",
            name="uq_return_estimate_run_basis_instrument",
        ),
        CheckConstraint(
            "return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_return_estimate_basis",
        ),
        Index(
            "ix_return_estimate_absolute_lookup",
            "run_id",
            "share_class_id",
            postgresql_where=text("return_basis = 'ABSOLUTE'"),
        ),
        {"schema": "portfolio"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"), nullable=False
    )
    return_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    sample_mean: Mapped[str] = mapped_column(Text, nullable=False)
    shrinkage_target: Mapped[str] = mapped_column(Text, nullable=False)
    shrinkage_intensity: Mapped[str] = mapped_column(Text, nullable=False)
    mu_before_clip: Mapped[str] = mapped_column(Text, nullable=False)
    mu: Mapped[str] = mapped_column(Text, nullable=False)
    mu_clipped: Mapped[bool] = mapped_column(Boolean, nullable=False)
    numeric_encoding_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RiskEstimate(Base):
    __tablename__ = "risk_estimate"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "return_basis",
            "share_class_id",
            name="uq_risk_estimate_run_basis_instrument",
        ),
        CheckConstraint(
            "return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_risk_estimate_basis",
        ),
        Index(
            "ix_risk_estimate_absolute_lookup",
            "run_id",
            "share_class_id",
            postgresql_where=text("return_basis = 'ABSOLUTE'"),
        ),
        {"schema": "portfolio"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"), nullable=False
    )
    return_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    variance: Mapped[str] = mapped_column(Text, nullable=False)
    volatility: Mapped[str] = mapped_column(Text, nullable=False)
    numeric_encoding_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CovarianceEstimate(Base):
    __tablename__ = "covariance_estimate"
    __table_args__ = (
        UniqueConstraint("run_id", "return_basis", name="uq_covariance_estimate_run_basis"),
        CheckConstraint(
            "return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_covariance_estimate_basis",
        ),
        CheckConstraint(
            "observation_count >= 0 AND instrument_count >= 0 " "AND dropped_dates_count >= 0",
            name="ck_covariance_estimate_nonnegative_counts",
        ),
        CheckConstraint(
            "covariance_payload ?& ARRAY['shape', 'instrument_order', "
            "'lower_triangle', 'numeric_encoding_version', 'checksum']",
            name="ck_covariance_estimate_covariance_payload",
        ),
        CheckConstraint(
            "correlation_payload ?& ARRAY['shape', 'instrument_order', "
            "'lower_triangle', 'numeric_encoding_version', 'checksum']",
            name="ck_covariance_estimate_correlation_payload",
        ),
        Index(
            "ix_covariance_estimate_absolute_lookup",
            "run_id",
            postgresql_where=text("return_basis = 'ABSOLUTE'"),
        ),
        {"schema": "portfolio"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"), nullable=False
    )
    return_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    covariance_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    shrinkage_intensity: Mapped[str] = mapped_column(Text, nullable=False)
    sample_min_eigenvalue: Mapped[str] = mapped_column(Text, nullable=False)
    sample_max_eigenvalue: Mapped[str] = mapped_column(Text, nullable=False)
    sample_condition_number: Mapped[str] = mapped_column(Text, nullable=False)
    final_min_eigenvalue: Mapped[str] = mapped_column(Text, nullable=False)
    final_max_eigenvalue: Mapped[str] = mapped_column(Text, nullable=False)
    final_condition_number: Mapped[str] = mapped_column(Text, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    instrument_count: Mapped[int] = mapped_column(Integer, nullable=False)
    dropped_dates_count: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_instruments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    input_lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EstimationValidationResult(Base):
    __tablename__ = "estimation_validation_result"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "return_basis",
            "code",
            name="uq_estimation_validation_run_basis_code",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "return_basis IS NULL OR return_basis IN ('ABSOLUTE', 'EXCESS')",
            name="ck_estimation_validation_basis",
        ),
        CheckConstraint(
            "severity IN ('REJECT', 'WARNING')",
            name="ck_estimation_validation_severity",
        ),
        CheckConstraint(
            "status IN ('PASSED', 'FAILED')",
            name="ck_estimation_validation_status",
        ),
        {"schema": "portfolio"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.estimation_run.id", ondelete="CASCADE"), nullable=False
    )
    return_basis: Mapped[str | None] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
