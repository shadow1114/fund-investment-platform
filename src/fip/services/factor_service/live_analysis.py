from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)
from fip.strategy_library.relative import calculate_relative_factors, excess_return
from fip.strategy_library.returns import (
    annualized_return,
    cumulative_return,
    period_return,
    rolling_return,
)
from fip.strategy_library.risk import (
    conditional_value_at_risk,
    downside_volatility,
    drawdown_duration,
    maximum_drawdown,
    recovery_duration,
    value_at_risk,
    volatility,
)
from fip.strategy_library.risk_adjusted import calmar, sharpe, sortino
from fip.strategy_library.stability import (
    kurtosis,
    positive_return_ratio,
    rolling_maximum_drawdown,
    rolling_sharpe,
    rolling_volatility,
    skewness,
)

FACTOR_CATALOG: tuple[dict[str, str], ...] = (
    {
        "factor_id": "F-RET-001",
        "name": "年化收益率",
        "category": "RET",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-RET-002",
        "name": "累计收益率",
        "category": "RET",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-RET-003",
        "name": "区间收益率",
        "category": "RET",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-RET-004",
        "name": "滚动收益率",
        "category": "RET",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-RISK-001",
        "name": "波动率",
        "category": "RISK",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-RISK-002",
        "name": "下行波动率",
        "category": "RISK",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-RISK-003",
        "name": "最大回撤",
        "category": "RISK",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-RISK-004",
        "name": "VaR 95%",
        "category": "RISK",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-RISK-005",
        "name": "CVaR 95%",
        "category": "RISK",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-RISK-006",
        "name": "最大回撤持续期",
        "category": "RISK",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-RISK-007",
        "name": "最大回撤恢复期",
        "category": "RISK",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-RAP-001",
        "name": "夏普比率",
        "category": "RAP",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-RAP-002",
        "name": "索提诺比率",
        "category": "RAP",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-RAP-003",
        "name": "卡玛比率",
        "category": "RAP",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-STAB-001",
        "name": "月度胜率",
        "category": "STAB",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-STAB-002",
        "name": "R²",
        "category": "STAB",
        "direction": "STRATEGY_DEPENDENT",
    },
    {
        "factor_id": "F-STAB-003",
        "name": "偏度",
        "category": "STAB",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-STAB-004",
        "name": "超额峰度",
        "category": "STAB",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-STAB-005",
        "name": "滚动夏普比率",
        "category": "STAB",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-STAB-006",
        "name": "滚动波动率",
        "category": "STAB",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-STAB-007",
        "name": "滚动最大回撤",
        "category": "STAB",
        "direction": "LOWER_IS_BETTER",
    },
    {
        "factor_id": "F-REL-001",
        "name": "超额收益",
        "category": "REL",
        "direction": "HIGHER_IS_BETTER",
    },
    {"factor_id": "F-REL-002", "name": "Alpha", "category": "REL", "direction": "HIGHER_IS_BETTER"},
    {"factor_id": "F-REL-003", "name": "Beta", "category": "REL", "direction": "TARGET_RANGE"},
    {
        "factor_id": "F-REL-004",
        "name": "信息比率",
        "category": "REL",
        "direction": "HIGHER_IS_BETTER",
    },
    {
        "factor_id": "F-REL-005",
        "name": "跟踪误差",
        "category": "REL",
        "direction": "STRATEGY_DEPENDENT",
    },
)

_ROLLING_WINDOW = 252


def _monthly_returns(values: Sequence[ReturnObservation]) -> tuple[ReturnObservation, ...]:
    grouped: dict[tuple[int, int], list[ReturnObservation]] = defaultdict(list)
    for point in values:
        grouped[(point.effective_at.year, point.effective_at.month)].append(point)
    result: list[ReturnObservation] = []
    for points in grouped.values():
        accumulated = 1.0
        for point in points:
            accumulated *= 1 + point.value
        result.append(ReturnObservation(points[-1].effective_at, accumulated - 1))
    return tuple(result)


