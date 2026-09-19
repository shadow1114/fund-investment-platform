from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from fip.api.app import create_app


class _FakeService:
    def __init__(self, _session: object) -> None:
        pass

    def submit(self, kind: str, resource_id: str, key: str):
        return SimpleNamespace(
            operation_id=f"OP-{key}",
            kind=kind,
            resource_id=resource_id,
            status="RUNNING",
            error=None,
        )

    def get(self, operation_id: str):
        return SimpleNamespace(
            operation_id=operation_id,
            kind="optimization",
            resource_id="OPT-1",
            status="COMPLETED",
            error=None,
        )


def test_persistent_mode_uses_job_service_for_submit_and_poll(monkeypatch) -> None:
    monkeypatch.setattr("fip.api.routers.commands.PersistentOperationService", _FakeService)
    monkeypatch.setattr("fip.api.routers.operations.PersistentOperationService", _FakeService)
    app = create_app(persistent_operations=True)
    with TestClient(app) as client:
        submitted = client.post(
            "/api/v1/portfolios/P-1/optimizations",
            json={},
            headers={"Idempotency-Key": "stable"},
        )
        polled = client.get("/api/v1/operations/OP-stable")
    assert submitted.status_code == 202
    assert submitted.json()["data"]["operation_id"] == "OP-stable"
    assert polled.status_code == 200
    assert polled.json()["data"]["status"] == "COMPLETED"
