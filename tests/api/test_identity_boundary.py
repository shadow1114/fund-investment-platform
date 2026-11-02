from types import SimpleNamespace

import pytest
from starlette.requests import Request

from fip.api.auth import resolve_principal
from fip.api.context import Principal
from fip.api.errors import AuthenticationError


def _request(headers: dict[str, str], *, environment: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/session",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
        "client": ("test", 1),
        "root_path": "",
    }
    scope["app"] = SimpleNamespace(
        state=SimpleNamespace(
            settings=SimpleNamespace(
                environment=environment, require_verified_principal=environment == "production"
            )
        )
    )
    return Request(scope)


def test_production_rejects_development_headers():
    with pytest.raises(AuthenticationError):
        resolve_principal(
            _request({"X-User-ID": "USR-1", "X-Roles": "admin"}, environment="production")
        )


def test_development_headers_create_principal():
    principal = resolve_principal(
        _request({"X-User-ID": "USR-1", "X-Roles": "reviewer"}, environment="development")
    )
    assert principal == Principal("USR-1", ("reviewer",), True, True)


def test_development_default_principal_has_maximum_permissions():
    principal = resolve_principal(_request({}, environment="development"))
    assert principal.roles == ("Administrator",)
    assert principal.can_review_decisions is True
    assert principal.can_review_classifications is True
    assert principal.can_manage_data_ingestion is True
    assert principal.can_manage_full_universe_ingestion is True


def test_development_admin_has_full_universe_permission():
    principal = resolve_principal(_request({"X-Roles": "admin"}, environment="development"))
    assert principal.can_manage_full_universe_ingestion is True
