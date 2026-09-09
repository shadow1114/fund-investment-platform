from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import sqrt

from fip.strategy_library.normalization import normalize_factor


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
    raw_value: float | None = None
    interaction_value: float | None = None
    direction: str | None = None
    window: str | None = None
    reason_code: str | None = None

    @property
    def scoring_value(self) -> float | None:
        if self.interaction_value is not None:
            return self.interaction_value
        return self.normalized_value


@dataclass(frozen=True, slots=True)
class FundScoreResult:
    value: float | None
    status: ScoreStatus
    reason_code: str | None
    data_completeness: float


@dataclass(frozen=True, slots=True)
class TrackingErrorInput:
    share_class_id: int
    tracking_error: float | None
    normalized_tracking_error: float | None
    information_ratio: float | None = None
    sharpe: float | None = None


@dataclass(frozen=True, slots=True)
class TrackingErrorScore:
    share_class_id: int
    interaction_value: float | None
    status: str
    reason_code: str | None


def calculate_tracking_error_scores(
    values: Sequence[TrackingErrorInput], *, profile: str, minimum_sample: int
) -> tuple[TrackingErrorScore, ...]:
    if profile in {"passive_equity", "bond"}:
        return tuple(
            TrackingErrorScore(
                item.share_class_id,
                (
                    0.0
                    if profile == "bond"
                    and item.tracking_error is not None
                    and item.tracking_error > 0.015
                    else item.normalized_tracking_error
                ),
                "AVAILABLE" if item.normalized_tracking_error is not None else "UNAVAILABLE",
                (
                    None
                    if item.normalized_tracking_error is not None
                    else "TRACKING_ERROR_UNAVAILABLE"
                ),
            )
            for item in values
        )
    if profile not in {"active_equity", "hybrid"}:
        raise ValueError(f"unsupported profile: {profile}")
    composites: list[tuple[int, float]] = []
    neutral: set[int] = set()
    unavailable_ids: set[int] = set()
    for item in values:
        if item.tracking_error is None or item.tracking_error < 0:
            unavailable_ids.add(item.share_class_id)
            continue
        if profile == "active_equity":
            if item.information_ratio is None:
                unavailable_ids.add(item.share_class_id)
            elif item.information_ratio > 0.5:
                composites.append(
                    (item.share_class_id, sqrt(item.tracking_error * item.information_ratio))
                )
            elif item.information_ratio <= 0:
                composites.append((item.share_class_id, -sqrt(item.tracking_error)))
            else:
                neutral.add(item.share_class_id)
        elif item.sharpe is None:
            unavailable_ids.add(item.share_class_id)
        elif item.sharpe > 1.0:
            composites.append((item.share_class_id, sqrt(item.tracking_error * item.sharpe)))
        else:
            composites.append((item.share_class_id, -sqrt(item.tracking_error)))
    normalized = {
        item.share_class_id: item
        for item in normalize_factor(composites, "HIGHER_IS_BETTER", minimum_sample)
    }
    results: list[TrackingErrorScore] = []
    for item in values:
        if item.share_class_id in neutral:
            results.append(TrackingErrorScore(item.share_class_id, 50.0, "AVAILABLE", None))
        elif item.share_class_id in unavailable_ids:
            results.append(
                TrackingErrorScore(
                    item.share_class_id,
                    None,
                    "UNAVAILABLE",
                    "TRACKING_ERROR_INTERACTION_UNAVAILABLE",
                )
            )
        else:
            normalized_item = normalized[item.share_class_id]
            results.append(
                TrackingErrorScore(
                    item.share_class_id,
                    normalized_item.normalized_value,
                    normalized_item.status,
                    normalized_item.reason_code,
                )
            )
    return tuple(results)


def calculate_score(
    items: Sequence[ScoringItem], *, minimum_factors: int, minimum_completeness: float
) -> FundScoreResult:
    """Apply fixed weights only to OOS-valid, available normalized inputs."""
    configured = [item for item in items if item.configured_weight > 0]
    available = [item for item in configured if item.scoring_value is not None]
    completeness = len(available) / len(configured) if configured else 0.0
    if any(item.effectiveness == "VALIDATION_PENDING" for item in items):
        return FundScoreResult(
            None, ScoreStatus.VALIDATION_PENDING, "OOS_PENDING", completeness
        )
    usable = [
        item
        for item in configured
        if item.effectiveness == "VALID" and item.scoring_value is not None
    ]
    if len(usable) < minimum_factors or completeness < minimum_completeness:
        return FundScoreResult(
            None,
            ScoreStatus.UNAVAILABLE,
            "INSUFFICIENT_FACTORS",
            completeness,
        )
    weight_total = sum(item.configured_weight for item in usable)
    value = sum(
        item.scoring_value * item.configured_weight / weight_total
        for item in usable
        if item.scoring_value is not None
    )
    return FundScoreResult(value, ScoreStatus.AVAILABLE, None, completeness)
