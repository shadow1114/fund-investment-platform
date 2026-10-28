import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fip.api.app import create_app
from fip.services.data_service.models.fund import Fund

pytestmark = pytest.mark.integration


def test_preview_freezes_unmapped_fund_and_submission_is_idempotent(db_engine):
    with Session(db_engine) as session:
        session.add(
            Fund(fund_code="SCOPE-UNMAPPED", product_name="Unmapped", grouping_status="CONFIRMED")
        )
        session.commit()
    app = create_app(persistent_operations=True, strict_contracts=True)
    app.state.api_engine = db_engine
    headers = {"X-Roles": "operations", "X-User-ID": "alice"}
    with TestClient(app) as client:
        preview = client.post(
            "/api/v1/fund-ingestion-previews",
            headers=headers,
            json={
                "dataset": "NAV",
                "scope": {"type": "SINGLE", "fund_id": "SCOPE-UNMAPPED"},
            },
        )
        assert preview.status_code == 200, preview.text
        data = preview.json()["data"]
        assert (data["fund_count"], data["unavailable_mapping_count"], data["subject_count"]) == (
            1,
            1,
            0,
        )
        assert "members" not in data
        key = {**headers, "Idempotency-Key": "stable-key"}
        submit = client.post(
            "/api/v1/fund-ingestion-jobs", headers=key, json={"preview_id": data["preview_id"]}
        )
        assert submit.status_code == 202, submit.text
        duplicate = client.post(
            "/api/v1/fund-ingestion-jobs", headers=key, json={"preview_id": data["preview_id"]}
        )
        assert duplicate.json()["data"]["operation_id"] == submit.json()["data"]["operation_id"]
        foreign = client.post(
            "/api/v1/fund-ingestion-jobs",
            headers={**key, "X-User-ID": "bob"},
            json={"preview_id": data["preview_id"]},
        )
        assert foreign.status_code == 403
        operation_id = submit.json()["data"]["operation_id"]
        progress = client.get(f"/api/v1/operations/{operation_id}", headers=headers).json()["data"][
            "progress"
        ]
        assert progress["total"] == 1
        items = client.get(f"/api/v1/ingestions/{operation_id}/items", headers=headers)
        assert items.status_code == 200
        assert items.json()["data"]["items"][0]["status"] == "SKIPPED"
        assert (
            client.get(
                f"/api/v1/ingestions/{operation_id}/items", headers={"X-User-ID": "bob"}
            ).status_code
            == 403
        )
        cancelled = client.post(f"/api/v1/ingestions/{operation_id}/cancel", headers=headers)
        assert cancelled.status_code == 202
    from sqlalchemy import select

    from fip.services.data_service.models.governance import AuditLog

    with Session(db_engine) as session:
        assert session.scalar(
            select(AuditLog.id).where(
                AuditLog.resource_id == operation_id, AuditLog.action == "CANCEL_REQUESTED"
            )
        )


