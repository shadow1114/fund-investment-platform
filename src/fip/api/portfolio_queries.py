from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from fip.api.context import Principal
from fip.api.errors import NotFoundError


class _Repository(Protocol):
    def list(self, **filters: object) -> list[dict[str, object]]: ...

    def get(self, identifier: str) -> Mapping[str, object]: ...


def _visible(row: Mapping[str, object], principal: Principal) -> bool:
    owner = row.get("owner_user_id")
    viewers = row.get("viewer_user_ids")
    if owner is None and viewers is None:
        return True
    if owner == principal.user_id:
        return True
    return isinstance(viewers, list | tuple | set) and principal.user_id in viewers


def _summary(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "portfolio_id": row.get("portfolio_id", row.get("id")),
        "portfolio_name": row.get("portfolio_name", row.get("name", "")),
        "portfolio_type": row.get("portfolio_type", "UNKNOWN"),
        "status": row.get("status", "UNKNOWN"),
        "base_currency": row.get("base_currency", "UNKNOWN"),
        "portfolio_version": row.get("portfolio_version", "UNKNOWN"),
    }


class PortfolioQueries:
    def __init__(self, repository: _Repository) -> None:
        self.repository = repository

    def list(
        self, *, principal: Principal, page: int, page_size: int, sort: str | None, order: str
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        rows = [_summary(row) for row in self.repository.list() if _visible(row, principal)]
        key = "portfolio_name" if sort in (None, "portfolio_name") else sort
        sort_key = key or "portfolio_name"
        rows.sort(
            key=lambda row: (str(row.get(sort_key, "")), str(row["portfolio_id"])),
            reverse=order == "desc",
        )
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], {
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
            }
        }

    def detail(self, identifier: str, *, principal: Principal) -> dict[str, object]:
        row = self.repository.get(identifier)
        if not _visible(row, principal):
            raise NotFoundError("portfolio", identifier)
        if set(row) <= {"id", "name"}:
            return dict(row)
        result = _summary(row)
        result.update(
            {
                "risk_profile": row.get("risk_profile", "UNKNOWN"),
                "portfolio_benchmark": row.get("portfolio_benchmark", {}),
                "portfolio_rule_version": row.get("portfolio_rule_version", "UNKNOWN"),
            }
        )
        return result


class OptimizationQueries:
    def __init__(self, repository: _Repository) -> None:
        self.repository = repository

    def detail(self, identifier: str) -> dict[str, object]:
        return dict(self.repository.get(identifier))


class DecisionQueries:
    def __init__(self, repository: _Repository) -> None:
        self.repository = repository

    def detail(self, identifier: str) -> dict[str, object]:
        return dict(self.repository.get(identifier))
