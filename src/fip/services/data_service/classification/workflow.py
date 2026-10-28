"""Pure orchestration helpers shared by offline preview and persisted refresh."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from .models import ClassificationSnapshot, Evidence
from .policy import ClassificationPolicy, load_policy
from .rules import classify
from .service import _canonical, _carry_paused, _observations

INDEX_REFRESH_PLAN = (
    ("fund_index_passive", {"symbol": "全部", "indicator": "被动指数型"}),
    ("fund_index_enhanced", {"symbol": "全部", "indicator": "增强指数型"}),
)


@dataclass(frozen=True)
class ClassificationPreview:
    snapshot: ClassificationSnapshot
    action: Literal["NO_CHANGE", "WRITE_REVISION", "CREATE_REVIEW"]
    unrecognized_reasons: tuple[str, ...]


def classify_v3_preview(
    observations: tuple[Evidence, ...] | list[Evidence],
    *,
    available_at: dt.datetime,
    baseline: ClassificationSnapshot | None = None,
    baseline_revision_id: int | None = None,
    policy: ClassificationPolicy | None = None,
) -> ClassificationSnapshot:
    """Run the same pure v3 rule path used by refresh, without persistence."""
    selected_policy = policy or load_policy(rule_version="3.0.0")
    if selected_policy.rule_version != "3.0.0":
        raise ValueError("v3 preview requires rule_version=3.0.0")
    if available_at.utcoffset() is None:
        raise ValueError("available_at must include timezone")
    current = classify(observations, classified_at=available_at, policy=selected_policy)
    current = current.model_copy(update={"observations": tuple(observations)})
    if baseline is not None:
        current = _carry_paused(current, baseline, baseline_revision_id or 1)
    return current


def preview_classification(
    proposed: ClassificationSnapshot,
    *,
    baseline: ClassificationSnapshot | None,
    baseline_reviewed: bool = False,
) -> ClassificationPreview:
    """Summarize whether a pure result differs and whether it needs human review."""
    if baseline is not None and _canonical(proposed.to_dict()) == _canonical(baseline.to_dict()):
        action: Literal["NO_CHANGE", "WRITE_REVISION", "CREATE_REVIEW"] = "NO_CHANGE"
    elif proposed.review_items or baseline_reviewed:
        action = "CREATE_REVIEW"
    else:
        action = "WRITE_REVISION"
    return ClassificationPreview(
        snapshot=proposed,
        action=action,
        unrecognized_reasons=tuple(
            item for item in proposed.review_items if "UNRECOGNIZED" in item or "UNKNOWN" in item
        ),
    )


def merge_snapshot_observations(
    baseline: ClassificationSnapshot | None,
    incoming: tuple[Evidence, ...] | list[Evidence],
) -> tuple[Evidence, ...]:
    """Merge by the classification service's stable observation identity."""
    from .service import _observation_key

    merged = {_observation_key(item): item for item in _observations(baseline)} if baseline else {}
    for item in incoming:
        merged[_observation_key(item)] = item
    return tuple(merged[key] for key in sorted(merged))


def evidence_effective_date(
    fallback: dt.date, observations: tuple[Evidence, ...] | list[Evidence]
) -> dt.date:
    """Never make a classification effective before any included evidence existed."""
    return max((fallback, *(item.classified_at.date() for item in observations)))


def should_fetch_snowball(
    snapshot: ClassificationSnapshot,
    *,
    available_at: dt.datetime,
    strategy_max_age: dt.timedelta = dt.timedelta(days=90),
) -> bool:
    """Fetch detail for unresolved/stale strategy or any unassessed quant tag."""
    if snapshot.strategy.status in {"UNKNOWN", "CANDIDATE", "CONFLICT"}:
        return True
    strategy_times = [item.classified_at for item in snapshot.strategy.evidence]
    if not strategy_times or available_at - max(strategy_times) > strategy_max_age:
        return True
    tag = (snapshot.strategy_tag_results or {}).get("QUANTITATIVE")
    return tag is None or tag.evaluation_state != "EVALUATED"


def index_refresh_requests() -> tuple[dict[str, object], ...]:
    """Exact offline request preview for one centralized two-set refresh."""
    return tuple(
        {"dataset": dataset, "params": dict(params)} for dataset, params in INDEX_REFRESH_PLAN
    )


def fund_refresh_requests(symbol: str) -> tuple[dict[str, object], ...]:
    """Exact mandatory request preview; supplemental detail is conditional."""
    return (
        {"dataset": "fund_overview", "params": {"symbol": symbol}},
        {"dataset": "fund_index_passive", "params": {"read": "latest saved batch"}},
        {"dataset": "fund_index_enhanced", "params": {"read": "latest saved batch"}},
        {
            "dataset": "fund_detail_xq",
            "params": {"symbol": symbol, "timeout": 20},
            "condition": "main strategy unresolved/conflicting/stale or tag not evaluated",
        },
    )
