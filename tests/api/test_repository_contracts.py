from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest
from starlette.requests import Request

from fip.api.dependencies import get_api_repositories
from fip.api.errors import NotFoundError
from fip.api.repositories import RepositoryAdapter


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


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


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


def test_dependency_creates_and_closes_one_adapter_set_per_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reusing a session across requests would leak transaction state."""
    sessions: list[_ClosingSession] = []

    def new_session() -> _ClosingSession:
        session = _ClosingSession()
        sessions.append(session)
        return session

    monkeypatch.setattr("fip.api.dependencies._new_session", new_session)

    first: Iterator[object] = get_api_repositories(_request())
    first_repositories = next(first)
    second: Iterator[object] = get_api_repositories(_request())
    second_repositories = next(second)

    assert first_repositories is not second_repositories
    assert first_repositories.funds is not second_repositories.funds  # type: ignore[attr-defined]
    assert first_repositories.funds.session is sessions[0]  # type: ignore[attr-defined]
    assert second_repositories.funds.session is sessions[1]  # type: ignore[attr-defined]

    first.close()
    second.close()

    assert [session.closed for session in sessions] == [True, True]
