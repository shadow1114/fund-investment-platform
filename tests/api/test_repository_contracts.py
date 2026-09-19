from __future__ import annotations

from collections.abc import Mapping

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import fip.api.app as api_app
from fip.api.errors import NotFoundError
from fip.api.repositories import ApiRepositories, RepositoryAdapter
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
