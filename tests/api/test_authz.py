from fastapi.testclient import TestClient

from fip.api.app import create_app


def test_development_header_auth_is_explicit() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/session", headers={"X-User-ID": "alice"})
    assert response.status_code == 200
    assert response.json()["data"]["user_id"] == "alice"


def test_production_requires_an_identity(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FIP_ENV", "production")
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/session")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_review_requires_reviewer_role() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/decisions/D-1/review",
            headers={"X-User-ID": "alice", "X-Roles": "Researcher"},
            json={"action": "APPROVED", "reason": "validated"},
        )
    assert response.status_code == 403


def test_session_exposes_maximum_development_capabilities_by_default() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/session")
    capabilities = response.json()["data"]["capabilities"]
    assert capabilities["can_review_decisions"] is True
    assert capabilities["can_review_classifications"] is True
    assert capabilities["can_manage_data_ingestion"] is True
    assert capabilities["can_manage_full_universe_ingestion"] is True
