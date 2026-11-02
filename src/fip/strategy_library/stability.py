from collections.abc import Sequence
from math import sqrt
from statistics import mean, pstdev, stdev

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)
from fip.strategy_library.risk_adjusted import sharpe


def positive_return_ratio(
    values: Sequence[ReturnObservation], *, minimum_observations: int = 1
) -> FactorResult:
    if len(values) < minimum_observations:
        return unavailable("F-STAB-001", "INSUFFICIENT_OBSERVATIONS", len(values))
    return FactorResult(
        "F-STAB-001",
        sum(x.value > 0 for x in values) / len(values),
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )


def rolling_sharpe(
    values: Sequence[ReturnObservation],
    annualization: int,
    risk_free: float | None,
    window: int,
    minimum_valid_points: int,
    *,
    minimum_observations: int = 1,
) -> FactorResult:
    if risk_free is None:
        return unavailable("F-STAB-005", "RISK_FREE_UNAVAILABLE", len(values))
    if len(values) < max(window, minimum_observations):
        return unavailable("F-STAB-005", "INSUFFICIENT_OBSERVATIONS", len(values))
    points = tuple(
        (
            values[index - 1].effective_at,
            sharpe(values[index - window : index], annualization, risk_free).value,
        )
        for index in range(window, len(values) + 1)
    )
    usable = [value for _, value in points if value is not None]
    if len(usable) < minimum_valid_points:
        return FactorResult(
            "F-STAB-005",
            None,
            FactorStatus.UNAVAILABLE,
            "INSUFFICIENT_VALID_WINDOWS",
            len(values),
            points,
        )
    return FactorResult(
        "F-STAB-005",
        sum(usable) / len(usable),
        FactorStatus.AVAILABLE,
        None,
        len(values),
        points,
    )


def rolling_volatility(
    values: Sequence[ReturnObservation], annualization: int, window: int
) -> FactorResult:
    if window < 2:
        raise ValueError("rolling window must contain at least two observations")
    if len(values) < window:
        return unavailable("F-STAB-006", "INSUFFICIENT_OBSERVATIONS", len(values))
    points = tuple(
        (
            values[index - 1].effective_at,
            stdev(item.value for item in values[index - window : index]) * sqrt(annualization),
        )
        for index in range(window, len(values) + 1)
    )
    usable = [value for _, value in points]
    if len(usable) < 12:
        return FactorResult(
            "F-STAB-006",
            None,
            FactorStatus.UNAVAILABLE,
            "INSUFFICIENT_VALID_WINDOWS",
            len(values),
            points,
        )
    return FactorResult(
        "F-STAB-006", mean(usable), FactorStatus.AVAILABLE, None, len(values), points
    )


def rolling_maximum_drawdown(values: Sequence[ReturnObservation], window: int) -> FactorResult:
    if window < 1:
        raise ValueError("rolling window must be positive")
    if len(values) < window:
        return unavailable("F-STAB-007", "INSUFFICIENT_OBSERVATIONS", len(values))
    from fip.strategy_library.risk import maximum_drawdown

    points = tuple(
        (
            values[index - 1].effective_at,
            maximum_drawdown(values[index - window : index]).value,
        )
        for index in range(window, len(values) + 1)
    )
    usable = [value for _, value in points if value is not None]
    if len(usable) < 12:
        return FactorResult(
            "F-STAB-007",
            None,
            FactorStatus.UNAVAILABLE,
            "INSUFFICIENT_VALID_WINDOWS",
            len(values),
            points,
        )
    return FactorResult(
        "F-STAB-007",
        mean(usable) if usable else None,
        FactorStatus.AVAILABLE if usable else FactorStatus.UNAVAILABLE,
        None if usable else "INSUFFICIENT_VALID_WINDOWS",
        len(values),
        points,
    )


def skewness(values: Sequence[ReturnObservation], minimum_observations: int = 120) -> FactorResult:
    rates = [item.value for item in values]
    if len(rates) < minimum_observations:
        return unavailable("F-STAB-003", "INSUFFICIENT_OBSERVATIONS", len(rates))
    sigma = pstdev(rates)
    if sigma == 0:
        return unavailable("F-STAB-003", "ZERO_VARIANCE", len(rates))
    center = mean(rates)
    value = sum((rate - center) ** 3 for rate in rates) / (len(rates) * sigma**3)
    return FactorResult("F-STAB-003", value, FactorStatus.AVAILABLE, None, len(rates))


def kurtosis(values: Sequence[ReturnObservation], minimum_observations: int = 120) -> FactorResult:
    rates = [item.value for item in values]
    if len(rates) < minimum_observations:
        return unavailable("F-STAB-004", "INSUFFICIENT_OBSERVATIONS", len(rates))
    sigma = pstdev(rates)
    if sigma == 0:
        return unavailable("F-STAB-004", "ZERO_VARIANCE", len(rates))
    center = mean(rates)
    value = sum((rate - center) ** 4 for rate in rates) / (len(rates) * sigma**4) - 3
    return FactorResult("F-STAB-004", value, FactorStatus.AVAILABLE, None, len(rates))
