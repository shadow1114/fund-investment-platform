from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.dependencies import get_api_repositories
from fip.api.repositories import ApiRepositories


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_api_repositories] = lambda: ApiRepositories.from_session(object())
    return TestClient(app)


def test_empty_collections_are_successful_and_paginated() -> None:
    response = _client().get("/api/v1/funds?page=2&page_size=10")
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["pagination"] == {
        "page": 2,
        "page_size": 10,
        "total_items": 0,
        "total_pages": 0,
    }


def test_unknown_detail_uses_unified_error_envelope() -> None:
    response = _client().get("/api/v1/funds/000001")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["meta"]["api_version"] == "v1"
