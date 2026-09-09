from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class ScoreStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    VALIDATION_PENDING = "VALIDATION_PENDING"


@dataclass(frozen=True, slots=True)
class ScoringItem:
    metric_id: str
    normalized_value: float | None
    configured_weight: float
    effectiveness: str


@dataclass(frozen=True, slots=True)
class FundScoreResult:
    value: float | None
    status: ScoreStatus
    reason_code: str | None


def calculate_score(
    items: Sequence[ScoringItem], *, minimum_factors: int, minimum_completeness: float
) -> FundScoreResult:
    """Apply fixed weights only to OOS-valid, available normalized inputs."""
    if any(item.effectiveness == "VALIDATION_PENDING" for item in items):
        return FundScoreResult(None, ScoreStatus.VALIDATION_PENDING, "OOS_PENDING")
    configured = [item for item in items if item.configured_weight > 0]
    usable = [
        item
        for item in configured
        if item.effectiveness == "VALID" and item.normalized_value is not None
    ]
    completeness = len(usable) / len(configured) if configured else 0.0
    if len(usable) < minimum_factors or completeness < minimum_completeness:
        return FundScoreResult(None, ScoreStatus.UNAVAILABLE, "INSUFFICIENT_FACTORS")
    weight_total = sum(item.configured_weight for item in usable)
    value = sum(
        item.normalized_value * item.configured_weight / weight_total
        for item in usable
        if item.normalized_value is not None
    )
    return FundScoreResult(value, ScoreStatus.AVAILABLE, None)