def test_worker_persists_bounded_chunks_and_resumes(db_session, monkeypatch):
    from datetime import UTC, datetime

    from sqlalchemy import select

    from fip.platform.jobs.executor import JobContext
    from fip.platform.jobs.fund_ingestion import handle_fund_ingestion
    from fip.platform.jobs.models import CalculationJob
    from fip.services.data_service.models.fund import FundShareClass
    from fip.services.data_service.models.fund_ingestion import FundIngestionRunItem

    fund = Fund(fund_code="CHUNK", product_name="Chunk", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    job = CalculationJob(
        execution_id="chunk-test",
        idempotency_key="chunk-test",
        job_type="fund_nav_ingest",
        status="RUNNING",
        progress=0,
        job_payload={"dataset": "NAV", "actor": "alice", "scoped_items": True},
    )
    db_session.add(job)
    db_session.flush()
    for i in range(51):
        share = FundShareClass(
            fund_id=fund.id, share_class_code=str(i), display_name=str(i), base_currency="CNY"
        )
        db_session.add(share)
        db_session.flush()
        db_session.add(
            FundIngestionRunItem(
                operation_id=job.execution_id,
                fund_id=fund.id,
                public_fund_id="CHUNK",
                share_class_id=share.id,
                symbol=str(i),
                status="PENDING",
                attempts=0,
            )
        )
    db_session.flush()
    monkeypatch.setattr(
        "fip.platform.jobs.fund_ingestion._run_scoped_chunk",
        lambda context, subjects: [{"status": "SUCCESS"} for _ in subjects],
    )
    context = JobContext(job, db_session, "worker", datetime.now(UTC))
    assert handle_fund_ingestion(context).status == "RUNNING"
    assert job.progress == 50
    db_session.expire_all()
    assert handle_fund_ingestion(context).status == "COMPLETED"
    assert job.progress == 51
    assert all(
        item.status == "SUCCESS"
        for item in db_session.scalars(
            select(FundIngestionRunItem).where(
                FundIngestionRunItem.operation_id == job.execution_id
            )
        )
    )


def test_retry_copies_only_failures_and_history_is_scoped(db_engine):
    from fip.platform.jobs.models import CalculationJob
    from fip.services.data_service.models.fund_ingestion import FundIngestionRunItem

    with Session(db_engine) as session:
        fund = Fund(fund_code="RETRY", product_name="Retry", grouping_status="CONFIRMED")
        session.add(fund)
        session.flush()
        session.add(
            CalculationJob(
                execution_id="retry-parent",
                idempotency_key="retry-parent",
                job_type="fund_nav_ingest",
                status="FAILED",
                progress=1,
                job_payload={
                    "dataset": "NAV",
                    "actor": "alice",
                    "scope_type": "SINGLE",
                    "scoped_items": True,
                },
            )
        )
        session.flush()
        session.add(
            FundIngestionRunItem(
                operation_id="retry-parent",
                fund_id=fund.id,
                public_fund_id="RETRY",
                share_class_id=None,
                symbol=None,
                status="FAILED",
                attempts=1,
            )
        )
        session.commit()
    app = create_app(persistent_operations=True)
    app.state.api_engine = db_engine
    headers = {"X-Roles": "operations", "X-User-ID": "alice", "Idempotency-Key": "retry-key"}
    with TestClient(app) as client:
        retry = client.post("/api/v1/ingestions/retry-parent/retry-failed", headers=headers)
        assert retry.status_code == 202, retry.text
        child_id = retry.json()["data"]["operation_id"]
        detail = client.get(f"/api/v1/ingestions/{child_id}", headers=headers).json()["data"]
        assert detail["parent_operation_id"] == "retry-parent"
        assert (
            client.post("/api/v1/ingestions/retry-parent/retry-failed", headers=headers).json()[
                "data"
            ]["operation_id"]
            == child_id
        )
        page = client.get(f"/api/v1/ingestions/{child_id}/items", headers=headers).json()["data"]
        assert page["total"] == 1 and page["items"][0]["status"] == "PENDING"
        history = client.get("/api/v1/fund-ingestions", headers=headers)
        assert history.status_code == 200
        assert child_id in [item["operation_id"] for item in history.json()["data"]["items"]]


def test_changed_and_expired_preview_are_rejected(db_engine):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from fip.services.data_service.models.fund_ingestion import FundIngestionPreview

    with Session(db_engine) as session:
        session.add(Fund(fund_code="STALE", product_name="Stale", grouping_status="CONFIRMED"))
        session.commit()
    app = create_app(persistent_operations=True)
    app.state.api_engine = db_engine
    headers = {"X-Roles": "operations", "X-User-ID": "alice", "Idempotency-Key": "stale-key"}
    with TestClient(app) as client:
        request = {"dataset": "NAV", "scope": {"type": "SINGLE", "fund_id": "STALE"}}
        preview_id = client.post(
            "/api/v1/fund-ingestion-previews", headers=headers, json=request
        ).json()["data"]["preview_id"]
        with Session(db_engine) as session:
            preview = session.get(FundIngestionPreview, preview_id)
            preview.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
        assert (
            client.post(
                "/api/v1/fund-ingestion-jobs", headers=headers, json={"preview_id": preview_id}
            ).status_code
            == 409
        )
        preview_id = client.post(
            "/api/v1/fund-ingestion-previews", headers=headers, json=request
        ).json()["data"]["preview_id"]
        with Session(db_engine) as session:
            fund = session.scalar(select(Fund).where(Fund.fund_code == "STALE"))
            fund.fund_code = "RENAMED"
            session.commit()
        assert (
            client.post(
                "/api/v1/fund-ingestion-jobs", headers=headers, json={"preview_id": preview_id}
            ).status_code
            == 409
        )


def test_cancel_marks_pending_items_and_preserves_success(db_session, monkeypatch):
    from datetime import UTC, datetime

    from fip.platform.jobs.executor import JobContext
    from fip.platform.jobs.fund_ingestion import handle_fund_ingestion
    from fip.platform.jobs.models import CalculationJob
    from fip.services.data_service.models.fund import FundShareClass
    from fip.services.data_service.models.fund_ingestion import FundIngestionRunItem

    fund = Fund(fund_code="CANCEL", product_name="Cancel", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    job = CalculationJob(
        execution_id="cancel-test",
        idempotency_key="cancel-test",
        job_type="fund_nav_ingest",
        status="RUNNING",
        progress=1,
        job_payload={
            "dataset": "NAV",
            "actor": "alice",
            "scoped_items": True,
            "cancel_requested": True,
        },
    )
    db_session.add(job)
    db_session.flush()
    for i, item_status in enumerate(["SUCCESS", "PENDING"]):
        share = FundShareClass(
            fund_id=fund.id, share_class_code=str(i), display_name=str(i), base_currency="CNY"
        )
        db_session.add(share)
        db_session.flush()
        db_session.add(
            FundIngestionRunItem(
                operation_id=job.execution_id,
                fund_id=fund.id,
                public_fund_id="CANCEL",
                share_class_id=share.id,
                symbol=str(i),
                status=item_status,
                attempts=0,
            )
        )
    db_session.flush()
    outcome = handle_fund_ingestion(JobContext(job, db_session, "w", datetime.now(UTC)))
    assert outcome.status == "CANCELLED"
    assert job.result_payload["success_count"] == 1
    assert job.result_payload["cancelled_count"] == 1


def test_full_universe_preview_requires_capability_and_returns_only_counts(db_engine):
    from fip.api.auth import get_principal
    from fip.api.context import Principal

    with Session(db_engine) as session:
        session.add(
            Fund(fund_code="UNIVERSE", product_name="Universe", grouping_status="CONFIRMED")
        )
        session.commit()
    app = create_app(persistent_operations=True, strict_contracts=True)
    app.state.api_engine = db_engine
    principal = Principal("admin", ("admin",), True, True, True, True)
    app.dependency_overrides[get_principal] = lambda: principal
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/fund-ingestion-previews", json={"dataset": "NAV", "scope": {"type": "ALL"}}
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["scope_type"] == "ALL" and data["fund_count"] >= 1
        assert "members" not in data and "fund_ids" not in data
        submitted = client.post(
            "/api/v1/fund-ingestion-jobs",
            headers={"Idempotency-Key": "universe-key"},
            json={"preview_id": data["preview_id"]},
        )
        assert submitted.status_code == 202, submitted.text
        assert submitted.json()["data"]["fund_ids"] == []
