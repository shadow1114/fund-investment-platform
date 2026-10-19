from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from fip.services.portfolio_service.drift import (
    DriftAnalysis,
    calculate_portfolio_drift,
    mark_to_market_portfolio,
)
from fip.services.portfolio_service.live_portfolio import (
    LivePortfolioSnapshot,
    LivePortfolioStatus,
    PortfolioState,
    Position,
)


def create_test_snapshot() -> LivePortfolioSnapshot:
    as_of = dt.date(2026, 1, 10)
    # Target: 000001: 50%, 000002: 50%
    target_pos = {
        "000001": Position(
            fund_id="000001",
            state=PortfolioState.TARGET,
            shares=Decimal("5000"),
            cost_basis=Decimal("5000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("5000"),
            weight=0.5,
            holding_days=0,
            as_of_date=as_of,
        ),
        "000002": Position(
            fund_id="000002",
            state=PortfolioState.TARGET,
            shares=Decimal("5000"),
            cost_basis=Decimal("5000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("5000"),
            weight=0.5,
            holding_days=0,
            as_of_date=as_of,
        ),
    }
    # Actual: initially 5000 shares each
    actual_pos = {
        "000001": Position(
            fund_id="000001",
            state=PortfolioState.ACTUAL,
            shares=Decimal("5000"),
            cost_basis=Decimal("5000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("5000"),
            weight=0.5,
            holding_days=1,
            as_of_date=as_of,
        ),
        "000002": Position(
            fund_id="000002",
            state=PortfolioState.ACTUAL,
            shares=Decimal("5000"),
            cost_basis=Decimal("5000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("5000"),
            weight=0.5,
            holding_days=1,
            as_of_date=as_of,
        ),
    }
    return LivePortfolioSnapshot(
        portfolio_id="P-001",
        as_of_date=as_of,
        status=LivePortfolioStatus.ACTIVE,
        cash_balance=Decimal("0.00"),
        total_equity=Decimal("10000.00"),
        has_pending_execution=False,
        target_positions=target_pos,
        pending_positions={},
        actual_positions=actual_pos,
    )


def test_mark_to_market_reweights_actual_positions() -> None:
    snapshot = create_test_snapshot()
    # Prices change: 000001 increases to 1.20, 000002 drops to 0.80
    new_prices = {"000001": Decimal("1.20"), "000002": Decimal("0.80")}
    new_date = dt.date(2026, 1, 11)

    updated = mark_to_market_portfolio(snapshot, new_prices, new_date)

    # 000001 MV = 5000 * 1.2 = 6000
    # 000002 MV = 5000 * 0.8 = 4000
    # Total = 10000
    assert updated.total_equity == Decimal("10000.00")
    assert updated.actual_positions["000001"].market_value == Decimal("6000.00")
    assert updated.actual_positions["000001"].weight == 0.60
    assert updated.actual_positions["000002"].market_value == Decimal("4000.00")
    assert updated.actual_positions["000002"].weight == 0.40
    assert updated.actual_positions["000001"].holding_days == 2


def test_calculate_portfolio_drift() -> None:
    snapshot = create_test_snapshot()
    new_prices = {"000001": Decimal("1.20"), "000002": Decimal("0.80")}
    updated = mark_to_market_portfolio(snapshot, new_prices, dt.date(2026, 1, 11))

    # Category map: 000001 -> EQUITY, 000002 -> BOND
    category_map = {"000001": "EQUITY", "000002": "BOND"}

    analysis: DriftAnalysis = calculate_portfolio_drift(
        updated,
        category_map=category_map,
        fund_drift_threshold=0.05,
        category_drift_threshold=0.08,
    )

    # Fund drift:
    # 000001: actual 0.60 - target 0.50 = +0.10
    # 000002: actual 0.40 - target 0.50 = -0.10
    assert analysis.fund_signed_drift["000001"] == pytest.approx(0.10)
    assert analysis.fund_signed_drift["000002"] == pytest.approx(-0.10)
    assert analysis.fund_absolute_drift["000001"] == pytest.approx(0.10)
    assert analysis.fund_absolute_drift["000002"] == pytest.approx(0.10)
    assert analysis.max_fund_absolute_drift == pytest.approx(0.10)

    # Threshold 0.05 exceeded by 0.10
    assert analysis.is_fund_drift_exceeded is True
    # Category drift: Equity drift +0.10 > 0.08
    assert analysis.category_absolute_drift["EQUITY"] == pytest.approx(0.10)
    assert analysis.is_category_drift_exceeded is True
    assert analysis.is_drift_triggered is True
