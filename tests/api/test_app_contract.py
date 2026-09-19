from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from fip.api.app import create_app


def _frozen_spec() -> dict[str, object]:
    return yaml.safe_load((Path(__file__).parents[2] / "frontend/openapi/m17.yaml").read_text())


def test_app_exposes_every_frozen_path_and_method() -> None:
    app = create_app()
    expected = _frozen_spec()["paths"]
    actual = {
        route.path: {method.lower() for method in route.methods or set()}
        for route in app.routes
        if route.path.startswith("/api/v1/")
    }
    assert actual == {
        path: set(methods)
        for path, methods in expected.items()  # type: ignore[union-attr]
    }


def test_session_returns_frozen_success_envelope() -> None:
    response = TestClient(create_app()).get("/api/v1/session")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data", "meta", "error"}
    assert body["error"] is None
    assert {"user_id", "roles", "capabilities"} <= set(body["data"])
    assert body["data"]["capabilities"]["can_review_decisions"] is False
    assert body["meta"]["api_version"] == "v1"
