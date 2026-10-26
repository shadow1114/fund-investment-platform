from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class PortfolioRecord(Base):
    __tablename__ = "portfolio"
    __table_args__ = {"schema": "portfolio"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    portfolio_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    portfolio_version: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    portfolio_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    viewer_user_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class OptimizationRecord(Base):
    __tablename__ = "optimization"
    __table_args__ = {"schema": "portfolio"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolio.portfolio.id"), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class DecisionRecord(Base):
    __tablename__ = "decision"
    __table_args__ = {"schema": "portfolio"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolio.portfolio.id"), nullable=False)
    optimization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class BacktestRecord(Base):
    __tablename__ = "backtest"
    __table_args__ = {"schema": "backtest"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class LivePortfolioRecord(Base):
    __tablename__ = "live_portfolio"
    __table_args__ = (
        Index("ix_live_portfolio_portfolio_id", "portfolio_id"),
        {"schema": "portfolio"},
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolio.portfolio.id"), nullable=False)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal(0)
    )
    total_equity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal(0)
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    has_pending_execution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_rebalanced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class PortfolioPositionRecord(Base):
    __tablename__ = "portfolio_position"
    __table_args__ = (
        Index("ix_portfolio_position_live_state", "live_portfolio_id", "state", "fund_id"),
        {"schema": "portfolio"},
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    live_portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio.live_portfolio.id"), nullable=False
    )
    fund_id: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)  # ACTUAL, TARGET, PENDING
    shares: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal(0))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal(0))
    market_price: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal(0)
    )
    market_value: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal(0)
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    holding_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)


class ExecutionReportRecord(Base):
    __tablename__ = "execution_report"
    __table_args__ = (
        Index("ix_execution_report_live_status", "live_portfolio_id", "status"),
        {"schema": "portfolio"},
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    live_portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio.live_portfolio.id"), nullable=False
    )
    rebalance_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fund_id: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY, SELL
    requested_shares: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    filled_shares: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal(0)
    )
    filled_price: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal(0)
    )
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal(0))
    # SUBMITTED, PARTIALLY_FILLED, FILLED, REJECTED, EXPIRED
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reported_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RebalanceEventRecord(Base):
    __tablename__ = "rebalance_event"
    __table_args__ = (
        Index("ix_rebalance_event_live_date", "live_portfolio_id", "decision_at"),
        {"schema": "portfolio"},
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    live_portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio.live_portfolio.id"), nullable=False
    )
    decision_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    trigger_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    primary_trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    recompute_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    turnover: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_improvement: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RebalanceTradeRecord(Base):
    __tablename__ = "rebalance_trade"
    __table_args__ = (
        Index("ix_rebalance_trade_rebalance_id", "rebalance_id"),
        {"schema": "portfolio"},
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rebalance_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio.rebalance_event.id"), nullable=False
    )
    fund_id: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False)
    current_weight: Mapped[float] = mapped_column(Float, nullable=False)
    weight_delta: Mapped[float] = mapped_column(Float, nullable=False)
    target_shares: Mapped[float] = mapped_column(Float, nullable=False)
    delta_shares: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_amount: Mapped[float] = mapped_column(Float, nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_filtered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unachieved_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RebalancePolicyRecord(Base):
    __tablename__ = "rebalance_policy"
    __table_args__ = {"schema": "portfolio"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    weight_drift_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.03)
    category_drift_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    min_trade_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.005)
    turnover_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.30)
    cost_benefit_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    pending_timeout_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
