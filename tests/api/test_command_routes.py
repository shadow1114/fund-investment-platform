from fastapi.testclient import TestClient

from fip.api.app import create_app


def test_optimization_submission_is_async_and_idempotent() -> None:
    client = TestClient(create_app())
    headers = {"Idempotency-Key": "optimization-1"}
    payload = {
        "decision_at": "2025-01-01",
        "universe_id": "U-1",
        "portfolio_rule_version": "p1",
        "return_estimate_version": "r1",
        "risk_model_version": "risk1",
        "mode": "REBALANCE",
    }
    first = client.post("/api/v1/portfolios/P-1/optimizations", json=payload, headers=headers)
    second = client.post("/api/v1/portfolios/P-1/optimizations", json=payload, headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["data"]["operation_id"] == second.json()["data"]["operation_id"]

    operation_id = first.json()["data"]["operation_id"]
    polled = client.get(f"/api/v1/operations/{operation_id}")
    assert polled.status_code == 200
    assert polled.json()["data"]["status"] == "RUNNING"


def test_override_review_requires_reviewer_and_reason() -> None:
    client = TestClient(create_app())
    denied = client.post(
        "/api/v1/decisions/D-1/review",
        json={"decision_status": "OVERRIDDEN"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN"

    invalid = client.post(
        "/api/v1/decisions/D-1/review",
        json={"decision_status": "OVERRIDDEN"},
        headers={"X-Roles": "reviewer"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
