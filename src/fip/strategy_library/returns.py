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


def period_return(
    values: Sequence[ReturnObservation], *, minimum_observations: int = 1
) -> FactorResult:
    result = cumulative_return(values, minimum_observations=minimum_observations)
    return FactorResult(
        "F-RET-003", result.value, result.status, result.reason, result.observations
    )


def rolling_return(
    values: Sequence[ReturnObservation],
    window: int,
    *,
    minimum_valid_points: int = 1,
    minimum_observations: int = 1,
) -> FactorResult:
    if window < 1:
        raise ValueError("rolling window must be positive")
    if len(values) < max(window, minimum_observations):
        return unavailable("F-RET-004", "INSUFFICIENT_OBSERVATIONS", len(values))
    points = tuple(
        (
            values[index].effective_at,
            cumulative_return(values[index - window + 1 : index + 1]).value,
        )
        for index in range(window - 1, len(values))
    )
    available = [value for _, value in points if value is not None]
    if len(available) < minimum_valid_points:
        return unavailable("F-RET-004", "INSUFFICIENT_VALID_WINDOWS", len(values))
    return FactorResult(
        "F-RET-004",
        sum(available) / len(available),
        FactorStatus.AVAILABLE,
        None,
        len(values),
        points,
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
