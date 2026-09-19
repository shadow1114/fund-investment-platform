from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fip.api.repositories import ApiRepositories
from fip.settings import settings

_engine = create_engine(settings.database_url, future=True)


def _new_session() -> Session:
    return Session(_engine, future=True)


def get_api_repositories(_: Request) -> Iterator[ApiRepositories]:
    """Provide and close one SQLAlchemy session-backed adapter set per request."""
    session = _new_session()
    try:
        yield ApiRepositories.from_session(session)
    finally:
        session.close()
