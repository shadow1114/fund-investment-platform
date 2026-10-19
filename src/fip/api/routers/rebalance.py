from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.orm import Session

from fip.api.auth import get_principal
from fip.api.context import Principal
from fip.api.contracts import success
from fip.api.errors import NotFoundError
from fip.api.schemas import (
    EvaluateRebalanceRequest,
    ExecutionReportRequest,
    ExecutionReportResponse,
    LivePortfolioViewModel,
    PositionViewModel,
    RebalanceProposalViewModel,
    RebalanceTradeViewModel,
    TypedEnvelope,
)
from fip.services.portfolio_service.drift import calculate_portfolio_drift
from fip.services.portfolio_service.live_portfolio import (
    ExecutionReport,
    ExecutionStatus,
    LivePortfolioSnapshot,
    Position,
    initialize_live_portfolio,
    process_execution_report,
)
from fip.services.portfolio_service.rebalance_proposer import generate_rebalance_proposal
from fip.services.portfolio_service.rebalance_trigger import RebalanceTriggerEngine

# FastAPI's dependency declarations live in signatures.
# ruff: noqa: B008

router = APIRouter()

# In-memory store for development/testing when PostgreSQL is absent or in memory mode
_LIVE_PORTFOLIOS: dict[str, LivePortfolioSnapshot] = {}
_HISTORICAL_REBALANCES: dict[str, list[dict[str, Any]]] = {}
_REBALANCE_TRADES: dict[str, list[dict[str, Any]]] = {}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _get_or_create_live_portfolio(
    portfolio_id: str,
    session: Session | None = None,
) -> LivePortfolioSnapshot:
    if portfolio_id in _LIVE_PORTFOLIOS:
        return _LIVE_PORTFOLIOS[portfolio_id]

    # Initialize default live snapshot
    target_weights = {"000001": 0.5, "000002": 0.5}
    prices = {"000001": Decimal("1.0"), "000002": Decimal("1.0")}
    snapshot = initialize_live_portfolio(
        portfolio_id=portfolio_id,
        target_weights=target_weights,
        total_capital=Decimal("100000.00"),
        prices=prices,
        as_of_date=dt.date(2026, 1, 10),
    )
    _LIVE_PORTFOLIOS[portfolio_id] = snapshot
    return snapshot


def _snapshot_to_view_model(snap: LivePortfolioSnapshot) -> LivePortfolioViewModel:
    def _convert_pos(positions: dict[str, Position]) -> list[PositionViewModel]:
        return [
            PositionViewModel(
                fund_id=p.fund_id,
                state=p.state.value,
                shares=float(p.shares),
                cost_basis=float(p.cost_basis),
                market_price=float(p.market_price),
                market_value=float(p.market_value),
                weight=p.weight,
                holding_days=p.holding_days,
            )
            for p in positions.values()
        ]

    return LivePortfolioViewModel(
        portfolio_id=snap.portfolio_id,
        as_of_date=snap.as_of_date.isoformat(),
        status=snap.status.value,
        cash_balance=float(snap.cash_balance),
        total_equity=float(snap.total_equity),
        has_pending_execution=snap.has_pending_execution,
        target_positions=_convert_pos(snap.target_positions),
        pending_positions=_convert_pos(snap.pending_positions),
        actual_positions=_convert_pos(snap.actual_positions),
        last_rebalanced_at=snap.last_rebalanced_at.isoformat() if snap.last_rebalanced_at else None,
    )


