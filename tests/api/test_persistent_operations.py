from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.operations import PersistentOperationService


class _FakeService:
    def __init__(self, _session: object) -> None:
        pass

    def submit(self, kind: str, resource_id: str, key: str, **_: object):
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


class _FakeSession:
    def get(self, _model, _identifier):
        return object()

    def execute(self, _statement):
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def add(self, _item):
        pass

    def commit(self):
        pass

    def close(self):
        pass


def test_persistent_mode_uses_job_service_for_submit_and_poll(monkeypatch) -> None:
    monkeypatch.setattr("fip.api.routers.commands.PersistentOperationService", _FakeService)
    monkeypatch.setattr("fip.api.routers.operations.PersistentOperationService", _FakeService)
    monkeypatch.setattr(
        "fip.api.routers.commands.Session", lambda *_args, **_kwargs: _FakeSession()
    )
    monkeypatch.setattr(
        "fip.api.routers.operations.Session", lambda *_args, **_kwargs: _FakeSession()
    )
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


def test_persistent_record_maps_terminal_failure_states() -> None:
    blocked = SimpleNamespace(
        execution_id="OP-BLOCKED",
        job_type="optimization",
        status="BLOCKED",
        error_code=None,
        error_detail=None,
        resource_id="OPT-1",
        result_ref=None,
        progress=0,
        created_at=None,
    )
    running = SimpleNamespace(
        execution_id="OP-RUNNING",
        job_type="optimization",
        status="RUNNING",
        error_code="STALE",
        error_detail="ignored",
        resource_id="OPT-1",
        result_ref=None,
        progress=2,
        created_at=None,
    )
    assert PersistentOperationService._record(blocked, "OPT-1").error == {
        "code": "DATA_BLOCKED",
        "message": "Operation blocked by data quality",
    }
    assert PersistentOperationService._record(running, "OPT-1").error is None
