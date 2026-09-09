from collections.abc import Sequence
from math import prod

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)


def cumulative_return(values: Sequence[ReturnObservation]) -> FactorResult:
    if not values:
        return unavailable("F-RET-002", "NO_OBSERVATIONS")
    return FactorResult(
        "F-RET-002",
        prod(1 + point.value for point in values) - 1,
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )


def annualized_return(values: Sequence[ReturnObservation], annualization: int) -> FactorResult:
    if not values:
        return unavailable("F-RET-001", "NO_OBSERVATIONS")
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
