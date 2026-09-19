"""Contract-facing fund-universe reads over the canonical repository seam."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any, cast

from fip.api.errors import NotFoundError
from fip.api.fund_queries import QueryResult
from fip.api.repositories import UniverseRepository


def _as_iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _matches(row: Mapping[str, object], filters: Mapping[str, object]) -> bool:
    return all(
        expected is None or row.get(field) == expected for field, expected in filters.items()
    )


class UniverseQueries:
    def __init__(self, repository: UniverseRepository) -> None:
        self._repository = repository

    def list(
        self,
        *,
        strategy_id: str | None,
        decision_at: date | None,
        eligibility_rules_version: str | None,
    ) -> QueryResult:
        filters: dict[str, object] = {
            "strategy_id": strategy_id,
            "decision_at": _as_iso(decision_at),
            "eligibility_rules_version": eligibility_rules_version,
        }
        rows = [dict(row) for row in self._repository.list(**filters)]
        matched = [row for row in rows if _matches(row, filters)]
        matched.sort(key=lambda row: str(row.get("universe_id", row.get("id", ""))))
        first = matched[0] if matched else {}
        return QueryResult(
            matched,
            {
                "eligibility_rules_version": first.get("eligibility_rules_version", "unknown"),
                "scoring_policy_version": first.get("scoring_policy_version"),
            },
        )

    def detail(self, universe_id: str) -> QueryResult:
        summary = dict(self._repository.get(universe_id))
        read = getattr(self._repository, "read_members", None)
        if not callable(read):
            raise NotFoundError("fund universe members", universe_id)
        members = cast(Callable[[str], Mapping[str, Any]], read)(universe_id)
        meta = dict(cast(Mapping[str, object], members.get("meta", {})))
        summary.update(
            {
                "members": members.get("members", []),
                "excluded": members.get("excluded", []),
            }
        )
        return QueryResult(
            summary,
            {
                "eligibility_rules_version": meta.get(
                    "eligibility_rules_version", summary.get("eligibility_rules_version", "unknown")
                ),
                "scoring_policy_version": meta.get(
                    "scoring_policy_version", summary.get("scoring_policy_version")
                ),
            },
        )
