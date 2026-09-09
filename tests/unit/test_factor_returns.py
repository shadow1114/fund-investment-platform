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
