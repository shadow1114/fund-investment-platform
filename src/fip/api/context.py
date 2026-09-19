from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class Principal:
    user_id: str
    roles: tuple[str, ...]
    can_review_decisions: bool


def principal_from_request(request: Request) -> Principal:
    """Development principal; production auth middleware can replace this source."""
    user_id = request.headers.get("X-User-ID", "development-user")
    raw_roles = request.headers.get("X-Roles", "Researcher")
    roles = tuple(role.strip() for role in raw_roles.split(",") if role.strip())
    can_review = any(role.lower() in {"reviewer", "admin", "administrator"} for role in roles)
    return Principal(user_id, roles, can_review)
