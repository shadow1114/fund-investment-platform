from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fip.api.errors import NotFoundError


class RepositoryAdapter:
    """Small, deterministic boundary shared by the API resource adapters.

    Domain-specific query implementations can replace the protected loading
    hooks without changing the HTTP-facing repository contract.
    """

    def __init__(self, session: object, resource: str) -> None:
        self.session = session
        self.resource = resource

    def _list_rows(self, **_: object) -> list[Mapping[str, object]]:
        return []

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        return next(
            (row for row in self._list_rows() if row.get("id") == identifier),
            None,
        )

    def list(self, **filters: object) -> list[dict[str, object]]:
        rows = (dict(row) for row in self._list_rows(**filters))
        return sorted(rows, key=lambda row: (str(row.get("name", "")), str(row.get("id", ""))))

    def get(self, identifier: str) -> Mapping[str, object]:
        row = self._get_row(identifier)
        if row is None:
            raise NotFoundError(self.resource, identifier)
        return dict(row)


class FundRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "fund")


class UniverseRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "fund universe")


class PortfolioRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "portfolio")


class DecisionRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "decision")


class BacktestRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "backtest")


@dataclass(frozen=True, slots=True)
class ApiRepositories:
    """The complete request-scoped set of API read adapters."""

    funds: FundRepository
    universes: UniverseRepository
    portfolios: PortfolioRepository
    decisions: DecisionRepository
    backtests: BacktestRepository

    @classmethod
    def from_session(cls, session: object) -> ApiRepositories:
        return cls(
            funds=FundRepository(session),
            universes=UniverseRepository(session),
            portfolios=PortfolioRepository(session),
            decisions=DecisionRepository(session),
            backtests=BacktestRepository(session),
        )


class ReadRepository:
    """Contract-facing adapter seam; domain repositories can be injected later."""

    def list_funds(self, **_: Any) -> list[dict[str, Any]]:
        return []

    def list_universes(self, **_: Any) -> list[dict[str, Any]]:
        return []

    def list_portfolios(self, **_: Any) -> list[dict[str, Any]]:
        return []

    def get(self, resource: str, identifier: str) -> dict[str, Any]:
        raise NotFoundError(resource, identifier)
