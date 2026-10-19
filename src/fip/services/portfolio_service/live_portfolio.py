from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class PortfolioState(str, Enum):
    ACTUAL = "ACTUAL"
    TARGET = "TARGET"
    PENDING = "PENDING"


class LivePortfolioStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    PENDING_REBALANCE = "PENDING_REBALANCE"
    SUSPENDED = "SUSPENDED"


class ExecutionStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PendingExecutionConflictError(Exception):
    """Raised when rebalance recommendation is issued while pending execution already exists."""


@dataclass(frozen=True)
class Position:
    fund_id: str
    state: PortfolioState
    shares: Decimal
    cost_basis: Decimal
    market_price: Decimal
    market_value: Decimal
    weight: float
    holding_days: int
    as_of_date: dt.date


@dataclass(frozen=True)
class TradeRecommendation:
    fund_id: str
    direction: str  # BUY or SELL
    shares: Decimal
    target_weight: float
    estimated_price: Decimal


@dataclass(frozen=True)
class ExecutionReport:
    report_id: str
    live_portfolio_id: str
    rebalance_id: str | None
    fund_id: str
    direction: str  # BUY or SELL
    requested_shares: Decimal
    filled_shares: Decimal
    filled_price: Decimal
    fee: Decimal
    status: ExecutionStatus
    reported_at: dt.datetime


@dataclass
class LivePortfolioSnapshot:
    portfolio_id: str
    as_of_date: dt.date
    status: LivePortfolioStatus
    cash_balance: Decimal
    total_equity: Decimal
    has_pending_execution: bool
    target_positions: dict[str, Position] = field(default_factory=dict)
    pending_positions: dict[str, Position] = field(default_factory=dict)
    actual_positions: dict[str, Position] = field(default_factory=dict)
    last_rebalanced_at: dt.datetime | None = None


def initialize_live_portfolio(
    portfolio_id: str,
    target_weights: dict[str, float],
    total_capital: Decimal,
    prices: dict[str, Decimal],
    as_of_date: dt.date,
) -> LivePortfolioSnapshot:
    """Initialize a LivePortfolio from target weights and initial capital.

    Note: As per architecture Section 12, never fake Actual with Target!
    Actual positions start empty until execution fills arrive.
    """
    targets: dict[str, Position] = {}
    for fund_id, weight in target_weights.items():
        allocated_capital = total_capital * Decimal(str(weight))
        price = prices.get(fund_id, Decimal("1.0000"))
        shares = allocated_capital / price if price > 0 else Decimal(0)
        targets[fund_id] = Position(
            fund_id=fund_id,
            state=PortfolioState.TARGET,
            shares=shares,
            cost_basis=allocated_capital,
            market_price=price,
            market_value=allocated_capital,
            weight=weight,
            holding_days=0,
            as_of_date=as_of_date,
        )

    return LivePortfolioSnapshot(
        portfolio_id=portfolio_id,
        as_of_date=as_of_date,
        status=LivePortfolioStatus.ACTIVE,
        cash_balance=total_capital,
        total_equity=total_capital,
        has_pending_execution=False,
        target_positions=targets,
        pending_positions={},
        actual_positions={},
        last_rebalanced_at=None,
    )


def deliver_rebalancing_recommendation(
    snapshot: LivePortfolioSnapshot,
    trades: list[TradeRecommendation],
    delivery_time: dt.datetime,
) -> LivePortfolioSnapshot:
    """Deliver rebalancing trades to execution, transitioning into Pending state."""
    if snapshot.has_pending_execution:
        raise PendingExecutionConflictError(
            "Cannot deliver new rebalancing trades while pending execution is in progress."
        )

    pending_map = dict(snapshot.pending_positions)
    for trade in trades:
        pending_map[trade.fund_id] = Position(
            fund_id=trade.fund_id,
            state=PortfolioState.PENDING,
            shares=trade.shares,
            cost_basis=trade.shares * trade.estimated_price,
            market_price=trade.estimated_price,
            market_value=trade.shares * trade.estimated_price,
            weight=trade.target_weight,
            holding_days=0,
            as_of_date=snapshot.as_of_date,
        )

    return LivePortfolioSnapshot(
        portfolio_id=snapshot.portfolio_id,
        as_of_date=snapshot.as_of_date,
        status=snapshot.status,
        cash_balance=snapshot.cash_balance,
        total_equity=snapshot.total_equity,
        has_pending_execution=bool(pending_map),
        target_positions=dict(snapshot.target_positions),
        pending_positions=pending_map,
        actual_positions=dict(snapshot.actual_positions),
        last_rebalanced_at=delivery_time,
    )


