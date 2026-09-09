from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FactorEffectivenessResult:
    ic: float | None
    icir: float | None
    monotonic: bool | None
    redundancy_group: str | None
    verdict: str
    reason_code: str | None


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
