import datetime as dt

import pytest

from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.returns import annualized_return, cumulative_return


def test_return_factors_have_known_values():
    values = [
        ReturnObservation(dt.date(2026, 1, 1), 0.1),
        ReturnObservation(dt.date(2026, 1, 2), -0.1),
    ]
    assert cumulative_return(values).value == pytest.approx(-0.01)
    assert annualized_return(values, 2).value == pytest.approx(-0.01)


@pytest.mark.parametrize("calculator", [cumulative_return, annualized_return])
def test_return_factors_enforce_injected_minimum_observations(calculator):
    values = [ReturnObservation(dt.date(2026, 1, 1), 0.01)]

    if calculator is annualized_return:
        result = calculator(values, 252, minimum_observations=2)
    else:
        result = calculator(values, minimum_observations=2)

    assert result.status == "UNAVAILABLE"
    assert result.reason == "INSUFFICIENT_OBSERVATIONS"
    assert result.observations == 1
