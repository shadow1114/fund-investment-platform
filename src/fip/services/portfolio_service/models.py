from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, String
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
