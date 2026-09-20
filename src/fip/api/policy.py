from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fip.api.context import Principal
from fip.api.errors import AuthenticationError, ForbiddenError


def _value(resource: object, name: str, default: Any = None) -> Any:
    if isinstance(resource, Mapping):
        return resource.get(name, default)
    return getattr(resource, name, default)


class ResourcePolicy:
    """Centralized resource visibility and mutation policy for API routes."""

    @staticmethod
    def _is_admin(principal: Principal) -> bool:
        return any(role.lower() in {"admin", "administrator"} for role in principal.roles)

    def can_read(self, principal: Principal, resource_type: str, resource: object) -> bool:
        if self._is_admin(principal) or resource_type not in {
            "portfolio",
            "decision",
            "optimization",
            "backtest",
        }:
            return True
        owner = _value(resource, "owner_user_id")
        viewers = _value(resource, "viewer_user_ids", [])
        return principal.user_id == owner or principal.user_id in (viewers or [])

    def can_write(self, principal: Principal, resource_type: str, resource: object) -> bool:
        if self._is_admin(principal):
            return True
        return self.can_read(principal, resource_type, resource) and principal.user_id == _value(
            resource, "owner_user_id"
        )


def require_read_access(principal: Principal | None, resource_type: str, resource: object) -> None:
    if principal is None:
        raise AuthenticationError("A verified identity is required")
    if not ResourcePolicy().can_read(principal, resource_type, resource):
        raise ForbiddenError()


def require_write_access(principal: Principal | None, resource_type: str, resource: object) -> None:
    if principal is None:
        raise AuthenticationError("A verified identity is required")
    if not ResourcePolicy().can_write(principal, resource_type, resource):
        raise ForbiddenError()
