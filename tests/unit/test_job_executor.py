
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
