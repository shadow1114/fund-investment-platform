from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelectionCondition:
    condition_id: str
    status: str
    passed: bool | None


@dataclass(frozen=True, slots=True)
class SelectionConditionResult:
    status: str
    conditions: tuple[SelectionCondition, ...]


def evaluate_candidate(conditions: Sequence[SelectionCondition]) -> SelectionConditionResult:
    ordered = tuple(sorted(conditions, key=lambda item: item.condition_id))
    selected = all(item.status == "AVAILABLE" and item.passed is True for item in ordered)
    return SelectionConditionResult("SELECTED" if selected else "REJECTED", ordered)
