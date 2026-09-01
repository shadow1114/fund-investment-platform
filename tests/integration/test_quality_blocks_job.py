from decimal import Decimal

import pytest

from fip.platform.jobs.models import ExecutionStatus
from fip.platform.jobs.submitter import JobSubmitter
from fip.services.data_service.quality import evaluate_batch_quality

pytestmark = pytest.mark.integration


def _apply(job, verdict):
    """把质量判定映射到 Job 状态。

    Global 阻断 → BLOCKED（不是 FAILED）：它不是系统故障，
    自动重试只会反复撞同一堵墙（01-system-architecture §10.5.4）。
    """
    if verdict.is_globally_blocked:
        job.status = ExecutionStatus.BLOCKED.value
        job.error_code = "DATA_QUALITY_GLOBAL_BLOCK"
    else:
        job.status = ExecutionStatus.COMPLETED.value
    return job


def test_global_block_marks_job_blocked_not_failed(db_session):
    job = JobSubmitter(db_session).submit("ingest", "ingest|q|global|2020-01-01|2020-01-02")
    verdict = evaluate_batch_quality(list(range(1, 101)), list(range(1, 51)),
                                     [], Decimal("0.95"))
    _apply(job, verdict)
    db_session.flush()
    assert job.status == ExecutionStatus.BLOCKED.value
    assert JobSubmitter.is_retryable(job) is False


def test_fund_level_issue_does_not_block_the_job(db_session):
    job = JobSubmitter(db_session).submit("ingest", "ingest|q|fund|2020-01-01|2020-01-02")
    verdict = evaluate_batch_quality(list(range(1, 101)), list(range(2, 101)),
                                     [], Decimal("0.95"))
    _apply(job, verdict)
    db_session.flush()
    assert job.status == ExecutionStatus.COMPLETED.value
    assert verdict.blocked_share_class_ids == frozenset({1})
