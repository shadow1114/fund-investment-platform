from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from fip.api.repositories import ApiRepositories


def _new_session(request: Request) -> Session:
    return Session(request.app.state.api_engine, future=True)


def get_api_repositories(request: Request) -> Iterator[ApiRepositories]:
    """Provide and close one SQLAlchemy session-backed adapter set per request."""
    session = _new_session(request)
    try:
        yield ApiRepositories.from_session(session)
    finally:
        session.close()
