import datetime as dt

from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.relative import calculate_relative_factors


def test_relative_factors_require_minimum_paired_observations():
    points = [ReturnObservation(dt.date(2026, 1, 1), 0.01)]
    results = calculate_relative_factors(points, points, points, 252)
    assert {result.reason for result in results} == {"INSUFFICIENT_PAIRED_OBSERVATIONS"}


def test_relative_factors_fail_closed_when_risk_free_series_is_missing():
    points = [ReturnObservation(dt.date(2026, 1, 1), 0.01)]
    results = calculate_relative_factors(points, points, (), 252, minimum_observations=1)
    assert {result.reason for result in results} == {"RISK_FREE_UNAVAILABLE"}


def test_relative_r_squared_is_unavailable_for_constant_fund_returns():
    dates = [dt.date(2026, 1, day) for day in range(1, 4)]
    fund = [ReturnObservation(day, 0.01) for day in dates]
    benchmark = [
        ReturnObservation(day, value) for day, value in zip(dates, (0.0, 0.01, 0.02), strict=True)
    ]
    result = calculate_relative_factors(fund, benchmark, fund, 252, minimum_observations=3)
    r_squared = next(item for item in result if item.factor_id == "F-STAB-002")
    assert r_squared.value is None
    assert r_squared.reason == "ZERO_TOTAL_VARIANCE"
