import datetime as dt

from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.relative import calculate_relative_factors


def test_relative_factors_require_minimum_paired_observations():
    points = [ReturnObservation(dt.date(2026, 1, 1), 0.01)]
    results = calculate_relative_factors(points, points, points, 252)
    assert {result.reason for result in results} == {"INSUFFICIENT_PAIRED_OBSERVATIONS"}
