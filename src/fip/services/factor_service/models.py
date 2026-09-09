import datetime as dt
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class FactorDefinition(Base):
    __tablename__ = "factor_definition"
    __table_args__ = {"schema": "factor"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factor_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    usage: Mapped[str] = mapped_column(String(16), nullable=False)


class FactorVersion(Base):
    __tablename__ = "factor_version"
    __table_args__ = (
        UniqueConstraint(
            "factor_definition_id", "version_label", name="uq_factor_version_definition_label"
        ),
        {"schema": "factor"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factor_definition_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_definition.id", ondelete="RESTRICT"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FactorRun(Base):
    __tablename__ = "factor_run"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "peer_group_snapshot_id",
            "metric_version_id",
            name="uq_factor_run_idempotency",
        ),
        {"schema": "factor"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    peer_group_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"), nullable=False
    )
    metric_version_id: Mapped[int] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT"), nullable=False
    )
    evaluation_policy_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT")
    )
    input_quality_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FactorValue(Base):
    __tablename__ = "factor_value"
    __table_args__ = (
        UniqueConstraint(
            "share_class_id",
            "factor_version_id",
            "window",
            "effective_at",
            "version",
            "evaluation_policy_version_id",
            name="uq_factor_value_versioned",
        ),
        {"schema": "factor"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factor_run_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_run.id", ondelete="RESTRICT"), nullable=False
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    factor_version_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_version.id", ondelete="RESTRICT"), nullable=False
    )
    window: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    raw_value: Mapped[float | None] = mapped_column(Numeric(24, 16))
    normalized_value: Mapped[float | None] = mapped_column(Numeric(24, 16))
    input_lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    adjustment_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_policy_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT")
    )


class FactorEffectiveness(Base):
    __tablename__ = "factor_effectiveness"
    __table_args__ = (
        UniqueConstraint(
            "factor_version_id",
            "peer_group_snapshot_id",
            "evaluation_window",
            "sample_split",
            "validation_policy_version_id",
            name="uq_factor_effectiveness_versioned",
        ),
        {"schema": "factor"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factor_version_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_version.id", ondelete="RESTRICT"), nullable=False
    )
    peer_group_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"), nullable=False
    )
    evaluation_window: Mapped[str] = mapped_column(String(32), nullable=False)
    sample_split: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT"), nullable=False
    )
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
