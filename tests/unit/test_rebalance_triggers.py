from __future__ import annotations

import datetime as dt
from decimal import Decimal

from fip.services.portfolio_service.drift import calculate_portfolio_drift
from fip.services.portfolio_service.live_portfolio import (
    LivePortfolioSnapshot,
    LivePortfolioStatus,
    PortfolioState,
    Position,
)
from fip.services.portfolio_service.rebalance_trigger import (
    RebalanceTriggerEngine,
    RecomputeScope,
    TriggerDecision,
    TriggerOutcome,
    TriggerType,
)


def create_base_snapshot(
    has_pending: bool = False,
    last_rebalanced_at: dt.datetime | None = None,
) -> LivePortfolioSnapshot:
    as_of = dt.date(2026, 1, 10)
    pos = {
        "000001": Position(
            fund_id="000001",
            state=PortfolioState.ACTUAL,
            shares=Decimal("1000"),
            cost_basis=Decimal("1000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("1000"),
            weight=0.5,
            holding_days=10,
            as_of_date=as_of,
        ),
        "000002": Position(
            fund_id="000002",
            state=PortfolioState.ACTUAL,
            shares=Decimal("1000"),
            cost_basis=Decimal("1000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("1000"),
            weight=0.5,
            holding_days=10,
            as_of_date=as_of,
        ),
    }
    return LivePortfolioSnapshot(
        portfolio_id="P-001",
        as_of_date=as_of,
        status=LivePortfolioStatus.ACTIVE,
        cash_balance=Decimal(0),
        total_equity=Decimal("2000.00"),
        has_pending_execution=has_pending,
        target_positions=dict(pos),
        pending_positions={},
        actual_positions=dict(pos),
        last_rebalanced_at=last_rebalanced_at,
    )


def test_no_trigger_when_within_tolerances() -> None:
    engine = RebalanceTriggerEngine(periodic_days=63)
    snapshot = create_base_snapshot(
        last_rebalanced_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    )
    drift = calculate_portfolio_drift(snapshot, fund_drift_threshold=0.05)

    decision: TriggerDecision = engine.evaluate(
        snapshot=snapshot,
        current_date=dt.date(2026, 1, 10),
        drift_analysis=drift,
        eligibility_status={"000001": "FULLY_ELIGIBLE", "000002": "FULLY_ELIGIBLE"},
        constraint_violations=[],
    )

    assert decision.is_triggered is False
    assert decision.decision_outcome == TriggerOutcome.SKIPPED_NO_TRIGGER


def test_skip_when_pending_execution_exists() -> None:
    engine = RebalanceTriggerEngine(periodic_days=63)
    snapshot = create_base_snapshot(
        has_pending=True,
        last_rebalanced_at=dt.datetime(2025, 9, 1, tzinfo=dt.UTC),  # > 63 days
    )
    drift = calculate_portfolio_drift(snapshot)

    decision = engine.evaluate(
        snapshot=snapshot,
        current_date=dt.date(2026, 1, 10),
        drift_analysis=drift,
        eligibility_status={"000001": "FULLY_ELIGIBLE", "000002": "FULLY_ELIGIBLE"},
        constraint_violations=[],
    )

    # Even though periodic trigger is overdue, pending execution blocks rebalance
    assert decision.is_triggered is False
    assert decision.decision_outcome == TriggerOutcome.SKIPPED_PENDING_EXISTS


def test_multi_trigger_merges_to_deepest_scope() -> None:
    engine = RebalanceTriggerEngine(periodic_days=63)
    # Both Drift triggered and Eligibility Event triggered!
    snapshot = create_base_snapshot(
        last_rebalanced_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    )
    # Simulate drift
    drift = calculate_portfolio_drift(snapshot, fund_drift_threshold=0.01)
    # Fund 000002 becomes HOLD_ONLY
    eligibility = {"000001": "FULLY_ELIGIBLE", "000002": "HOLD_ONLY"}

    decision = engine.evaluate(
        snapshot=snapshot,
        current_date=dt.date(2026, 1, 10),
        drift_analysis=drift,
        eligibility_status=eligibility,
        constraint_violations=["FUND_MAX_WEIGHT_EXCEEDED"],
    )

    # Constraint Breach (REOPTIMIZE_ONLY) + Eligibility Event (UNIVERSE_TO_OPT)
    # Deepest scope should be UNIVERSE_TO_OPT
    assert decision.is_triggered is True
    assert set(decision.trigger_types) >= {
        TriggerType.ELIGIBILITY_EVENT,
        TriggerType.CONSTRAINT_BREACH,
    }
    assert decision.recompute_scope == RecomputeScope.UNIVERSE_TO_OPT
    # All reasons must be preserved
    reasons = [r["trigger_type"] for r in decision.trigger_reasons]
    assert "ELIGIBILITY_EVENT" in reasons
    assert "CONSTRAINT_BREACH" in reasons


def test_periodic_trigger_selects_full_pipeline() -> None:
    engine = RebalanceTriggerEngine(periodic_days=60)
    # 90 days elapsed since last rebalance
    snapshot = create_base_snapshot(
        last_rebalanced_at=dt.datetime(2025, 10, 1, tzinfo=dt.UTC)
    )
    drift = calculate_portfolio_drift(snapshot, fund_drift_threshold=0.10)

    decision = engine.evaluate(
        snapshot=snapshot,
        current_date=dt.date(2026, 1, 10),
        drift_analysis=drift,
        eligibility_status={"000001": "FULLY_ELIGIBLE", "000002": "FULLY_ELIGIBLE"},
        constraint_violations=[],
    )

    assert decision.is_triggered is True
    assert decision.primary_trigger == TriggerType.PERIODIC
    assert decision.recompute_scope == RecomputeScope.FULL_PIPELINE
