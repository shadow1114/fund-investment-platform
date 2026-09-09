from collections.abc import Sequence

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
    results = [
        sharpe(values[index - window : index], annualization, risk_free).value
        for index in range(window, len(values) + 1)
    ]
    usable = [value for value in results if value is not None]
    if len(usable) < minimum_valid_points:
        return unavailable("F-STAB-005", "INSUFFICIENT_VALID_WINDOWS", len(values))
    return FactorResult(
        "F-STAB-005",
        sum(usable) / len(usable),
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )
