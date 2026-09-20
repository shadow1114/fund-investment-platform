from fastapi.testclient import TestClient

from fip.api.app import create_app


def test_invalid_query_uses_stable_validation_code():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/funds?page_size=0")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_not_found_error_keeps_resource_not_found_code():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/operations/NO-SUCH-OPERATION")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
