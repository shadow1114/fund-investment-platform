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
        # Only verified upstream middleware may establish this state. Raw
        # headers and bearer tokens are deliberately rejected here.
        verified = getattr(request.state, "verified_principal", None)
        if not isinstance(verified, Principal):
            raise AuthenticationError("A verified identity is required")
        return verified
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
