import datetime as dt

import pytest

from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.stability import positive_return_ratio, rolling_sharpe


def _observations(*values: float) -> tuple[ReturnObservation, ...]:
    return tuple(
        ReturnObservation(dt.date(2026, 1, index + 1), value)
        for index, value in enumerate(values)
    )


def test_positive_return_ratio_has_known_value():
    result = positive_return_ratio(_observations(0.01, 0.0, -0.01, 0.02))

    assert result.value == pytest.approx(0.5)


def test_stability_factors_enforce_observation_requirements():
    values = _observations(0.01, -0.01)

    ratio = positive_return_ratio(values, minimum_observations=3)
    rolling = rolling_sharpe(
        values,
        252,
        0.0,
        window=2,
        minimum_valid_points=2,
        minimum_observations=3,
    )

    assert ratio.reason == "INSUFFICIENT_OBSERVATIONS"
    assert rolling.reason == "INSUFFICIENT_OBSERVATIONS"


def test_rolling_sharpe_requires_risk_free_rate_and_valid_windows():
    values = _observations(0.01, -0.01, 0.02)

    assert rolling_sharpe(values, 252, None, 2, 1).reason == "RISK_FREE_UNAVAILABLE"
    assert rolling_sharpe(values, 252, 0.0, 2, 3).reason == "INSUFFICIENT_VALID_WINDOWS"