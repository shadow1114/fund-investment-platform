from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from fip.services.portfolio_service.live_portfolio import (
    ExecutionReport,
    ExecutionStatus,
    LivePortfolioStatus,
    PendingExecutionConflictError,
    PortfolioState,
    TradeRecommendation,
    deliver_rebalancing_recommendation,
    initialize_live_portfolio,
    process_execution_report,
)


def test_initialize_live_portfolio_sets_target_and_cash() -> None:
    target_weights = {"000001": 0.6, "000002": 0.4}
    prices = {"000001": Decimal("1.5000"), "000002": Decimal("2.0000")}
    as_of = dt.date(2026, 1, 10)

    snapshot = initialize_live_portfolio(
        portfolio_id="P-001",
        target_weights=target_weights,
        total_capital=Decimal("100000.00"),
        prices=prices,
        as_of_date=as_of,
    )

    assert snapshot.portfolio_id == "P-001"
    assert snapshot.cash_balance == Decimal("100000.00")
    assert snapshot.total_equity == Decimal("100000.00")
    assert snapshot.has_pending_execution is False
    assert snapshot.status == LivePortfolioStatus.ACTIVE

    # Target positions populated
    assert set(snapshot.target_positions.keys()) == {"000001", "000002"}
    assert snapshot.target_positions["000001"].weight == 0.6
    assert snapshot.target_positions["000001"].state == PortfolioState.TARGET
    # Actual positions should be empty initially (Never fake Actual with Target)
    assert len(snapshot.actual_positions) == 0


def test_deliver_recommendation_creates_pending_execution() -> None:
    snapshot = initialize_live_portfolio(
        portfolio_id="P-001",
        target_weights={"000001": 1.0},
        total_capital=Decimal("10000.00"),
        prices={"000001": Decimal("1.0000")},
        as_of_date=dt.date(2026, 1, 10),
    )

    trade = TradeRecommendation(
        fund_id="000001",
        direction="BUY",
        shares=Decimal("10000.00"),
        target_weight=1.0,
        estimated_price=Decimal("1.0000"),
    )

    delivered = deliver_rebalancing_recommendation(
        snapshot, [trade], delivery_time=dt.datetime(2026, 1, 10, 10, 0, tzinfo=dt.UTC)
    )

    assert delivered.has_pending_execution is True
    assert "000001" in delivered.pending_positions
    assert delivered.pending_positions["000001"].shares == Decimal("10000.00")

    # Repeat delivery while pending should fail closed
    with pytest.raises(PendingExecutionConflictError):
        deliver_rebalancing_recommendation(
            delivered, [trade], delivery_time=dt.datetime(2026, 1, 10, 10, 5, tzinfo=dt.UTC)
        )


def test_process_execution_report_updates_actual_and_clears_pending() -> None:
    snapshot = initialize_live_portfolio(
        portfolio_id="P-001",
        target_weights={"000001": 1.0},
        total_capital=Decimal("10000.00"),
        prices={"000001": Decimal("1.0000")},
        as_of_date=dt.date(2026, 1, 10),
    )

    trade = TradeRecommendation(
        fund_id="000001",
        direction="BUY",
        shares=Decimal("10000.00"),
        target_weight=1.0,
        estimated_price=Decimal("1.0000"),
    )
    pending_snap = deliver_rebalancing_recommendation(
        snapshot, [trade], delivery_time=dt.datetime(2026, 1, 10, 10, 0, tzinfo=dt.UTC)
    )

    # Process partial fill
    partial_report = ExecutionReport(
        report_id="R-01",
        live_portfolio_id="P-001",
        rebalance_id=None,
        fund_id="000001",
        direction="BUY",
        requested_shares=Decimal("10000.00"),
        filled_shares=Decimal("6000.00"),
        filled_price=Decimal("1.0000"),
        fee=Decimal("10.00"),
        status=ExecutionStatus.PARTIALLY_FILLED,
        reported_at=dt.datetime(2026, 1, 10, 10, 30, tzinfo=dt.UTC),
    )

    after_partial = process_execution_report(pending_snap, partial_report)
    assert after_partial.has_pending_execution is True
    assert after_partial.pending_positions["000001"].shares == Decimal("4000.00")
    assert after_partial.actual_positions["000001"].shares == Decimal("6000.00")
    assert after_partial.cash_balance == Decimal("10000.00") - Decimal("6010.00")

    # Process remaining fill
    full_report = ExecutionReport(
        report_id="R-02",
        live_portfolio_id="P-001",
        rebalance_id=None,
        fund_id="000001",
        direction="BUY",
        requested_shares=Decimal("4000.00"),
        filled_shares=Decimal("4000.00"),
        filled_price=Decimal("1.0000"),
        fee=Decimal("5.00"),
        status=ExecutionStatus.FILLED,
        reported_at=dt.datetime(2026, 1, 10, 11, 0, tzinfo=dt.UTC),
    )

    after_full = process_execution_report(after_partial, full_report)
    assert after_full.has_pending_execution is False
    assert "000001" not in after_full.pending_positions
    assert after_full.actual_positions["000001"].shares == Decimal("10000.00")
    assert after_full.cash_balance == Decimal("10000.00") - Decimal("6010.00") - Decimal("4005.00")
