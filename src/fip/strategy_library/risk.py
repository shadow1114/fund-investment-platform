from collections.abc import Sequence
from math import sqrt
from statistics import stdev

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)


def volatility(
    values: Sequence[ReturnObservation],
    annualization: int,
    *,
    minimum_observations: int = 2,
) -> FactorResult:
    if len(values) < max(2, minimum_observations):
        return unavailable("F-RISK-001", "INSUFFICIENT_OBSERVATIONS", len(values))
    return FactorResult(
        "F-RISK-001",
        stdev(x.value for x in values) * sqrt(annualization),
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )


def downside_volatility(
    values: Sequence[ReturnObservation],
    annualization: int,
    mar: float | None,
    *,
    minimum_observations: int = 2,
) -> FactorResult:
    if mar is None:
        return unavailable("F-RISK-002", "MAR_UNAVAILABLE", len(values))
    downside = [min(0.0, x.value - mar) for x in values]
    if len(downside) < max(2, minimum_observations):
        return unavailable("F-RISK-002", "INSUFFICIENT_OBSERVATIONS", len(values))
    return FactorResult(
        "F-RISK-002",
        stdev(downside) * sqrt(annualization),
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )


def maximum_drawdown(
    values: Sequence[ReturnObservation], *, minimum_observations: int = 1
) -> FactorResult:
    if len(values) < minimum_observations:
        return unavailable("F-RISK-003", "INSUFFICIENT_OBSERVATIONS", len(values))
    wealth = peak = 1.0
    drawdown = 0.0
    for point in values:
        wealth *= 1 + point.value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1)
    return FactorResult("F-RISK-003", drawdown, FactorStatus.AVAILABLE, None, len(values))
