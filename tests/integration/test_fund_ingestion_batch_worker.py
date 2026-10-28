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
        other_manager = {
            "X-Roles": "operations",
            "X-User-ID": "bob",
            "Idempotency-Key": "bob-retry-key",
        }
        for path in (
            f"/api/v1/ingestions/{operation_id}",
            f"/api/v1/ingestions/{operation_id}/items",
            f"/api/v1/operations/{operation_id}",
        ):
            assert client.get(path, headers=other_manager).status_code == 403
        for action in ("cancel", "retry-failed"):
            assert (
                client.post(
                    f"/api/v1/ingestions/{operation_id}/{action}", headers=other_manager
                ).status_code
                == 403
            )
        history = client.get("/api/v1/fund-ingestions", headers=other_manager).json()["data"]
        assert operation_id not in [item["operation_id"] for item in history["items"]]
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


def test_filtered_all_includes_matching_fund_without_share_classes(db_engine):
    from fip.api.auth import get_principal
    from fip.api.context import Principal

    with Session(db_engine) as session:
        session.add(
            Fund(
                fund_code="NO-SHARES", product_name="No shares unique", grouping_status="CONFIRMED"
            )
        )
        session.commit()
    app = create_app(persistent_operations=True)
    app.state.api_engine = db_engine
    app.dependency_overrides[get_principal] = lambda: Principal(
        "alice", (), False, False, True, True
    )
    with TestClient(app) as client:
        preview = client.post(
            "/api/v1/fund-ingestion-previews",
            json={
                "dataset": "NAV",
                "scope": {"type": "ALL", "filters": {"fund_name": "No shares unique"}},
            },
        )
        assert preview.status_code == 200
        data = preview.json()["data"]
        assert data["fund_count"] == 1 and data["unavailable_mapping_count"] == 1
        job = client.post(
            "/api/v1/fund-ingestion-jobs",
            headers={"Idempotency-Key": "no-shares"},
            json={"preview_id": data["preview_id"]},
        )
        assert job.status_code == 202
        items = client.get(f"/api/v1/ingestions/{job.json()['data']['operation_id']}/items")
        assert items.json()["data"]["items"][0]["status"] == "SKIPPED"


def test_snapshot_lock_blocks_concurrent_catalogue_writes(db_engine):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from fip.api.routers.fund_ingestions import _lock_scope_sources

    with Session(db_engine) as snapshot_session, Session(db_engine) as editor:
        _lock_scope_sources(snapshot_session)
        editor.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(OperationalError):
            editor.execute(
                text(
                    "INSERT INTO fund.fund (fund_code, product_name, grouping_status) "
                    "VALUES ('LOCK-TEST', 'Lock test', 'CONFIRMED')"
                )
            )
        editor.rollback()
        editor.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(OperationalError):
            editor.execute(
                text(
                    "UPDATE fund.provider_fund_identity "
                    "SET provider_fund_id = provider_fund_id WHERE false"
                )
            )
        editor.rollback()
        snapshot_session.rollback()


def test_cancel_waits_for_worker_and_conflicts_if_job_finished(db_engine):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import select

    from fip.platform.jobs.models import CalculationJob

    with Session(db_engine) as seed:
        seed.add(
            CalculationJob(
                execution_id="cancel-race",
                idempotency_key="cancel-race",
                job_type="fund_nav_ingest",
                status="RUNNING",
                progress=0,
                job_payload={"dataset": "NAV", "actor": "alice", "scoped_items": True},
            )
        )
        seed.commit()
    app = create_app(persistent_operations=True)
    app.state.api_engine = db_engine
    headers = {"X-Roles": "operations", "X-User-ID": "alice"}
    with TestClient(app) as client, Session(db_engine) as worker, ThreadPoolExecutor() as pool:
        job = worker.scalar(
            select(CalculationJob)
            .where(CalculationJob.execution_id == "cancel-race")
            .with_for_update()
        )
        future = pool.submit(client.post, "/api/v1/ingestions/cancel-race/cancel", headers=headers)
        import time

        time.sleep(0.2)
        assert not future.done()
        job.status = "COMPLETED"
        worker.commit()
        assert future.result(timeout=5).status_code == 409


