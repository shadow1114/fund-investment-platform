from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True, slots=True)
class FactorEffectivenessResult:
    ic: float | None
    icir: float | None
    monotonic: bool | None
    redundancy_group: str | None
    verdict: str
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class EffectivenessThresholds:
    ic_mean_min: float
    icir_abs_min: float
    minimum_cross_sections: int
    ic_std_ddof: int
    redundancy_threshold: float


def _average_ranks(values: Sequence[float]) -> list[float]:
    positions = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(positions):
        end = start + 1
        while end < len(positions) and values[positions[end]] == values[positions[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for position in positions[start:end]:
            ranks[position] = rank
        start = end
    return ranks


def validate_effectiveness(
    observations: Sequence[tuple[float, float]], *, minimum_observations: int
) -> FactorEffectivenessResult:
    """Compute Spearman Rank IC on the supplied frozen OOS order only."""
    if len(observations) < minimum_observations:
        return FactorEffectivenessResult(
            None, None, None, None, "VALIDATION_PENDING", "INSUFFICIENT_OOS_OBSERVATIONS"
        )
    factors, outcomes = zip(*observations, strict=True)
    x_ranks, y_ranks = _average_ranks(factors), _average_ranks(outcomes)
    x_mean, y_mean = sum(x_ranks) / len(x_ranks), sum(y_ranks) / len(y_ranks)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks, strict=True))
    x_scale = sum((x - x_mean) ** 2 for x in x_ranks)
    y_scale = sum((y - y_mean) ** 2 for y in y_ranks)
    if x_scale == 0 or y_scale == 0:
        return FactorEffectivenessResult(None, None, None, None, "INVALID", "CONSTANT_OOS_SERIES")
    ic = numerator / (x_scale * y_scale) ** 0.5
    return FactorEffectivenessResult(ic, None, ic > 0, None, "VALID", None)


def validate_effectiveness_series(
    ic_series: Sequence[float],
    *,
    layer_returns: Sequence[float],
    expected_direction: str,
    thresholds: EffectivenessThresholds,
    redundant_with: tuple[str, float] | None = None,
) -> FactorEffectivenessResult:
    if len(ic_series) < thresholds.minimum_cross_sections:
        return FactorEffectivenessResult(
            None,
            None,
            None,
            None,
            "VALIDATION_PENDING",
            "INSUFFICIENT_OOS_CROSS_SECTIONS",
        )
    if expected_direction not in {"POSITIVE", "NEGATIVE"}:
        raise ValueError(f"unsupported expected direction: {expected_direction}")
    if thresholds.ic_std_ddof < 0 or len(ic_series) <= thresholds.ic_std_ddof:
        raise ValueError("IC standard-deviation degrees of freedom are invalid")
    ic_mean = sum(ic_series) / len(ic_series)
    variance = sum((value - ic_mean) ** 2 for value in ic_series) / (
        len(ic_series) - thresholds.ic_std_ddof
    )
    ic_std = sqrt(variance)
    if ic_std == 0:
        return FactorEffectivenessResult(
            ic_mean, None, None, None, "INVALID", "ZERO_IC_DISPERSION"
        )
    icir = ic_mean / ic_std
    direction_consistent = (
        ic_mean > 0 if expected_direction == "POSITIVE" else ic_mean < 0
    )
    monotonic = len(layer_returns) >= 2 and all(
        left <= right if expected_direction == "POSITIVE" else left >= right
        for left, right in zip(layer_returns, layer_returns[1:], strict=False)
    )
    if abs(ic_mean) < thresholds.ic_mean_min:
        return FactorEffectivenessResult(
            ic_mean, icir, monotonic, None, "INVALID", "IC_MEAN_BELOW_THRESHOLD"
        )
    if not direction_consistent:
        return FactorEffectivenessResult(
            ic_mean, icir, monotonic, None, "INVALID", "IC_DIRECTION_MISMATCH"
        )
    if abs(icir) < thresholds.icir_abs_min:
        return FactorEffectivenessResult(
            ic_mean, icir, monotonic, None, "INVALID", "ICIR_BELOW_THRESHOLD"
        )
    if not monotonic:
        return FactorEffectivenessResult(
            ic_mean, icir, monotonic, None, "INVALID", "NON_MONOTONIC_LAYERS"
        )
    if redundant_with is not None and abs(redundant_with[1]) > thresholds.redundancy_threshold:
        return FactorEffectivenessResult(
            ic_mean,
            icir,
            monotonic,
            redundant_with[0],
            "INVALID",
            "REDUNDANT_FACTOR",
        )
    return FactorEffectivenessResult(ic_mean, icir, monotonic, None, "VALID", None)
