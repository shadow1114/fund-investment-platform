import pytest
from sqlalchemy import func, select

from fip.platform.jobs.models import CalculationJob, ExecutionStatus
from fip.platform.jobs.submitter import JobSubmitter

pytestmark = pytest.mark.integration


def test_duplicate_submission_returns_the_same_job(db_session):
    """重复投递不产生重复结果（NFR-REL-001）。"""
    submitter = JobSubmitter(db_session)
    first = submitter.submit("factor_calculation", "ingest|fund_nav|000001|2020-01-01|2020-12-31")
    second = submitter.submit("factor_calculation", "ingest|fund_nav|000001|2020-01-01|2020-12-31")
    assert first.execution_id == second.execution_id
    count = db_session.execute(select(func.count()).select_from(CalculationJob)).scalar_one()
    assert count == 1


def test_different_keys_create_separate_jobs(db_session):
    submitter = JobSubmitter(db_session)
    a = submitter.submit("ingest", "ingest|fund_nav|000001|2020-01-01|2020-12-31")
    b = submitter.submit("ingest", "ingest|fund_nav|000002|2020-01-01|2020-12-31")
    assert a.execution_id != b.execution_id


def test_new_job_starts_running(db_session):
    job = JobSubmitter(db_session).submit("ingest", "ingest|x|y|2020-01-01|2020-01-02")
    assert job.status == ExecutionStatus.RUNNING.value
    assert job.progress == 0


@pytest.mark.parametrize(
    ("status", "retryable"),
    [
        (ExecutionStatus.FAILED, True),       # 系统故障 → 幂等重试
        (ExecutionStatus.BLOCKED, False),     # 数据阻断 → 修数据后重跑，不自动重试
        (ExecutionStatus.COMPLETED, False),
        (ExecutionStatus.CANCELLED, False),
        (ExecutionStatus.RUNNING, False),
    ],
)
def test_only_system_failure_is_retryable(db_session, status, retryable):
    key = f"ingest|k|{status.value}|2020-01-01|2020-01-02"
    job = JobSubmitter(db_session).submit("ingest", key)
    job.status = status.value
    assert JobSubmitter.is_retryable(job) is retryable
