import datetime as dt

import pytest

from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.risk import downside_volatility, maximum_drawdown, volatility


def _observations(*values: float) -> tuple[ReturnObservation, ...]:
    return tuple(
        ReturnObservation(dt.date(2026, 1, index + 1), value)
        for index, value in enumerate(values)
    )


def test_risk_factors_have_known_values():
    values = _observations(0.1, -0.2)

    assert volatility(values, 1).value == pytest.approx(0.21213203435596428)
    assert downside_volatility(values, 1, 0.0).value == pytest.approx(0.14142135623730953)
    assert maximum_drawdown(values).value == pytest.approx(-0.2)


def test_risk_factors_enforce_injected_minimum_observations():
    values = _observations(0.01, -0.01)

    results = (
        volatility(values, 252, minimum_observations=3),
        downside_volatility(values, 252, 0.0, minimum_observations=3),
        maximum_drawdown(values, minimum_observations=3),
    )

    assert {result.reason for result in results} == {"INSUFFICIENT_OBSERVATIONS"}
    assert {result.observations for result in results} == {2}


def test_downside_volatility_requires_mar():
    result = downside_volatility(_observations(0.01, -0.01), 252, None)

    assert result.status == "UNAVAILABLE"
    assert result.reason == "MAR_UNAVAILABLE"