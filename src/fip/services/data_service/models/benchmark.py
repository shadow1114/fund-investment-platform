import datetime as dt
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base
from fip.platform.db.mixins import (
    IntervalMixin,
    VersionedMixin,
    interval_check,
    interval_temporal_check_constraints,
    temporal_check_constraints,
)
from fip.platform.db.types import NavNumeric, RatioNumeric


class BenchmarkIndexType(StrEnum):
    PRICE = "PRICE"
    TOTAL_RETURN = "TOTAL_RETURN"
    FULL_PRICE = "FULL_PRICE"


class BenchmarkDefinition(Base):
    __tablename__ = "benchmark_definition"
    __table_args__ = {"schema": "market"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    benchmark_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)


class BenchmarkIndex(Base):
    __tablename__ = "benchmark_index"
    __table_args__ = (
        CheckConstraint(
            "index_type IN ('PRICE', 'TOTAL_RETURN', 'FULL_PRICE')",
            name="ck_benchmark_index_type",
        ),
        UniqueConstraint(
            "provider_code",
            "provider_symbol",
            "index_type",
            name="uq_benchmark_index_provider_symbol_type",
        ),
        {"schema": "market"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    index_type: Mapped[str] = mapped_column(String(32), nullable=False)


class BenchmarkComponent(Base):
    __tablename__ = "benchmark_component"
    __table_args__ = (
        CheckConstraint("weight > 0 AND weight <= 1", name="ck_benchmark_component_weight"),
        UniqueConstraint("benchmark_id", "index_id", name="uq_benchmark_component_index"),
        {"schema": "market"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(
        ForeignKey("market.benchmark_definition.id", ondelete="RESTRICT"), nullable=False
    )
    index_id: Mapped[int] = mapped_column(
        ForeignKey("market.benchmark_index.id", ondelete="RESTRICT"), nullable=False
    )
    weight: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)


class BenchmarkMapping(Base, IntervalMixin):
    __tablename__ = "benchmark_mapping"
    __table_args__ = (
        *interval_temporal_check_constraints("benchmark_mapping"),
        interval_check("benchmark_mapping"),
        CheckConstraint(
            "(share_class_id IS NOT NULL) <> (classification_code IS NOT NULL)",
            name="ck_benchmark_mapping_scope",
        ),
        Index("ix_benchmark_mapping_fund_pit", "share_class_id", "valid_from", "available_at"),
        Index(
            "ix_benchmark_mapping_class_pit",
            "classification_code",
            "valid_from",
            "available_at",
        ),
        {"schema": "market"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(
        ForeignKey("market.benchmark_definition.id", ondelete="RESTRICT"), nullable=False
    )
    share_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT")
    )
    classification_code: Mapped[str | None] = mapped_column(String(32))
    mapping_source: Mapped[str] = mapped_column(String(32), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(32), nullable=False)


class BenchmarkIndexValue(Base, VersionedMixin):
    __tablename__ = "benchmark_index_value"
    __table_args__ = (
        *temporal_check_constraints("benchmark_index_value"),
        CheckConstraint("value > 0", name="ck_benchmark_index_value_positive"),
        Index(
            "ix_benchmark_index_value_pit",
            "index_id",
            "effective_at",
            "available_at",
            text("version DESC"),
        ),
        {"schema": "market"},
    )
    index_id: Mapped[int] = mapped_column(
        ForeignKey("market.benchmark_index.id", ondelete="RESTRICT"), primary_key=True
    )
    effective_at: Mapped[dt.date] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[Decimal] = mapped_column(NavNumeric, nullable=False)
