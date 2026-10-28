import pytest

from fip.platform.jobs.executor import JobExecutor, JobOutcome


def test_duplicate_handler_registration_is_rejected():
    executor = JobExecutor()
    executor.register("backtest", lambda _: JobOutcome.completed())

    with pytest.raises(ValueError, match="backtest"):
        executor.register("backtest", lambda _: JobOutcome.completed())


def test_unavailable_handler_produces_terminal_failure():
    outcome = JobExecutor().outcome_for("unknown")

    assert outcome.status == "FAILED"
    assert outcome.error_code == "HANDLER_UNAVAILABLE"


def test_job_outcomes_preserve_result_and_error_fields():
    completed = JobOutcome.completed("/api/v1/backtests/BT-1/result")
    blocked = JobOutcome.blocked("DATA_BLOCKED", "quality gate")
    failed = JobOutcome.failed("ENGINE_ERROR", "boom")

    assert completed.result_ref == "/api/v1/backtests/BT-1/result"
    assert blocked.status == "BLOCKED" and blocked.error_code == "DATA_BLOCKED"
    assert failed.status == "FAILED" and failed.error_message == "boom"


def test_running_chunk_releases_lease_without_finishing():
    from datetime import UTC, datetime
    from types import SimpleNamespace

    now = datetime.now(UTC)
    job = SimpleNamespace(
        job_type="chunk",
        status="RUNNING",
        result_ref="existing",
        error_code=None,
        error_detail=None,
        last_error_at=None,
        finished_at=None,
        claimed_by="worker",
        lease_expires_at=now,
    )
    from contextlib import nullcontext

    session = SimpleNamespace(flush=lambda: None, begin_nested=nullcontext)
    executor = JobExecutor({"chunk": lambda _: JobOutcome.running()})
    executor.claim_one = lambda *_: job

    outcome = executor.execute_one(session, "worker", now)

    assert outcome.status == "RUNNING"
    assert job.finished_at is None
    assert job.claimed_by is None and job.lease_expires_at is None
    assert job.result_ref == "existing"


def test_handler_exception_releases_claim_and_keeps_job_running():
    from datetime import UTC, datetime
    from types import SimpleNamespace

    class Session:
        def begin_nested(self):
            from contextlib import nullcontext

            return nullcontext()

        def flush(self):
            pass

    now = datetime.now(UTC)
    job = SimpleNamespace(
        job_type="broken",
        status="RUNNING",
        result_ref="ref",
        error_code=None,
        error_detail=None,
        last_error_at=None,
        finished_at=None,
        claimed_by="worker",
        lease_expires_at=now,
    )

    def broken(_):
        raise RuntimeError("provider persistence failed")

    executor = JobExecutor({"broken": broken})
    executor.claim_one = lambda *_: job
    outcome = executor.execute_one(Session(), "worker", now)
    assert outcome.status == "RUNNING" and outcome.error_code == "HANDLER_EXCEPTION"
    assert job.finished_at is None and job.claimed_by is None and job.lease_expires_at is None
