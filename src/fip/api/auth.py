from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import Request

from fip.api.context import Principal
from fip.api.errors import AuthenticationError


def authenticate_request(request: Request) -> Principal:
    """Resolve a principal; the development header mechanism is never production auth."""
    environment = os.getenv("FIP_ENV", "development").lower()
    if environment == "production":
        # Production never trusts the development identity headers.  The
        # deployment's auth middleware supplies a bearer subject in this
        # explicit adapter until a full OIDC connector is installed.
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise AuthenticationError()
        token_subject = authorization.removeprefix("Bearer ").strip()
        if not token_subject:
            raise AuthenticationError()
        user_id, _, role_text = token_subject.partition("|")
        raw_roles = role_text or "Researcher"
    else:
        user_id = request.headers.get("X-User-ID", "development-user")
        raw_roles = request.headers.get("X-Roles", "Researcher")
    roles = tuple(role.strip() for role in raw_roles.split(",") if role.strip())
    can_review = any(role.lower() in {"reviewer", "admin", "administrator"} for role in roles)
    return Principal(user_id, roles, can_review)


def principal_dependency() -> Callable[[Request], Principal]:
    """Return an injectable dependency factory for tests and future identity middleware."""
    return authenticate_request


get_principal = authenticate_request
