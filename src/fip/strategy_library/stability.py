from collections.abc import Sequence

from fip.strategy_library.factor_types import FactorResult, ReturnObservation, unavailable
from fip.strategy_library.risk_adjusted import sharpe


def positive_return_ratio(values: Sequence[ReturnObservation]) -> FactorResult:
    if not values:
        return unavailable("F-STAB-001", "NO_OBSERVATIONS")
    return FactorResult(
        "F-STAB-001", sum(x.value > 0 for x in values) / len(values), "AVAILABLE", None, len(values)
    )


def rolling_sharpe(
    values: Sequence[ReturnObservation], annualization: int, window: int, minimum_valid_points: int
) -> FactorResult:
    if len(values) < window:
        return unavailable("F-STAB-005", "INSUFFICIENT_OBSERVATIONS", len(values))
    results = [
        sharpe(values[index - window : index], annualization).value
        for index in range(window, len(values) + 1)
    ]
    usable = [value for value in results if value is not None]
    if len(usable) < minimum_valid_points:
        return unavailable("F-STAB-005", "INSUFFICIENT_VALID_WINDOWS", len(values))
    return FactorResult("F-STAB-005", sum(usable) / len(usable), "AVAILABLE", None, len(values))
