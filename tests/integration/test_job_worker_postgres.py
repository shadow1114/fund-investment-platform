from datetime import UTC, datetime, timedelta

import pytest

from fip.platform.jobs.executor import JobExecutor, JobOutcome
from fip.platform.jobs.models import CalculationJob

pytestmark = pytest.mark.integration


def _job(session, *, key: str, claimed_by: str | None = None, expired: bool = False):
    job = CalculationJob(
        execution_id=f"OP-{key}",
        idempotency_key=f"worker|{key}",
        job_type="backtest",
        status="RUNNING",
        progress=0,
        claimed_by=claimed_by,
        lease_expires_at=(datetime.now(UTC) - timedelta(minutes=1)) if expired else None,
    )
    session.add(job)
    session.flush()
    return job


def test_failed_handler_is_persisted_as_failed_not_completed(db_session):
    _job(db_session, key="failed")
    executor = JobExecutor({"backtest": lambda _: JobOutcome.failed("ENGINE_ERROR", "boom")})

    outcome = executor.execute_one(db_session, "worker-a", datetime.now(UTC))
    db_session.flush()
    job = db_session.query(CalculationJob).filter_by(idempotency_key="worker|failed").one()

    assert outcome is not None and outcome.status == "FAILED"
    assert job.status == "FAILED"
    assert job.error_code == "ENGINE_ERROR"


def test_expired_lease_can_be_reclaimed(db_session):
    job = _job(db_session, key="reclaim", claimed_by="dead-worker", expired=True)

    claimed = JobExecutor().claim_one(db_session, "worker-b", datetime.now(UTC))

    assert claimed is not None and claimed.execution_id == job.execution_id
    assert claimed.claimed_by == "worker-b"
