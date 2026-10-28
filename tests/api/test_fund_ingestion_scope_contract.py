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