def _to_payload(metadata: dict[str, str], result: FactorResult) -> dict[str, object]:
    return {
        **metadata,
        "raw_value": result.value,
        "normalized_value": None,
        "status": "VALID" if result.status == "AVAILABLE" else result.status.value,
        "reason_code": result.reason,
        "observations": result.observations,
        "series": [
            {"date": effective_at.isoformat(), "value": value}
            for effective_at, value in result.series
        ],
    }


def calculate_period_factor_values(
    *,
    fund_returns: Sequence[ReturnObservation],
    benchmark_returns: Sequence[ReturnObservation],
    risk_free_returns: Sequence[ReturnObservation],
    annualized_risk_free: float | None,
    annualized_mar: float | None,
    annualization: int = 252,
    minimum_observations: int | None = None,
) -> list[dict[str, object]]:
    minimum = minimum_observations or max(2, int(len(fund_returns) * 0.9))
    daily_mar = annualized_mar / annualization if annualized_mar is not None else None
    monthly = _monthly_returns(fund_returns)
    rolling = (
        rolling_sharpe(fund_returns, annualization, annualized_risk_free, _ROLLING_WINDOW, 12)
        if fund_returns
        else unavailable("F-STAB-005", "INSUFFICIENT_OBSERVATIONS")
    )
    values: dict[str, FactorResult] = {
        "F-RET-001": annualized_return(fund_returns, annualization, minimum_observations=minimum),
        "F-RET-002": cumulative_return(fund_returns, minimum_observations=minimum),
        "F-RET-003": period_return(fund_returns, minimum_observations=minimum),
        "F-RET-004": rolling_return(fund_returns, _ROLLING_WINDOW, minimum_observations=minimum),
        "F-RISK-001": volatility(fund_returns, annualization, minimum_observations=minimum),
        "F-RISK-002": downside_volatility(
            fund_returns, annualization, daily_mar, minimum_observations=minimum
        ),
        "F-RISK-003": maximum_drawdown(fund_returns, minimum_observations=minimum),
        "F-RISK-004": value_at_risk(fund_returns, minimum_observations=max(100, minimum)),
        "F-RISK-005": conditional_value_at_risk(
            fund_returns, minimum_observations=max(100, minimum)
        ),
        "F-RISK-006": drawdown_duration(fund_returns, minimum_observations=minimum),
        "F-RISK-007": recovery_duration(fund_returns, minimum_observations=minimum),
        "F-RAP-001": sharpe(
            fund_returns, annualization, annualized_risk_free, minimum_observations=minimum
        ),
        "F-RAP-002": sortino(
            fund_returns, annualization, annualized_mar, minimum_observations=minimum
        ),
        "F-RAP-003": calmar(fund_returns, annualization, minimum_observations=minimum),
        "F-STAB-001": positive_return_ratio(monthly, minimum_observations=12),
        "F-STAB-003": skewness(fund_returns),
        "F-STAB-004": kurtosis(fund_returns),
        "F-STAB-005": rolling,
        "F-STAB-006": rolling_volatility(fund_returns, annualization, _ROLLING_WINDOW),
        "F-STAB-007": rolling_maximum_drawdown(fund_returns, _ROLLING_WINDOW),
        "F-REL-001": excess_return(fund_returns, benchmark_returns, minimum_observations=minimum),
    }
    if benchmark_returns:
        relative_values = calculate_relative_factors(
            fund_returns,
            benchmark_returns,
            risk_free_returns,
            annualization,
            minimum_observations=minimum,
        )
    else:
        relative_values = tuple(
            unavailable(factor_id, "BENCHMARK_UNAVAILABLE")
            for factor_id in (
                "F-REL-002",
                "F-REL-003",
                "F-REL-004",
                "F-REL-005",
                "F-STAB-002",
            )
        )
    values.update({item.factor_id: item for item in relative_values})
    if len(fund_returns) < minimum:
        for factor_id, result in values.items():
            if result.status in (FactorStatus.AVAILABLE, FactorStatus.WARNING):
                values[factor_id] = FactorResult(
                    factor_id,
                    None,
                    FactorStatus.UNAVAILABLE,
                    "INSUFFICIENT_OBSERVATIONS",
                    result.observations,
                )
    return [_to_payload(metadata, values[metadata["factor_id"]]) for metadata in FACTOR_CATALOG]
