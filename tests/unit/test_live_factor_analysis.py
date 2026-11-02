import datetime as dt
from decimal import Decimal

from fip.api.repositories import _resolve_risk_free_curve
from fip.platform.decision_data.pit import RiskFreeRatePoint
from fip.services.factor_service.live_analysis import (
    FACTOR_CATALOG,
    calculate_period_factor_values,
)
from fip.strategy_library.factor_types import ReturnObservation


def test_live_analysis_returns_all_catalog_factors_grouped_by_catalog_identity():
    start = dt.date(2024, 1, 1)
    fund = tuple(
        ReturnObservation(start + dt.timedelta(days=index), 0.0005 + (index % 7 - 3) * 0.0001)
        for index in range(400)
    )
    benchmark = tuple(
        ReturnObservation(point.effective_at, 0.0004 + (index % 5 - 2) * 0.0001)
        for index, point in enumerate(fund)
    )
    rates = tuple(ReturnObservation(point.effective_at, 0.0001) for point in fund)

    results = calculate_period_factor_values(
        fund_returns=fund,
        benchmark_returns=benchmark,
        risk_free_returns=rates,
        annualized_risk_free=0.025,
        annualized_mar=0.0,
        annualization=252,
    )

    assert {item["factor_id"] for item in results} == {item["factor_id"] for item in FACTOR_CATALOG}
    assert len(results) == 26
    rolling = next(item for item in results if item["factor_id"] == "F-STAB-005")
    assert len(rolling["series"]) == len(fund) - 251
    assert all(item["category"] for item in results)


def test_live_analysis_marks_benchmark_factors_unavailable_without_benchmark():
    start = dt.date(2026, 1, 1)
    fund = tuple(
        ReturnObservation(start + dt.timedelta(days=index), 0.001 if index % 2 else -0.0002)
        for index in range(90)
    )
    results = calculate_period_factor_values(
        fund_returns=fund,
        benchmark_returns=(),
        risk_free_returns=(),
        annualized_risk_free=None,
        annualized_mar=0.0,
        annualization=252,
    )
    relative = [item for item in results if item["category"] == "REL"]
    assert len(relative) == 5
    assert all(item["status"] == "UNAVAILABLE" for item in relative)


def test_period_minimum_observations_apply_to_relative_and_duration_factors():
    start = dt.date(2026, 1, 1)
    fund = tuple(ReturnObservation(start + dt.timedelta(days=i), -0.01) for i in range(60))
    benchmark = tuple(ReturnObservation(point.effective_at, -0.005) for point in fund)
    results = calculate_period_factor_values(
        fund_returns=fund,
        benchmark_returns=benchmark,
        risk_free_returns=fund,
        annualized_risk_free=0.02,
        annualized_mar=0.0,
        annualization=252,
        minimum_observations=100,
    )
    by_id = {item["factor_id"]: item for item in results}
    for factor_id in (
        "F-RET-004",
        "F-RISK-006",
        "F-RISK-007",
        "F-REL-001",
        "F-REL-002",
        "F-REL-003",
        "F-REL-004",
        "F-REL-005",
        "F-STAB-002",
    ):
        assert by_id[factor_id]["status"] == "UNAVAILABLE"
    assert by_id["F-RET-004"]["reason_code"] == "INSUFFICIENT_OBSERVATIONS"
    assert by_id["F-RISK-006"]["reason_code"] == "INSUFFICIENT_OBSERVATIONS"
    assert by_id["F-RISK-007"]["reason_code"] == "INSUFFICIENT_OBSERVATIONS"
    assert by_id["F-REL-001"]["reason_code"] == "INSUFFICIENT_PAIRED_OBSERVATIONS"


def test_period_minimum_coverage_also_gates_stability_factors():
    start = dt.date(2024, 1, 1)
    fund = tuple(
        ReturnObservation(start + dt.timedelta(days=i), 0.001 + (i % 3) * 0.0001)
        for i in range(400)
    )
    benchmark = tuple(ReturnObservation(point.effective_at, 0.0005) for point in fund)
    results = calculate_period_factor_values(
        fund_returns=fund,
        benchmark_returns=benchmark,
        risk_free_returns=fund,
        annualized_risk_free=0.02,
        annualized_mar=0.0,
        annualization=252,
        minimum_observations=1134,
    )

    by_id = {item["factor_id"]: item for item in results}
    for factor_id in (
        "F-STAB-001",
        "F-STAB-003",
        "F-STAB-004",
        "F-STAB-005",
        "F-STAB-006",
        "F-STAB-007",
    ):
        assert by_id[factor_id]["status"] == "UNAVAILABLE"
        assert by_id[factor_id]["reason_code"] == "INSUFFICIENT_OBSERVATIONS"


def test_risk_free_curve_interpolates_only_between_adjacent_tenors():
    day = dt.date(2026, 10, 30)
    points = (
        RiskFreeRatePoint(day, "3M", Decimal("0.02"), 1, "EXACT"),
        RiskFreeRatePoint(day, "1Y", Decimal("0.05"), 1, "EXACT"),
    )
    resolved = _resolve_risk_free_curve(points, "6M", "CNY")

    assert resolved == ((day, Decimal("0.02981818181818181818181818182"), "INTERPOLATED"),)
