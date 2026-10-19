from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from fip.services.portfolio_service.live_portfolio import (
    LivePortfolioSnapshot,
    Position,
)


@dataclass(frozen=True)
class DriftAnalysis:
    fund_signed_drift: dict[str, float]
    fund_absolute_drift: dict[str, float]
    category_signed_drift: dict[str, float]
    category_absolute_drift: dict[str, float]
    max_fund_absolute_drift: float
    max_category_absolute_drift: float
    is_fund_drift_exceeded: bool
    is_category_drift_exceeded: bool
    is_drift_triggered: bool


def mark_to_market_portfolio(
    snapshot: LivePortfolioSnapshot,
    prices: dict[str, Decimal],
    as_of_date: dt.date,
) -> LivePortfolioSnapshot:
    """Mark all actual positions to current market prices and update weights."""
    updated_actuals: dict[str, Position] = {}
    total_mv = Decimal(0)

    # Days elapsed
    days_delta = (as_of_date - snapshot.as_of_date).days if as_of_date > snapshot.as_of_date else 0

    for fund_id, pos in snapshot.actual_positions.items():
        price = prices.get(fund_id, pos.market_price)
        mv = pos.shares * price
        total_mv += mv
        updated_actuals[fund_id] = Position(
            fund_id=fund_id,
            state=pos.state,
            shares=pos.shares,
            cost_basis=pos.cost_basis,
            market_price=price,
            market_value=mv,
            weight=0.0,
            holding_days=pos.holding_days + days_delta,
            as_of_date=as_of_date,
        )

    total_equity = snapshot.cash_balance + total_mv
    reweighted: dict[str, Position] = {}
    for fund_id, pos in updated_actuals.items():
        w = float(pos.market_value / total_equity) if total_equity > 0 else 0.0
        reweighted[fund_id] = Position(
            fund_id=pos.fund_id,
            state=pos.state,
            shares=pos.shares,
            cost_basis=pos.cost_basis,
            market_price=pos.market_price,
            market_value=pos.market_value,
            weight=w,
            holding_days=pos.holding_days,
            as_of_date=pos.as_of_date,
        )

    return LivePortfolioSnapshot(
        portfolio_id=snapshot.portfolio_id,
        as_of_date=as_of_date,
        status=snapshot.status,
        cash_balance=snapshot.cash_balance,
        total_equity=total_equity,
        has_pending_execution=snapshot.has_pending_execution,
        target_positions=dict(snapshot.target_positions),
        pending_positions=dict(snapshot.pending_positions),
        actual_positions=reweighted,
        last_rebalanced_at=snapshot.last_rebalanced_at,
    )


def calculate_portfolio_drift(
    snapshot: LivePortfolioSnapshot,
    category_map: dict[str, str] | None = None,
    fund_drift_threshold: float = 0.03,
    category_drift_threshold: float = 0.05,
    non_tradable_funds: set[str] | None = None,
) -> DriftAnalysis:
    """Calculate signed and absolute drift across funds and categories.

    Per spec 06-rebalancing.md Section 4:
    - Absolute drift is used for trigger evaluation.
    - Signed drift is used for display, attribution, and trade direction.
    - Fund-level and category-level drift thresholds are evaluated independently.
    """
    category_map = category_map or {}
    non_tradables = non_tradable_funds or set()

    all_funds = set(snapshot.target_positions.keys()) | set(snapshot.actual_positions.keys())

    fund_signed: dict[str, float] = {}
    fund_absolute: dict[str, float] = {}

    cat_target_weights: dict[str, float] = {}
    cat_actual_weights: dict[str, float] = {}

    for f in all_funds:
        target_w = snapshot.target_positions[f].weight if f in snapshot.target_positions else 0.0
        actual_w = snapshot.actual_positions[f].weight if f in snapshot.actual_positions else 0.0

        signed = actual_w - target_w
        fund_signed[f] = signed
        fund_absolute[f] = abs(signed)

        cat = category_map.get(f, "UNCLASSIFIED")
        cat_target_weights[cat] = cat_target_weights.get(cat, 0.0) + target_w
        cat_actual_weights[cat] = cat_actual_weights.get(cat, 0.0) + actual_w

    cat_signed: dict[str, float] = {}
    cat_absolute: dict[str, float] = {}
    all_cats = set(cat_target_weights.keys()) | set(cat_actual_weights.keys())
    for cat in all_cats:
        c_signed = cat_actual_weights.get(cat, 0.0) - cat_target_weights.get(cat, 0.0)
        cat_signed[cat] = c_signed
        cat_absolute[cat] = abs(c_signed)

    # Exclude non-tradable funds from trigger evaluation to avoid false alarms
    eval_fund_abs = {
        f: d for f, d in fund_absolute.items() if f not in non_tradables
    }
    max_fund_abs = max(eval_fund_abs.values()) if eval_fund_abs else 0.0
    max_cat_abs = max(cat_absolute.values()) if cat_absolute else 0.0

    is_fund_exceeded = max_fund_abs >= fund_drift_threshold
    is_cat_exceeded = max_cat_abs >= category_drift_threshold
    is_triggered = is_fund_exceeded or is_cat_exceeded

    return DriftAnalysis(
        fund_signed_drift=fund_signed,
        fund_absolute_drift=fund_absolute,
        category_signed_drift=cat_signed,
        category_absolute_drift=cat_absolute,
        max_fund_absolute_drift=max_fund_abs,
        max_category_absolute_drift=max_cat_abs,
        is_fund_drift_exceeded=is_fund_exceeded,
        is_category_drift_exceeded=is_cat_exceeded,
        is_drift_triggered=is_triggered,
    )
