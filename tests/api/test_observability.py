from fastapi.testclient import TestClient

from fip.api.app import create_app


def test_metrics_expose_bounded_http_counters():
    with TestClient(create_app()) as client:
        client.get("/health/live")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "fip_http_requests_total" in response.text
    assert "route=\"/health/live\"" in response.text
