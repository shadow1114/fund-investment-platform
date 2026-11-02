from collections.abc import Sequence
from math import sqrt
from statistics import mean, stdev

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)


def volatility(
    values: Sequence[ReturnObservation],
    annualization: int,
    *,
    minimum_observations: int = 2,
) -> FactorResult:
    if len(values) < max(2, minimum_observations):
        return unavailable("F-RISK-001", "INSUFFICIENT_OBSERVATIONS", len(values))
    return FactorResult(
        "F-RISK-001",
        stdev(x.value for x in values) * sqrt(annualization),
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )


def downside_volatility(
    values: Sequence[ReturnObservation],
    annualization: int,
    mar: float | None,
    *,
    minimum_observations: int = 2,
) -> FactorResult:
    if mar is None:
        return unavailable("F-RISK-002", "MAR_UNAVAILABLE", len(values))
    downside = [min(0.0, x.value - mar) for x in values]
    if len(downside) < max(2, minimum_observations):
        return unavailable("F-RISK-002", "INSUFFICIENT_OBSERVATIONS", len(values))
    if not any(value < 0 for value in downside):
        return FactorResult(
            "F-RISK-002",
            0.0,
            FactorStatus.WARNING,
            "NO_DOWNSIDE_OBSERVATIONS",
            len(values),
        )
    return FactorResult(
        "F-RISK-002",
        sqrt(sum(value * value for value in downside) / (len(downside) - 1)) * sqrt(annualization),
        FactorStatus.AVAILABLE,
        None,
        len(values),
    )


def maximum_drawdown(
    values: Sequence[ReturnObservation], *, minimum_observations: int = 1
) -> FactorResult:
    if len(values) < minimum_observations:
        return unavailable("F-RISK-003", "INSUFFICIENT_OBSERVATIONS", len(values))
    wealth = peak = 1.0
    drawdown = 0.0
    for point in values:
        wealth *= 1 + point.value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1)
    return FactorResult("F-RISK-003", drawdown, FactorStatus.AVAILABLE, None, len(values))


def _left_quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def value_at_risk(
    values: Sequence[ReturnObservation],
    *,
    confidence: float = 0.95,
    minimum_observations: int = 100,
) -> FactorResult:
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    if len(values) < minimum_observations:
        return unavailable("F-RISK-004", "INSUFFICIENT_OBSERVATIONS", len(values))
    value = max(0.0, -_left_quantile([item.value for item in values], 1 - confidence))
    return FactorResult("F-RISK-004", value, FactorStatus.AVAILABLE, None, len(values))


def conditional_value_at_risk(
    values: Sequence[ReturnObservation],
    *,
    confidence: float = 0.95,
    minimum_observations: int = 100,
    minimum_tail_observations: int = 5,
) -> FactorResult:
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    if len(values) < minimum_observations:
        return unavailable("F-RISK-005", "INSUFFICIENT_OBSERVATIONS", len(values))
    rates = [item.value for item in values]
    cutoff = _left_quantile(rates, 1 - confidence)
    tail = [rate for rate in rates if rate <= cutoff]
    if not tail:
        return unavailable("F-RISK-005", "INSUFFICIENT_TAIL_SAMPLE", len(values))
    status = (
        FactorStatus.WARNING if len(tail) < minimum_tail_observations else FactorStatus.AVAILABLE
    )
    return FactorResult(
        "F-RISK-005",
        max(0.0, -mean(tail)),
        status,
        "SMALL_TAIL_SAMPLE" if status == FactorStatus.WARNING else None,
        len(values),
    )


def drawdown_duration(
    values: Sequence[ReturnObservation], *, minimum_observations: int = 1
) -> FactorResult:
    if len(values) < minimum_observations:
        return unavailable("F-RISK-006", "INSUFFICIENT_OBSERVATIONS", len(values))
    wealth = peak = 1.0
    current = longest = 0
    for point in values:
        wealth *= 1 + point.value
        if wealth >= peak:
            peak = wealth
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return FactorResult("F-RISK-006", float(longest), FactorStatus.AVAILABLE, None, len(values))


def recovery_duration(
    values: Sequence[ReturnObservation], *, minimum_observations: int = 1
) -> FactorResult:
    if len(values) < minimum_observations:
        return unavailable("F-RISK-007", "INSUFFICIENT_OBSERVATIONS", len(values))
    wealth = peak = 1.0
    levels = [1.0]
    max_peak = 0.0
    max_trough_index = 0
    deepest = 0.0
    for index, point in enumerate(values, start=1):
        wealth *= 1 + point.value
        levels.append(wealth)
        if wealth >= peak:
            peak = wealth
        if wealth / peak - 1 < deepest:
            deepest = wealth / peak - 1
            max_peak = peak
            max_trough_index = index
    if deepest == 0.0:
        return FactorResult("F-RISK-007", 0.0, FactorStatus.AVAILABLE, None, len(values))
    for index in range(max_trough_index + 1, len(levels)):
        if levels[index] >= max_peak:
            return FactorResult(
                "F-RISK-007",
                float(index - max_trough_index),
                FactorStatus.AVAILABLE,
                None,
                len(values),
            )
    return unavailable("F-RISK-007", "NOT_RECOVERED", len(values))
