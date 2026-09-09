from collections.abc import Sequence
from math import prod

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)


def cumulative_return(
    values: Sequence[ReturnObservation], *, minimum_observations: int = 1
) -> FactorResult:
    if len(values) < minimum_observations:
        return unavailable("F-RET-002", "INSUFFICIENT_OBSERVATIONS", len(values))
    return FactorResult(
        "F-RET-002",
        prod(1 + point.value for point in values) - 1,
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )


def annualized_return(
    values: Sequence[ReturnObservation],
    annualization: int,
    *,
    minimum_observations: int = 1,
) -> FactorResult:
    if len(values) < minimum_observations:
        return unavailable("F-RET-001", "INSUFFICIENT_OBSERVATIONS", len(values))
    cumulative = prod(1 + point.value for point in values)
    if cumulative <= 0:
        return unavailable("F-RET-001", "NON_POSITIVE_COMPOUND_RETURN", len(values))
    return FactorResult(
        "F-RET-001",
        cumulative ** (annualization / len(values)) - 1,
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )
