from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class NormalizationStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class NormalizedFactorValue:
    share_class_id: int
    raw_value: float
    normalized_value: float | None
    status: NormalizationStatus
    reason_code: str | None


def normalize_factor(
    values: Sequence[tuple[int, float]],
    direction: str,
    minimum_sample: int,
    target_range: tuple[float, float] | None = None,
) -> tuple[NormalizedFactorValue, ...]:
    """Return percentile values without mutating or replacing supplied raw values."""
    ordered = tuple(sorted(values))
    if len(ordered) < minimum_sample:
        return tuple(
            NormalizedFactorValue(
                share_class_id,
                raw_value,
                None,
                NormalizationStatus.UNAVAILABLE,
                "INSUFFICIENT_PEER_SAMPLE",
            )
            for share_class_id, raw_value in ordered
        )
    if direction not in {"HIGHER_IS_BETTER", "LOWER_IS_BETTER", "TARGET_RANGE"}:
        raise ValueError(f"unsupported normalization direction: {direction}")
    if direction == "TARGET_RANGE":
        if target_range is None or target_range[0] > target_range[1]:
            raise ValueError("TARGET_RANGE normalization requires an ordered target range")
        lower, upper = target_range

        def rank_value(item: tuple[int, float]) -> float:
            return max(lower - item[1], 0.0, item[1] - upper)

        ranked = sorted(ordered, key=rank_value)
    else:
        def rank_value(item: tuple[int, float]) -> float:
            return item[1]

        ranked = sorted(ordered, key=rank_value, reverse=direction == "HIGHER_IS_BETTER")
    ranks: dict[int, float] = {}
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and rank_value(ranked[end]) == rank_value(ranked[index]):
            end += 1
        average_rank = (index + 1 + end) / 2
        for share_class_id, _ in ranked[index:end]:
            ranks[share_class_id] = average_rank
        index = end
    denominator = len(ordered) - 1
    return tuple(
        NormalizedFactorValue(
            share_class_id,
            raw_value,
            100 * (len(ordered) - ranks[share_class_id]) / denominator,
            NormalizationStatus.AVAILABLE,
            None,
        )
        for share_class_id, raw_value in ordered
    )