def test_raw_store_error_rolls_back_chunk_and_worker_can_resume(db_session, monkeypatch):
    from datetime import UTC, datetime

    from sqlalchemy import select

    from fip.platform.jobs.executor import JobExecutor
    from fip.platform.jobs.fund_ingestion import handle_fund_ingestion
    from fip.platform.jobs.models import CalculationJob
    from fip.services.data_service.models.fund import FundShareClass
    from fip.services.data_service.models.fund_ingestion import FundIngestionRunItem

    class ProviderError(Exception):
        record = object()

    class Adapter:
        def fetch(self, dataset, **params):
            raise ProviderError("fetch failed")

    class Service:
        def __init__(self, session, adapter, policy):
            self.adapter = adapter

        def ingest_fund_overview(self, fund_id, symbol, actor):
            self.adapter.fetch("basic", symbol=symbol)

        def _store_raw(self, record):
            raise RuntimeError("raw persistence unavailable")

    # Other tests in this module may have left unrelated claimable jobs in this isolated database.
    from sqlalchemy import update

    db_session.execute(
        update(CalculationJob).where(CalculationJob.status == "RUNNING").values(status="COMPLETED")
    )
    fund = Fund(fund_code="RAW-ERROR", product_name="Raw", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    share = FundShareClass(
        fund_id=fund.id, share_class_code="A", display_name="A", base_currency="CNY"
    )
    db_session.add(share)
    job = CalculationJob(
        execution_id="raw-error",
        idempotency_key="raw-error",
        job_type="fund_basic_info_ingest",
        status="RUNNING",
        progress=0,
        job_payload={"dataset": "BASIC_INFO", "actor": "alice", "scoped_items": True},
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(
        FundIngestionRunItem(
            operation_id=job.execution_id,
            fund_id=fund.id,
            public_fund_id=fund.fund_code,
            share_class_id=share.id,
            symbol="SYM",
            status="PENDING",
            attempts=0,
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        "fip.services.data_service.adapters.akshare.client.AkShareSourceAdapter", Adapter
    )
    monkeypatch.setattr("fip.services.data_service.ingest.IngestService", Service)
    executor = JobExecutor({"fund_basic_info_ingest": handle_fund_ingestion})
    first = executor.execute_one(db_session, "w1", datetime.now(UTC))
    assert first.status == "RUNNING" and first.error_code == "HANDLER_EXCEPTION"
    item = db_session.scalar(
        select(FundIngestionRunItem).where(FundIngestionRunItem.operation_id == "raw-error")
    )
    assert item.status == "PENDING" and item.attempts == 0
    monkeypatch.setattr(
        "fip.platform.jobs.fund_ingestion._run_scoped_chunk",
        lambda context, subjects: [{"status": "SUCCESS"} for _ in subjects],
    )
    assert executor.execute_one(db_session, "w2", datetime.now(UTC)).status == "COMPLETED"
    assert item.status == "SUCCESS" and item.attempts == 1


def test_basic_info_subprocess_timeout_is_recorded_as_retryable(db_session, monkeypatch):
    from datetime import UTC, datetime
    from subprocess import TimeoutExpired

    from sqlalchemy import select

    from fip.platform.jobs.executor import JobContext
    from fip.platform.jobs.fund_ingestion import handle_fund_ingestion
    from fip.platform.jobs.models import CalculationJob
    from fip.services.data_service.models.fund import FundShareClass
    from fip.services.data_service.models.fund_ingestion import FundIngestionRunItem

    class Adapter:
        pass

    class Service:
        def __init__(self, session, adapter, policy):
            pass

        def ingest_fund_overview(self, fund_id, symbol, actor):
            raise TimeoutExpired("akshare", 30)

    fund = Fund(fund_code="TIMEOUT", product_name="Timeout", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    share = FundShareClass(
        fund_id=fund.id, share_class_code="A", display_name="A", base_currency="CNY"
    )
    db_session.add(share)
    job = CalculationJob(
        execution_id="timeout",
        idempotency_key="timeout",
        job_type="fund_basic_info_ingest",
        status="RUNNING",
        progress=0,
        job_payload={"dataset": "BASIC_INFO", "actor": "alice", "scoped_items": True},
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(
        FundIngestionRunItem(
            operation_id=job.execution_id,
            fund_id=fund.id,
            public_fund_id=fund.fund_code,
            share_class_id=share.id,
            symbol="SYM",
            status="PENDING",
            attempts=0,
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        "fip.services.data_service.adapters.akshare.client.AkShareSourceAdapter", Adapter
    )
    monkeypatch.setattr("fip.services.data_service.ingest.IngestService", Service)
    assert (
        handle_fund_ingestion(JobContext(job, db_session, "worker", datetime.now(UTC))).status
        == "FAILED"
    )
    item = db_session.scalar(
        select(FundIngestionRunItem).where(FundIngestionRunItem.operation_id == "timeout")
    )
    assert item.status == "FAILED"
    assert (
        item.result["retryable"] is True
        and item.result["error_code"] == "PROVIDER_TEMPORARY_FAILURE"
    )
