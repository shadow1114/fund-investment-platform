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
    assert principal == Principal("USR-1", ("reviewer",), True)
