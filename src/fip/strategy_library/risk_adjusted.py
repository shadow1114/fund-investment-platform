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
    values: Sequence[ReturnObservation], annualization: int, risk_free: float = 0.0
) -> FactorResult:
    vol = volatility(values, annualization)
    ret = annualized_return(values, annualization)
    if vol.value in (None, 0.0) or ret.value is None:
        return unavailable("F-RAP-001", "ZERO_DENOMINATOR", len(values))
    assert vol.value is not None
    return FactorResult(
        "F-RAP-001", (ret.value - risk_free) / vol.value, FactorStatus.AVAILABLE, None, len(values)
    )


def sortino(
    values: Sequence[ReturnObservation], annualization: int, mar: float = 0.0
) -> FactorResult:
    downside = downside_volatility(values, annualization, mar)
    ret = annualized_return(values, annualization)
    if downside.value in (None, 0.0) or ret.value is None:
        return unavailable("F-RAP-002", "ZERO_DENOMINATOR", len(values))
    assert downside.value is not None
    return FactorResult(
        "F-RAP-002", (ret.value - mar) / downside.value, FactorStatus.AVAILABLE, None, len(values)
    )


def calmar(values: Sequence[ReturnObservation], annualization: int) -> FactorResult:
    drawdown = maximum_drawdown(values)
    ret = annualized_return(values, annualization)
    if drawdown.value in (None, 0.0) or ret.value is None:
        return unavailable("F-RAP-003", "ZERO_DENOMINATOR", len(values))
    assert drawdown.value is not None
    return FactorResult(
        "F-RAP-003", ret.value / abs(drawdown.value), FactorStatus.AVAILABLE, None, len(values)
    )
