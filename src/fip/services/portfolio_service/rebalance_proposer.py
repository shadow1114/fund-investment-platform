from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from fip.services.portfolio_service.live_portfolio import LivePortfolioSnapshot


class ProposalOutcome(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    SKIPPED_COST_BENEFIT = "SKIPPED_COST_BENEFIT"
    SKIPPED_FILTERED = "SKIPPED_FILTERED"
    SKIPPED_NO_DELTA = "SKIPPED_NO_DELTA"


@dataclass(frozen=True)
class ProposedTrade:
    fund_id: str
    direction: str  # BUY or SELL
    target_weight: float
    current_weight: float
    weight_delta: float
    target_shares: float
    delta_shares: float
    estimated_amount: float
    eligibility_status: str
    is_filtered: bool
    unachieved_reason: str | None = None


@dataclass(frozen=True)
class RebalanceProposal:
    decision_outcome: ProposalOutcome
    turnover: float
    estimated_cost: float
    expected_improvement: float
    trades: list[ProposedTrade]
    unachieved_targets: dict[str, str]
    explainability_summary: str


def generate_rebalance_proposal(
    snapshot: LivePortfolioSnapshot,
    target_weights: dict[str, float],
    prices: dict[str, Decimal],
    eligibility_map: dict[str, str] | None = None,
    fee_rate: float = 0.0015,
    min_trade_threshold: float = 0.005,
    expected_annualized_improvement: float = 0.0,
    holding_horizon_years: float = 0.25,
    cost_benefit_multiplier: float = 1.5,
) -> RebalanceProposal:
    """Generate trade recommendations with eligibility, min-trade threshold,
    and cost-benefit checks."""
    eligibility_map = eligibility_map or {}
    total_equity_float = float(snapshot.total_equity)

    all_funds = set(target_weights.keys()) | set(snapshot.actual_positions.keys())
    trades: list[ProposedTrade] = []
    unachieved: dict[str, str] = {}

    effective_weight_deltas: list[float] = []
    traded_volume = 0.0

    for fund_id in all_funds:
        target_w = target_weights.get(fund_id, 0.0)
        curr_pos = snapshot.actual_positions.get(fund_id)
        current_w = curr_pos.weight if curr_pos else 0.0
        delta_w = target_w - current_w

        if abs(delta_w) < 1e-7:
            continue

        direction = "BUY" if delta_w > 0 else "SELL"
        eligibility = eligibility_map.get(fund_id, "FULLY_ELIGIBLE")

        price = float(prices.get(fund_id, Decimal("1.0")))
        price = max(price, 0.0001)

        is_filtered = False
        unachieved_reason: str | None = None

        # 1. Eligibility restrictions
        if eligibility == "NOT_TRADABLE":
            is_filtered = True
            unachieved_reason = f"Fund {fund_id} is NOT_TRADABLE; trading is completely frozen."
            unachieved[fund_id] = unachieved_reason
        elif eligibility in ("HOLD_ONLY", "EXIT_ONLY") and direction == "BUY":
            is_filtered = True
            unachieved_reason = f"Fund {fund_id} is {eligibility}; cannot increase weight."
            unachieved[fund_id] = unachieved_reason

        # 2. Minimum trade threshold filtering (non-convex post-filtering)
        if not is_filtered and abs(delta_w) < min_trade_threshold:
            is_filtered = True
            unachieved_reason = (
                f"Trade delta ({abs(delta_w):.4f}) below threshold ({min_trade_threshold:.4f})."
            )

        if not is_filtered:
            effective_weight_deltas.append(abs(delta_w))
            traded_volume += abs(delta_w) * total_equity_float

        est_amount = abs(delta_w) * total_equity_float
        delta_shares = est_amount / price
        target_shares = (target_w * total_equity_float) / price

        trades.append(
            ProposedTrade(
                fund_id=fund_id,
                direction=direction,
                target_weight=target_w,
                current_weight=current_w,
                weight_delta=delta_w,
                target_shares=target_shares,
                delta_shares=delta_shares,
                estimated_amount=est_amount,
                eligibility_status=eligibility,
                is_filtered=is_filtered,
                unachieved_reason=unachieved_reason,
            )
        )

    # Single-sided turnover: 0.5 * sum(|effective_delta_w|)
    turnover = 0.5 * sum(effective_weight_deltas)
    estimated_cost = traded_volume * fee_rate

    # Cost-benefit comparison (Unified Annualized comparison)
    # Annualized cost = (one-off cost rate) / horizon
    one_off_cost_rate = (estimated_cost / total_equity_float) if total_equity_float > 0 else 0.0
    annualized_cost = one_off_cost_rate / max(holding_horizon_years, 0.01)
    required_improvement = annualized_cost * cost_benefit_multiplier

    cost_benefit_passed = expected_annualized_improvement >= required_improvement

    if turnover == 0.0:
        outcome = ProposalOutcome.SKIPPED_FILTERED if trades else ProposalOutcome.SKIPPED_NO_DELTA
    elif not cost_benefit_passed:
        outcome = ProposalOutcome.SKIPPED_COST_BENEFIT
    else:
        outcome = ProposalOutcome.RECOMMENDED

    explainability = (
        f"Rebalance Outcome: {outcome.value}. "
        f"Turnover: {turnover:.2%}. Estimated Cost: {estimated_cost:.2f}. "
        f"Annualized Expected Improvement: {expected_annualized_improvement:.2%} vs "
        f"Required: {required_improvement:.2%}. "
        f"Unachieved Targets: {len(unachieved)}."
    )

    return RebalanceProposal(
        decision_outcome=outcome,
        turnover=turnover,
        estimated_cost=estimated_cost,
        expected_improvement=expected_annualized_improvement,
        trades=trades,
        unachieved_targets=unachieved,
        explainability_summary=explainability,
    )
