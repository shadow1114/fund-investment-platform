from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fip.services.portfolio_service.drift import DriftAnalysis
from fip.services.portfolio_service.live_portfolio import LivePortfolioSnapshot


class TriggerType(str, Enum):
    PERIODIC = "PERIODIC"
    DRIFT = "DRIFT"
    ELIGIBILITY_EVENT = "ELIGIBILITY_EVENT"
    CONSTRAINT_BREACH = "CONSTRAINT_BREACH"


class RecomputeScope(str, Enum):
    REOPTIMIZE_ONLY = "REOPTIMIZE_ONLY"
    ESTIMATION_AND_OPT = "ESTIMATION_AND_OPT"
    UNIVERSE_TO_OPT = "UNIVERSE_TO_OPT"
    FULL_PIPELINE = "FULL_PIPELINE"


# Scope ordering: higher number means deeper scope
SCOPE_DEPTH = {
    RecomputeScope.REOPTIMIZE_ONLY: 1,
    RecomputeScope.ESTIMATION_AND_OPT: 2,
    RecomputeScope.UNIVERSE_TO_OPT: 3,
    RecomputeScope.FULL_PIPELINE: 4,
}

TRIGGER_TO_SCOPE = {
    TriggerType.CONSTRAINT_BREACH: RecomputeScope.REOPTIMIZE_ONLY,
    TriggerType.DRIFT: RecomputeScope.ESTIMATION_AND_OPT,
    TriggerType.ELIGIBILITY_EVENT: RecomputeScope.UNIVERSE_TO_OPT,
    TriggerType.PERIODIC: RecomputeScope.FULL_PIPELINE,
}


class TriggerOutcome(str, Enum):
    TRIGGERED = "TRIGGERED"
    SKIPPED_NO_TRIGGER = "SKIPPED_NO_TRIGGER"
    SKIPPED_PENDING_EXISTS = "SKIPPED_PENDING_EXISTS"
    SKIPPED_COST_BENEFIT = "SKIPPED_COST_BENEFIT"


@dataclass(frozen=True)
class TriggerDecision:
    is_triggered: bool
    trigger_types: list[TriggerType]
    primary_trigger: TriggerType | None
    recompute_scope: RecomputeScope | None
    trigger_reasons: list[dict[str, Any]]
    decision_outcome: TriggerOutcome


class RebalanceTriggerEngine:
    def __init__(self, periodic_days: int = 63) -> None:
        self.periodic_days = periodic_days

    def evaluate(
        self,
        snapshot: LivePortfolioSnapshot,
        current_date: dt.date,
        drift_analysis: DriftAnalysis,
        eligibility_status: dict[str, str],
        constraint_violations: list[str],
    ) -> TriggerDecision:
        """Evaluate rebalancing triggers and merge multiple triggers using deepest scope."""
        # 1. Anti-duplicate / pending execution check
        if snapshot.has_pending_execution:
            return TriggerDecision(
                is_triggered=False,
                trigger_types=[],
                primary_trigger=None,
                recompute_scope=None,
                trigger_reasons=[
                    {
                        "trigger_type": "PENDING_CHECK",
                        "reason": "Pending execution exists; skipping to avoid duplicate orders.",
                    }
                ],
                decision_outcome=TriggerOutcome.SKIPPED_PENDING_EXISTS,
            )

        triggered_types: list[TriggerType] = []
        reasons: list[dict[str, Any]] = []

        # 2. Check Periodic trigger
        if snapshot.last_rebalanced_at is not None:
            last_date = snapshot.last_rebalanced_at.date()
            days_since = (current_date - last_date).days
            if days_since >= self.periodic_days:
                triggered_types.append(TriggerType.PERIODIC)
                reasons.append(
                    {
                        "trigger_type": TriggerType.PERIODIC.value,
                        "reason": f"Interval reached ({days_since} >= {self.periodic_days} days).",
                    }
                )
        else:
            # First rebalance if never rebalanced and holds assets
            if snapshot.actual_positions:
                triggered_types.append(TriggerType.PERIODIC)
                reasons.append(
                    {
                        "trigger_type": TriggerType.PERIODIC.value,
                        "reason": "Portfolio has not been rebalanced previously.",
                    }
                )

        # 3. Check Drift trigger
        if drift_analysis.is_drift_triggered:
            triggered_types.append(TriggerType.DRIFT)
            reasons.append(
                {
                    "trigger_type": TriggerType.DRIFT.value,
                    "max_fund_absolute_drift": drift_analysis.max_fund_absolute_drift,
                    "max_category_absolute_drift": drift_analysis.max_category_absolute_drift,
                    "reason": "Asset weight drift exceeded configured threshold.",
                }
            )

        # 4. Check Eligibility Event trigger
        ineligible_holdings = [
            f
            for f in snapshot.actual_positions
            if eligibility_status.get(f) in ("HOLD_ONLY", "EXIT_ONLY", "NOT_TRADABLE", "REJECTED")
        ]
        if ineligible_holdings:
            triggered_types.append(TriggerType.ELIGIBILITY_EVENT)
            reasons.append(
                {
                    "trigger_type": TriggerType.ELIGIBILITY_EVENT.value,
                    "ineligible_funds": ineligible_holdings,
                    "reason": f"Funds {ineligible_holdings} lost full investment eligibility.",
                }
            )

        # 5. Check Constraint Breach trigger
        if constraint_violations:
            triggered_types.append(TriggerType.CONSTRAINT_BREACH)
            reasons.append(
                {
                    "trigger_type": TriggerType.CONSTRAINT_BREACH.value,
                    "violations": constraint_violations,
                    "reason": f"Portfolio breached constraints: {constraint_violations}.",
                }
            )

        if not triggered_types:
            return TriggerDecision(
                is_triggered=False,
                trigger_types=[],
                primary_trigger=None,
                recompute_scope=None,
                trigger_reasons=[
                    {"reason": "All checks within tolerances; no rebalance required."}
                ],
                decision_outcome=TriggerOutcome.SKIPPED_NO_TRIGGER,
            )

        # 6. Deepest scope merge
        # Priority order: CONSTRAINT_BREACH (1) < DRIFT (2) < ELIGIBILITY_EVENT (3) < PERIODIC (4)
        deepest_scope = max(
            (TRIGGER_TO_SCOPE[t] for t in triggered_types),
            key=lambda s: SCOPE_DEPTH[s],
        )

        # Primary trigger is the one corresponding to the deepest scope
        primary_t = next(t for t in triggered_types if TRIGGER_TO_SCOPE[t] == deepest_scope)

        return TriggerDecision(
            is_triggered=True,
            trigger_types=triggered_types,
            primary_trigger=primary_t,
            recompute_scope=deepest_scope,
            trigger_reasons=reasons,
            decision_outcome=TriggerOutcome.TRIGGERED,
        )
