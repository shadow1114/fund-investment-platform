import datetime as dt

from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.risk_adjusted import calmar, sharpe, sortino


def _observations(*values: float) -> tuple[ReturnObservation, ...]:
    return tuple(
        ReturnObservation(dt.date(2026, 1, index + 1), value)
        for index, value in enumerate(values)
    )


def test_risk_adjusted_factors_have_known_available_results():
    values = _observations(0.02, -0.01, 0.03)

    assert sharpe(values, 252, 0.01).status == "AVAILABLE"
    assert sortino(values, 252, 0.0).status == "AVAILABLE"
    assert calmar(values, 252).status == "AVAILABLE"


def test_risk_adjusted_factors_preserve_missing_rate_reasons():
    values = _observations(0.02, -0.01)

    assert sharpe(values, 252, None).reason == "RISK_FREE_UNAVAILABLE"
    assert sortino(values, 252, None).reason == "MAR_UNAVAILABLE"


def test_risk_adjusted_factors_enforce_injected_minimum_observations():
    values = _observations(0.02, -0.01)

    results = (
        sharpe(values, 252, 0.0, minimum_observations=3),
        sortino(values, 252, 0.0, minimum_observations=3),
        calmar(values, 252, minimum_observations=3),
    )

    assert {result.reason for result in results} == {"INSUFFICIENT_OBSERVATIONS"}


def test_risk_adjusted_factors_report_zero_denominators():
    values = _observations(0.01, 0.01)

    assert sharpe(values, 252, 0.0).reason == "ZERO_DENOMINATOR"
    assert sortino(values, 252, 0.0).reason == "ZERO_DENOMINATOR"
    assert calmar(values, 252).reason == "ZERO_DENOMINATOR"