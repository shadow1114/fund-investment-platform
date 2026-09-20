from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import Request

from fip.api.context import Principal
from fip.api.errors import AuthenticationError


class VerifiedPrincipalProvider:
    """Replaceable boundary for upstream HTTP authentication middleware."""

    def resolve(self, request: Request) -> Principal | None:
        principal = getattr(request.state, "verified_principal", None)
        return principal if isinstance(principal, Principal) else None


def resolve_principal(request: Request) -> Principal:
    """Resolve a principal; the development header mechanism is never production auth."""
    runtime = getattr(getattr(request.app, "state", None), "settings", None)
    environment = os.getenv("FIP_ENV", getattr(runtime, "environment", "development")).lower()
    if environment == "production":
        verified = VerifiedPrincipalProvider().resolve(request)
        if verified is None:
            raise AuthenticationError("A verified identity is required")
        return verified
    user_id = request.headers.get("X-User-ID", "development-user")
    raw_roles = request.headers.get("X-Roles", "Researcher")
    roles = tuple(role.strip() for role in raw_roles.split(",") if role.strip())
    can_review = any(role.lower() in {"reviewer", "admin", "administrator"} for role in roles)
    return Principal(user_id, roles, can_review)


def authenticate_request(request: Request) -> Principal:
    return resolve_principal(request)


def principal_dependency() -> Callable[[Request], Principal]:
    """Return an injectable dependency factory for tests and future identity middleware."""
    return authenticate_request


get_principal = authenticate_request