@router.get(
    "/portfolios/{portfolio_id}/live",
    operation_id="getLivePortfolio",
    response_model=TypedEnvelope[LivePortfolioViewModel],
)
def get_live_portfolio(
    portfolio_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    snapshot = _get_or_create_live_portfolio(portfolio_id)
    view = _snapshot_to_view_model(snapshot)
    return success(view.model_dump(mode="json"), request_id=_request_id(request))


@router.post(
    "/portfolios/{portfolio_id}/execution-reports",
    operation_id="submitExecutionReport",
    response_model=TypedEnvelope[ExecutionReportResponse],
)
def submit_execution_report(
    portfolio_id: str,
    request: Request,
    payload: ExecutionReportRequest = Body(...),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    snapshot = _get_or_create_live_portfolio(portfolio_id)

    report = ExecutionReport(
        report_id=payload.report_id,
        live_portfolio_id=portfolio_id,
        rebalance_id=payload.rebalance_id,
        fund_id=payload.fund_id,
        direction=payload.direction,
        requested_shares=Decimal(str(payload.requested_shares)),
        filled_shares=Decimal(str(payload.filled_shares)),
        filled_price=Decimal(str(payload.filled_price)),
        fee=Decimal(str(payload.fee)),
        status=ExecutionStatus(payload.status),
        reported_at=dt.datetime.now(dt.UTC),
    )

    updated_snapshot = process_execution_report(snapshot, report)
    _LIVE_PORTFOLIOS[portfolio_id] = updated_snapshot

    response = ExecutionReportResponse(
        report_id=payload.report_id,
        portfolio_id=portfolio_id,
        status=updated_snapshot.status.value,
        has_pending_execution=updated_snapshot.has_pending_execution,
        total_equity=float(updated_snapshot.total_equity),
        cash_balance=float(updated_snapshot.cash_balance),
    )
    return success(response.model_dump(mode="json"), request_id=_request_id(request))


@router.post(
    "/portfolios/{portfolio_id}/rebalances/evaluate",
    operation_id="evaluateRebalance",
    response_model=TypedEnvelope[RebalanceProposalViewModel],
)
def evaluate_rebalance(
    portfolio_id: str,
    request: Request,
    payload: EvaluateRebalanceRequest = Body(...),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    snapshot = _get_or_create_live_portfolio(portfolio_id)
    decision_date = dt.date.fromisoformat(payload.decision_at)

    prices_decimal = {f: Decimal(str(p)) for f, p in payload.prices.items()}

    # 1. Drift Analysis
    drift = calculate_portfolio_drift(
        snapshot,
        fund_drift_threshold=payload.fund_drift_threshold,
        category_drift_threshold=payload.category_drift_threshold,
    )

    # 2. Trigger Evaluation
    engine = RebalanceTriggerEngine(periodic_days=63)
    trigger_decision = engine.evaluate(
        snapshot=snapshot,
        current_date=decision_date,
        drift_analysis=drift,
        eligibility_status={},
        constraint_violations=[],
    )

    # 3. Propose Trades if triggered or if targets provided
    target_weights = {
        f: pos.weight for f, pos in snapshot.target_positions.items()
    } or {"000001": 0.5, "000002": 0.5}

    proposal = generate_rebalance_proposal(
        snapshot=snapshot,
        target_weights=target_weights,
        prices=prices_decimal,
        fee_rate=payload.fee_rate,
        min_trade_threshold=payload.min_trade_threshold,
        expected_annualized_improvement=payload.expected_annualized_improvement,
    )

    rebalance_id = f"REB-{portfolio_id}-{payload.decision_at}"
    trade_views = [
        RebalanceTradeViewModel(
            fund_id=t.fund_id,
            direction=t.direction,
            target_weight=t.target_weight,
            current_weight=t.current_weight,
            weight_delta=t.weight_delta,
            target_shares=t.target_shares,
            delta_shares=t.delta_shares,
            estimated_amount=t.estimated_amount,
            eligibility_status=t.eligibility_status,
            is_filtered=t.is_filtered,
            unachieved_reason=t.unachieved_reason,
        )
        for t in proposal.trades
    ]

    primary_trigger_str = (
        trigger_decision.primary_trigger.value if trigger_decision.primary_trigger else None
    )
    scope_str = (
        trigger_decision.recompute_scope.value if trigger_decision.recompute_scope else None
    )

    # Store in history
    event_dict = {
        "rebalance_id": rebalance_id,
        "portfolio_id": portfolio_id,
        "decision_at": payload.decision_at,
        "is_triggered": trigger_decision.is_triggered,
        "primary_trigger": primary_trigger_str,
        "recompute_scope": scope_str,
        "outcome": proposal.decision_outcome.value,
        "turnover": proposal.turnover,
        "estimated_cost": proposal.estimated_cost,
    }
    _HISTORICAL_REBALANCES.setdefault(portfolio_id, []).append(event_dict)
    _REBALANCE_TRADES[rebalance_id] = [t.model_dump(mode="json") for t in trade_views]

    result = RebalanceProposalViewModel(
        is_triggered=trigger_decision.is_triggered,
        trigger_types=[t.value for t in trigger_decision.trigger_types],
        primary_trigger=primary_trigger_str,
        recompute_scope=scope_str,
        decision_outcome=proposal.decision_outcome.value,
        turnover=proposal.turnover,
        estimated_cost=proposal.estimated_cost,
        expected_improvement=proposal.expected_improvement,
        trades=trade_views,
        unachieved_targets=proposal.unachieved_targets,
        explainability_summary=proposal.explainability_summary,
    )
    return success(result.model_dump(mode="json"), request_id=_request_id(request))


@router.get(
    "/portfolios/{portfolio_id}/rebalances",
    operation_id="listRebalances",
    response_model=TypedEnvelope[list[dict[str, Any]]],
)
def list_rebalances(
    portfolio_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    events = _HISTORICAL_REBALANCES.get(portfolio_id, [])
    return success(events, request_id=_request_id(request))


@router.get(
    "/rebalances/{rebalance_id}/trades",
    operation_id="getRebalanceTrades",
    response_model=TypedEnvelope[list[dict[str, Any]]],
)
def get_rebalance_trades(
    rebalance_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    trades = _REBALANCE_TRADES.get(rebalance_id)
    if trades is None:
        raise NotFoundError("rebalance", rebalance_id)
    return success(trades, request_id=_request_id(request))
