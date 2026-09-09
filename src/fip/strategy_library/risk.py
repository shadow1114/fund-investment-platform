from collections.abc import Sequence
from math import sqrt
from statistics import stdev

from fip.strategy_library.factor_types import FactorResult, ReturnObservation, unavailable


def volatility(values: Sequence[ReturnObservation], annualization: int) -> FactorResult:
    if len(values) < 2:
        return unavailable("F-RISK-001", "INSUFFICIENT_OBSERVATIONS", len(values))
    return FactorResult(
        "F-RISK-001",
        stdev(x.value for x in values) * sqrt(annualization),
        "AVAILABLE",
        None,
        len(values),
    )


def downside_volatility(
    values: Sequence[ReturnObservation], annualization: int, mar: float = 0.0
) -> FactorResult:
    downside = [min(0.0, x.value - mar) for x in values]
    if len(downside) < 2:
        return unavailable("F-RISK-002", "INSUFFICIENT_OBSERVATIONS", len(values))
    return FactorResult(
        "F-RISK-002", stdev(downside) * sqrt(annualization), "AVAILABLE", None, len(values)
    )


def maximum_drawdown(values: Sequence[ReturnObservation]) -> FactorResult:
    if not values:
        return unavailable("F-RISK-003", "NO_OBSERVATIONS")
    wealth = peak = 1.0
    drawdown = 0.0
    for point in values:
        wealth *= 1 + point.value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1)
    return FactorResult("F-RISK-003", drawdown, "AVAILABLE", None, len(values))
