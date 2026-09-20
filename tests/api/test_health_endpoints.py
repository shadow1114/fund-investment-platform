from types import SimpleNamespace

from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.settings import Settings


def _offline_app():
    settings = Settings(database_url="sqlite://")
    app = create_app(settings_override=settings)
    app.state.api_engine = SimpleNamespace(connect=lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    return app


def test_liveness_does_not_require_database():
    with TestClient(_offline_app()) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_503_when_database_is_unavailable():
    with TestClient(_offline_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
