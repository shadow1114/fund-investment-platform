from collections.abc import Sequence
from math import sqrt
from statistics import mean, stdev

from fip.strategy_library.factor_types import (
    FactorResult,
    FactorStatus,
    ReturnObservation,
    unavailable,
)


def align_return_series(
    fund: Sequence[ReturnObservation],
    benchmark: Sequence[ReturnObservation],
    risk_free: Sequence[ReturnObservation] = (),
) -> tuple[tuple[float, float, float], ...]:
    bench = {x.effective_at: x.value for x in benchmark}
    rf = {x.effective_at: x.value for x in risk_free}
    return tuple(
        (x.value, bench[x.effective_at], rf.get(x.effective_at, 0.0))
        for x in fund
        if x.effective_at in bench and (not risk_free or x.effective_at in rf)
    )


def calculate_relative_factors(
    fund_returns: Sequence[ReturnObservation],
    benchmark_returns: Sequence[ReturnObservation],
    risk_free_rates: Sequence[ReturnObservation],
    annualization: int,
    minimum_observations: int = 60,
) -> tuple[FactorResult, ...]:
    rows = align_return_series(fund_returns, benchmark_returns, risk_free_rates)
    if len(rows) < minimum_observations:
        return tuple(
            unavailable(fid, "INSUFFICIENT_PAIRED_OBSERVATIONS", len(rows))
            for fid in ("F-REL-002", "F-REL-003", "F-REL-004", "F-REL-005", "F-STAB-002")
        )
    fund, benchmark, rf = map(list, zip(*rows, strict=True))
    variance = sum((x - mean(benchmark)) ** 2 for x in benchmark)
    if variance == 0:
        return tuple(
            unavailable(fid, "UNIDENTIFIABLE_REGRESSION", len(rows))
            for fid in ("F-REL-002", "F-REL-003", "F-REL-004", "F-REL-005", "F-STAB-002")
        )
    beta = (
        sum((x - mean(benchmark)) * (y - mean(fund)) for x, y in zip(benchmark, fund, strict=True))
        / variance
    )
    alpha = (mean(fund) - mean(rf) - beta * (mean(benchmark) - mean(rf))) * annualization
    active = [f - b for f, b in zip(fund, benchmark, strict=True)]
    tracking = stdev(active) * sqrt(annualization)
    ir = mean(active) * annualization / tracking if tracking else None
    residual = [
        f - (mean(fund) + beta * (b - mean(benchmark)))
        for f, b in zip(fund, benchmark, strict=True)
    ]
    total_variance = sum((x - mean(fund)) ** 2 for x in fund)
    r_squared = None if total_variance == 0 else 1 - sum(x * x for x in residual) / total_variance
    return (
        FactorResult("F-REL-002", alpha, FactorStatus.AVAILABLE, None, len(rows)),
        FactorResult("F-REL-003", beta, FactorStatus.AVAILABLE, None, len(rows)),
        FactorResult(
            "F-REL-004",
            ir,
            FactorStatus.AVAILABLE if ir is not None else FactorStatus.UNAVAILABLE,
            None if ir is not None else "ZERO_DENOMINATOR",
            len(rows),
        ),
        FactorResult("F-REL-005", tracking, FactorStatus.AVAILABLE, None, len(rows)),
        FactorResult(
            "F-STAB-002",
            r_squared,
            FactorStatus.AVAILABLE if r_squared is not None else FactorStatus.UNAVAILABLE,
            None if r_squared is not None else "ZERO_TOTAL_VARIANCE",
            len(rows),
        ),
    )