def process_execution_report(
    snapshot: LivePortfolioSnapshot,
    report: ExecutionReport,
) -> LivePortfolioSnapshot:
    """Process an execution report/fill from external broker or simulator."""
    actuals = dict(snapshot.actual_positions)
    pendings = dict(snapshot.pending_positions)
    cash = snapshot.cash_balance

    if report.status in (ExecutionStatus.FILLED, ExecutionStatus.PARTIALLY_FILLED):
        fill_shares = report.filled_shares
        fill_price = report.filled_price
        fee = report.fee
        fund_id = report.fund_id

        if report.direction == "BUY":
            cash -= (fill_shares * fill_price + fee)
            existing = actuals.get(fund_id)
            if existing:
                total_shares = existing.shares + fill_shares
                total_cost = existing.cost_basis + fill_shares * fill_price + fee
                new_mv = total_shares * fill_price
                actuals[fund_id] = Position(
                    fund_id=fund_id,
                    state=PortfolioState.ACTUAL,
                    shares=total_shares,
                    cost_basis=total_cost,
                    market_price=fill_price,
                    market_value=new_mv,
                    weight=0.0,  # Updated during mark-to-market
                    holding_days=existing.holding_days,
                    as_of_date=snapshot.as_of_date,
                )
            else:
                actuals[fund_id] = Position(
                    fund_id=fund_id,
                    state=PortfolioState.ACTUAL,
                    shares=fill_shares,
                    cost_basis=fill_shares * fill_price + fee,
                    market_price=fill_price,
                    market_value=fill_shares * fill_price,
                    weight=0.0,
                    holding_days=0,
                    as_of_date=snapshot.as_of_date,
                )
        elif report.direction == "SELL":
            cash += (fill_shares * fill_price - fee)
            existing = actuals.get(fund_id)
            if existing:
                rem_shares = max(Decimal(0), existing.shares - fill_shares)
                if rem_shares == 0:
                    del actuals[fund_id]
                else:
                    prop = rem_shares / existing.shares
                    actuals[fund_id] = Position(
                        fund_id=fund_id,
                        state=PortfolioState.ACTUAL,
                        shares=rem_shares,
                        cost_basis=existing.cost_basis * prop,
                        market_price=fill_price,
                        market_value=rem_shares * fill_price,
                        weight=0.0,
                        holding_days=existing.holding_days,
                        as_of_date=snapshot.as_of_date,
                    )

        # Update or remove pending
        if fund_id in pendings:
            pending_pos = pendings[fund_id]
            remaining_pending_shares = max(Decimal(0), pending_pos.shares - fill_shares)
            if report.status == ExecutionStatus.FILLED or remaining_pending_shares == 0:
                del pendings[fund_id]
            else:
                pendings[fund_id] = Position(
                    fund_id=fund_id,
                    state=PortfolioState.PENDING,
                    shares=remaining_pending_shares,
                    cost_basis=remaining_pending_shares * pending_pos.market_price,
                    market_price=pending_pos.market_price,
                    market_value=remaining_pending_shares * pending_pos.market_price,
                    weight=pending_pos.weight,
                    holding_days=0,
                    as_of_date=snapshot.as_of_date,
                )

    elif report.status in (ExecutionStatus.REJECTED, ExecutionStatus.EXPIRED):
        # Cancel pending
        if report.fund_id in pendings:
            del pendings[report.fund_id]

    # Recalculate equity
    total_mv = sum((p.market_value for p in actuals.values()), Decimal(0))
    total_equity = cash + total_mv

    # Recalculate actual weights
    reweighted_actuals = {}
    for f_id, p in actuals.items():
        w = float(p.market_value / total_equity) if total_equity > 0 else 0.0
        reweighted_actuals[f_id] = Position(
            fund_id=p.fund_id,
            state=p.state,
            shares=p.shares,
            cost_basis=p.cost_basis,
            market_price=p.market_price,
            market_value=p.market_value,
            weight=w,
            holding_days=p.holding_days,
            as_of_date=p.as_of_date,
        )

    return LivePortfolioSnapshot(
        portfolio_id=snapshot.portfolio_id,
        as_of_date=snapshot.as_of_date,
        status=snapshot.status,
        cash_balance=cash,
        total_equity=total_equity,
        has_pending_execution=bool(pendings),
        target_positions=dict(snapshot.target_positions),
        pending_positions=pendings,
        actual_positions=reweighted_actuals,
        last_rebalanced_at=snapshot.last_rebalanced_at,
    )
