from fastapi.testclient import TestClient

from fip.api.app import create_app


def test_preview_rejects_all_without_capability_and_invalid_scope():
    app = create_app(persistent_operations=True)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/fund-ingestion-previews",
            json={"dataset": "NAV", "scope": {"type": "ALL"}},
            headers={"X-Roles": "operations"},
        )
        invalid = client.post(
            "/api/v1/fund-ingestion-previews",
            json={"dataset": "NAV", "scope": {"type": "SELECTED", "fund_ids": ["one"]}},
            headers={"X-Roles": "operations"},
        )
    assert response.status_code == 403
    assert invalid.status_code == 422


def test_history_time_range_is_typed_and_rejects_reversed_bounds():
    app = create_app(persistent_operations=True)
    schema = app.openapi()["paths"]["/api/v1/fund-ingestions"]["get"]
    names = {parameter.get("name") for parameter in schema["parameters"]}
    assert {"created_from", "created_to"} <= names
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/fund-ingestions",
            params={"created_from": "2026-10-29T00:00:00Z", "created_to": "2026-10-28T00:00:00Z"},
            headers={"X-Roles": "operations"},
        )
    assert response.status_code == 422
