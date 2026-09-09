from collections.abc import Sequence

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)
from fip.strategy_library.returns import annualized_return
from fip.strategy_library.risk import downside_volatility, maximum_drawdown, volatility


def sharpe(
    values: Sequence[ReturnObservation],
    annualization: int,
    risk_free: float | None,
    *,
    minimum_observations: int = 2,
) -> FactorResult:
    if risk_free is None:
        return unavailable("F-RAP-001", "RISK_FREE_UNAVAILABLE", len(values))
    vol = volatility(values, annualization, minimum_observations=minimum_observations)
    ret = annualized_return(values, annualization, minimum_observations=minimum_observations)
    if vol.reason == "INSUFFICIENT_OBSERVATIONS" or ret.reason == "INSUFFICIENT_OBSERVATIONS":
        return unavailable("F-RAP-001", "INSUFFICIENT_OBSERVATIONS", len(values))
    if vol.value in (None, 0.0) or ret.value is None:
        return unavailable("F-RAP-001", "ZERO_DENOMINATOR", len(values))
    assert vol.value is not None
    return FactorResult(
        "F-RAP-001", (ret.value - risk_free) / vol.value, FactorStatus.AVAILABLE, None, len(values)
    )


def sortino(
    values: Sequence[ReturnObservation],
    annualization: int,
    mar: float | None,
    *,
    minimum_observations: int = 2,
) -> FactorResult:
    if mar is None:
        return unavailable("F-RAP-002", "MAR_UNAVAILABLE", len(values))
    downside = downside_volatility(
        values, annualization, mar, minimum_observations=minimum_observations
    )
    ret = annualized_return(values, annualization, minimum_observations=minimum_observations)
    if downside.reason == "INSUFFICIENT_OBSERVATIONS" or ret.reason == "INSUFFICIENT_OBSERVATIONS":
        return unavailable("F-RAP-002", "INSUFFICIENT_OBSERVATIONS", len(values))
    if downside.value in (None, 0.0) or ret.value is None:
        return unavailable("F-RAP-002", "ZERO_DENOMINATOR", len(values))
    assert downside.value is not None
    return FactorResult(
        "F-RAP-002", (ret.value - mar) / downside.value, FactorStatus.AVAILABLE, None, len(values)
    )


def calmar(
    values: Sequence[ReturnObservation],
    annualization: int,
    *,
    minimum_observations: int = 1,
) -> FactorResult:
    drawdown = maximum_drawdown(values, minimum_observations=minimum_observations)
    ret = annualized_return(values, annualization, minimum_observations=minimum_observations)
    if drawdown.reason == "INSUFFICIENT_OBSERVATIONS" or ret.reason == "INSUFFICIENT_OBSERVATIONS":
        return unavailable("F-RAP-003", "INSUFFICIENT_OBSERVATIONS", len(values))
    if drawdown.value in (None, 0.0) or ret.value is None:
        return unavailable("F-RAP-003", "ZERO_DENOMINATOR", len(values))
    assert drawdown.value is not None
    return FactorResult(
        "F-RAP-003", ret.value / abs(drawdown.value), FactorStatus.AVAILABLE, None, len(values)
    )
