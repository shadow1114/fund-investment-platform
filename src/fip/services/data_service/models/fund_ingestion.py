"""Persisted previews and per-subject ingestion state."""

import datetime as dt

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class FundIngestionPreview(Base):
    __tablename__ = "fund_ingestion_preview"
    __table_args__ = {"schema": "governance"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    members: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FundIngestionRunItem(Base):
    __tablename__ = "fund_ingestion_run_item"
    __table_args__ = (
        UniqueConstraint(
            "operation_id",
            "fund_id",
            "share_class_id",
            name="uq_fund_ingestion_run_item_subject",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_fund_ingestion_run_item_operation_status", "operation_id", "status", "id"),
        {"schema": "governance"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("governance.calculation_job.execution_id", ondelete="CASCADE"), nullable=False
    )
    fund_id: Mapped[int] = mapped_column(ForeignKey("fund.fund.id"), nullable=False)
    public_fund_id: Mapped[str] = mapped_column(String(32), nullable=False)
    share_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("fund.fund_share_class.id"), nullable=True
    )
    symbol: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
