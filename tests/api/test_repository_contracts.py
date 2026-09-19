from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import fip.api.app as api_app
from fip.api.dependencies import get_api_repositories
from fip.api.errors import NotFoundError
from fip.api.repositories import (
    ApiRepositories,
    BacktestRepository,
    DecisionRepository,
    FundRepository,
    OptimizationRepository,
    PortfolioRepository,
    RepositoryAdapter,
    UniverseRepository,
)
from fip.api.routers.reads import get_repository


class _RowsAdapter(RepositoryAdapter):
    def _list_rows(self, **_: object) -> list[Mapping[str, object]]:
        return [
            {"id": "fund-2", "name": "Zeta"},
            {"id": "fund-1", "name": "Alpha"},
            {"id": "fund-3", "name": "Alpha"},
        ]


class _ClosingSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FoundFundRepository(FundRepository):
    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if identifier == "fund-1":
            return {"id": "fund-1", "name": "Alpha"}
        return None


class _FoundRepository(RepositoryAdapter):
    def __init__(self, session: object, resource: str, identifier: str) -> None:
        super().__init__(session, resource)
        self.identifier = identifier

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if identifier == self.identifier:
            return {"id": identifier, "name": "Available"}
        return None


def _repositories_with_detail(resource: str, identifier: str) -> ApiRepositories:
    session = object()
    repositories = ApiRepositories.from_session(session)
    assert isinstance(repositories.optimizations, OptimizationRepository)
    adapter = _FoundRepository(session, resource, identifier)
    replacements = {
        "fund": {"funds": adapter},
        "fund universe": {"universes": adapter},
        "portfolio": {"portfolios": adapter},
        "optimization": {"optimizations": adapter},
        "decision": {"decisions": adapter},
        "backtest": {"backtests": adapter},
    }
    return replace(repositories, **replacements[resource])  # type: ignore[arg-type]


def test_list_rows_have_a_deterministic_id_tiebreaker() -> None:
    """Changing the stable sort key would make equal-name rows reorder."""
    rows = _RowsAdapter(session=object(), resource="fund").list()

    assert rows == [
        {"id": "fund-1", "name": "Alpha"},
        {"id": "fund-3", "name": "Alpha"},
        {"id": "fund-2", "name": "Zeta"},
    ]


def test_missing_detail_id_raises_contract_not_found_error() -> None:
    """Returning an empty mapping for an unknown detail resource is a contract bug."""
    adapter = _RowsAdapter(session=object(), resource="fund")

    with pytest.raises(NotFoundError, match="fund 'missing' was not found"):
        adapter.get("missing")


def test_router_dependency_supplies_one_canonical_adapter_set_per_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bypassing the request-scoped set would give routes the old placeholder adapter."""
    sessions: list[_ClosingSession] = []

    def new_session(*_: object) -> _ClosingSession:
        session = _ClosingSession()
        sessions.append(session)
        return session

    monkeypatch.setattr("fip.api.dependencies._new_session", new_session)
    app = FastAPI()

    @app.get("/repository-probe")
    def repository_probe(
        repositories: ApiRepositories = Depends(get_repository),  # noqa: B008
    ) -> dict[str, object]:
        adapters = (
            repositories.funds,
            repositories.universes,
            repositories.portfolios,
            repositories.decisions,
            repositories.backtests,
        )
        return {
            "resources": [adapter.resource for adapter in adapters],
            "same_session": all(adapter.session is adapters[0].session for adapter in adapters),
        }

    with TestClient(app) as client:
        first = client.get("/repository-probe")
        second = client.get("/repository-probe")

    assert first.json() == {
        "resources": ["fund", "fund universe", "portfolio", "decision", "backtest"],
        "same_session": True,
    }
    assert second.json() == first.json()
    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
    assert [session.closed for session in sessions] == [True, True]


def test_app_lifespan_owns_configured_engine_and_disposes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A module-global engine would not be disposed when this app stops."""
    created_urls: list[str] = []

    class _Engine:
        def __init__(self) -> None:
            self.disposed = False

        def dispose(self) -> None:
            self.disposed = True

    engine = _Engine()

    def create_engine(database_url: str) -> _Engine:
        created_urls.append(database_url)
        return engine

    monkeypatch.setattr(api_app.settings, "database_url", "postgresql+psycopg://db/fip")
    monkeypatch.setattr(api_app, "create_api_engine", create_engine)

    app = api_app.create_app()
    assert created_urls == ["postgresql+psycopg://db/fip"]
    assert app.state.api_engine is engine

    with TestClient(app):
        assert engine.disposed is False

    assert engine.disposed is True


def test_fund_detail_route_uses_the_injected_canonical_repository() -> None:
    """A direct `_not_found` call would discard a repository detail result."""
    session = object()
    repositories = ApiRepositories(
        funds=_FoundFundRepository(session),
        universes=UniverseRepository(session),
        portfolios=PortfolioRepository(session),
        optimizations=OptimizationRepository(session),
        decisions=DecisionRepository(session),
        backtests=BacktestRepository(session),
    )
    app = api_app.create_app()
    app.dependency_overrides[get_api_repositories] = lambda: repositories

    with TestClient(app) as client:
        response = client.get("/api/v1/funds/fund-1")

    assert response.status_code == 200
    assert response.json()["data"] == {"id": "fund-1", "name": "Alpha"}


@pytest.mark.parametrize(
    ("path", "resource", "identifier"),
    [
        ("/api/v1/funds/fund-1", "fund", "fund-1"),
        ("/api/v1/funds/fund-1/nav-series", "fund", "fund-1"),
        ("/api/v1/funds/fund-1/evaluations", "fund", "fund-1"),
        ("/api/v1/funds/fund-1/scores", "fund", "fund-1"),
        ("/api/v1/fund-universes/universe-1", "fund universe", "universe-1"),
        ("/api/v1/portfolios/portfolio-1", "portfolio", "portfolio-1"),
        (
            "/api/v1/portfolios/portfolio-1/optimizations/optimization-1",
            "optimization",
            "optimization-1",
        ),
        ("/api/v1/decisions/decision-1", "decision", "decision-1"),
        ("/api/v1/backtests/backtest-1/status", "backtest", "backtest-1"),
        ("/api/v1/backtests/backtest-1/result", "backtest", "backtest-1"),
        ("/api/v1/backtests/backtest-1/performance", "backtest", "backtest-1"),
        ("/api/v1/backtests/backtest-1/bias-check", "backtest", "backtest-1"),
    ],
)
def test_detail_routes_use_the_request_scoped_repository_override(
    path: str, resource: str, identifier: str
) -> None:
    """A direct NotFoundError bypass would make every case below return 404."""
    app = api_app.create_app()
    app.dependency_overrides[get_api_repositories] = lambda: _repositories_with_detail(
        resource, identifier
    )

    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
