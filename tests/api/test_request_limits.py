from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.limits import LocalRateLimiter
from fip.settings import Settings


def test_page_size_above_configured_max_is_validation_error():
    runtime = Settings(database_url="sqlite://", max_page_size=10)
    with TestClient(create_app(settings_override=runtime)) as client:
        response = client.get("/api/v1/funds?page_size=11")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_default_page_size_limit_is_200_but_fund_ingestion_history_stays_at_100():
    runtime = Settings(database_url="sqlite://")
    assert runtime.max_page_size == 200
    with TestClient(create_app(settings_override=runtime)) as client:
        assert client.get("/api/v1/funds?page_size=201").status_code == 422
        assert client.get("/api/v1/fund-ingestions?page_size=101").status_code == 422
        assert (
            client.get("/api/v1/ingestions/test-operation/items?page_size=101").status_code == 422
        )


def test_rate_limit_is_429_with_retry_after():
    runtime = Settings(database_url="sqlite://", rate_limit_per_minute=1)
    app = create_app(settings_override=runtime)
    app.state.rate_limiter = LocalRateLimiter(1)
    with TestClient(app) as client:
        client.get("/api/v1/session", headers={"X-User-ID": "USR-1"})
        response = client.get("/api/v1/session", headers={"X-User-ID": "USR-1"})

    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["error"]["code"] == "RATE_LIMITED"
