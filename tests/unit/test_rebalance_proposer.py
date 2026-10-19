from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from fip.services.portfolio_service.live_portfolio import (
    LivePortfolioSnapshot,
    LivePortfolioStatus,
    PortfolioState,
    Position,
)
from fip.services.portfolio_service.rebalance_proposer import (
    ProposalOutcome,
    RebalanceProposal,
    generate_rebalance_proposal,
)


def create_proposer_snapshot() -> LivePortfolioSnapshot:
    as_of = dt.date(2026, 1, 10)
    # Total equity = 100,000
    # Actual positions:
    # 000001: 60,000 (60%)
    # 000002: 40,000 (40%)
    actuals = {
        "000001": Position(
            fund_id="000001",
            state=PortfolioState.ACTUAL,
            shares=Decimal("60000"),
            cost_basis=Decimal("60000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("60000"),
            weight=0.60,
            holding_days=10,
            as_of_date=as_of,
        ),
        "000002": Position(
            fund_id="000002",
            state=PortfolioState.ACTUAL,
            shares=Decimal("40000"),
            cost_basis=Decimal("40000"),
            market_price=Decimal("1.0"),
            market_value=Decimal("40000"),
            weight=0.40,
            holding_days=10,
            as_of_date=as_of,
        ),
    }
    return LivePortfolioSnapshot(
        portfolio_id="P-001",
        as_of_date=as_of,
        status=LivePortfolioStatus.ACTIVE,
        cash_balance=Decimal("0.00"),
        total_equity=Decimal("100000.00"),
        has_pending_execution=False,
        target_positions={},
        pending_positions={},
        actual_positions=actuals,
    )


def test_generate_proposal_with_turnover_and_trades() -> None:
    snapshot = create_proposer_snapshot()
    # Rebalance target: 50% / 50%
    target_weights = {"000001": 0.50, "000002": 0.50}
    prices = {"000001": Decimal("1.0"), "000002": Decimal("1.0")}
    eligibility = {"000001": "FULLY_ELIGIBLE", "000002": "FULLY_ELIGIBLE"}

    proposal: RebalanceProposal = generate_rebalance_proposal(
        snapshot=snapshot,
        target_weights=target_weights,
        prices=prices,
        eligibility_map=eligibility,
        fee_rate=0.0015,
        min_trade_threshold=0.01,
        expected_annualized_improvement=0.02,  # 2% improvement
        holding_horizon_years=0.25,  # 1 quarter
    )

    assert proposal.decision_outcome == ProposalOutcome.RECOMMENDED
    # 000001: 60% -> 50% = sell 10% (10,000)
    # 000002: 40% -> 50% = buy 10% (10,000)
    # Turnover = 0.5 * (0.10 + 0.10) = 10%
    assert proposal.turnover == pytest.approx(0.10)
    assert len(proposal.trades) == 2

    sell_trade = next(t for t in proposal.trades if t.fund_id == "000001")
    assert sell_trade.direction == "SELL"
    assert sell_trade.delta_shares == pytest.approx(10000.0)
    assert sell_trade.estimated_amount == pytest.approx(10000.0)

    buy_trade = next(t for t in proposal.trades if t.fund_id == "000002")
    assert buy_trade.direction == "BUY"
    assert buy_trade.delta_shares == pytest.approx(10000.0)
    assert buy_trade.estimated_amount == pytest.approx(10000.0)


def test_min_trade_threshold_filters_small_trades() -> None:
    snapshot = create_proposer_snapshot()
    # 000001: 59.8% -> delta = -0.2% (< 1% min trade threshold)
    target_weights = {"000001": 0.598, "000002": 0.402}
    prices = {"000001": Decimal("1.0"), "000002": Decimal("1.0")}
    eligibility = {"000001": "FULLY_ELIGIBLE", "000002": "FULLY_ELIGIBLE"}

    proposal = generate_rebalance_proposal(
        snapshot=snapshot,
        target_weights=target_weights,
        prices=prices,
        eligibility_map=eligibility,
        min_trade_threshold=0.01,  # 1%
        expected_annualized_improvement=0.05,
    )

    # All adjustments are 0.2% < 1%, so filtered out
    assert proposal.turnover == 0.0
    assert all(t.is_filtered for t in proposal.trades)


def test_hold_only_blocks_buying_and_records_unachieved() -> None:
    snapshot = create_proposer_snapshot()
    # 000002 wants to buy 10% (from 40% to 50%), but is HOLD_ONLY
    target_weights = {"000001": 0.50, "000002": 0.50}
    prices = {"000001": Decimal("1.0"), "000002": Decimal("1.0")}
    eligibility = {"000001": "FULLY_ELIGIBLE", "000002": "HOLD_ONLY"}

    proposal = generate_rebalance_proposal(
        snapshot=snapshot,
        target_weights=target_weights,
        prices=prices,
        eligibility_map=eligibility,
        expected_annualized_improvement=0.05,
    )

    # 000002 buy must be blocked
    buy_trade = next(t for t in proposal.trades if t.fund_id == "000002")
    assert buy_trade.is_filtered is True
    assert "HOLD_ONLY" in (buy_trade.unachieved_reason or "")
    assert "000002" in proposal.unachieved_targets


def test_cost_benefit_gate_skips_unprofitable_rebalance() -> None:
    snapshot = create_proposer_snapshot()
    target_weights = {"000001": 0.50, "000002": 0.50}
    prices = {"000001": Decimal("1.0"), "000002": Decimal("1.0")}
    eligibility = {"000001": "FULLY_ELIGIBLE", "000002": "FULLY_ELIGIBLE"}

    # Very small expected improvement (0.0001) vs transaction fee
    proposal = generate_rebalance_proposal(
        snapshot=snapshot,
        target_weights=target_weights,
        prices=prices,
        eligibility_map=eligibility,
        fee_rate=0.005,  # 0.5% fee
        expected_annualized_improvement=0.0001,
        holding_horizon_years=0.25,
        cost_benefit_multiplier=2.0,
    )

    assert proposal.decision_outcome == ProposalOutcome.SKIPPED_COST_BENEFIT
