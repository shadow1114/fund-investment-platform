import datetime as dt

import pytest

from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.relative import excess_return
from fip.strategy_library.risk import (
    conditional_value_at_risk,
    drawdown_duration,
    recovery_duration,
    value_at_risk,
)
from fip.strategy_library.stability import (
    kurtosis,
    rolling_maximum_drawdown,
    rolling_volatility,
    skewness,
)


def observations(*rates: float) -> tuple[ReturnObservation, ...]:
    return tuple(
        ReturnObservation(dt.date(2026, 1, index + 1), value) for index, value in enumerate(rates)
    )


def test_var_and_cvar_use_historical_left_tail_losses():
    values = observations(*([-0.1] * 2 + [0.01] * 18))
    assert value_at_risk(values, minimum_observations=20).value == pytest.approx(0.1)
    assert conditional_value_at_risk(
        values, minimum_observations=20, minimum_tail_observations=1
    ).value == pytest.approx(0.1)
    assert (
        conditional_value_at_risk(
            values, minimum_observations=20, minimum_tail_observations=5
        ).status
        == "WARNING"
    )


def test_drawdown_duration_and_recovery_duration_use_trading_observations():
    values = observations(0.1, -0.1, -0.1, 0.25)
    assert drawdown_duration(values).value == 2
    assert recovery_duration(values).value == 1
    not_recovered = recovery_duration(observations(0.1, -0.2, 0.01))
    assert not_recovered.status == "UNAVAILABLE"
    assert not_recovered.reason == "NOT_RECOVERED"


def test_skewness_and_excess_kurtosis_are_unavailable_for_constant_series():
    values = observations(0.01, 0.01, 0.01)
    assert skewness(values, minimum_observations=3).reason == "ZERO_VARIANCE"
    assert kurtosis(values, minimum_observations=3).reason == "ZERO_VARIANCE"


def test_rolling_volatility_and_drawdown_return_dated_series():
    values = observations(0.1, -0.2, 0.05, 0.01)
    volatility = rolling_volatility(values, annualization=1, window=2)
    drawdown = rolling_maximum_drawdown(values, window=2)
    assert volatility.factor_id == "F-STAB-006"
    assert len(volatility.series) == 3
    assert drawdown.factor_id == "F-STAB-007"
    assert len(drawdown.series) == 3


def test_excess_return_compounds_fund_and_benchmark_returns():
    fund = observations(0.1, 0.1)
    benchmark = observations(0.05, 0.05)
    result = excess_return(fund, benchmark)
    assert result.factor_id == "F-REL-001"
    assert result.value == pytest.approx(1.1**2 - 1.05**2)
