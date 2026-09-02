import threading

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

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


def test_concurrent_submission_of_the_same_key_returns_one_job(db_engine):
    """两个独立连接真正并发地提交同一幂等键，而非在单会话上顺序模拟。

    `db_session` fixture 用 `join_transaction_mode="create_savepoint"` 把
    全部动作纳入同一外层事务再回滚，同一连接上开第二个 session 不会产生
    真正的写冲突，测不到 IntegrityError 分支。这里绕开 db_session，直接
    从 db_engine 拿两个独立连接/会话，让两次 submit() 的 INSERT 真正在
    数据库层竞争同一条唯一索引。

    因为两边都会真正 commit（不在任何 fixture 的回滚范围内），测试结束
    后必须手工删除这条幂等键对应的行，避免污染同一会话内的后续用例。
    """
    idempotency_key = "ingest|concurrency-probe|subject|2020-01-01|2020-01-02"
    conn_a = db_engine.connect()
    conn_b = db_engine.connect()
    session_a = Session(bind=conn_a, future=True)
    session_b = Session(bind=conn_b, future=True)

    barrier = threading.Barrier(2)
    results: dict[str, CalculationJob | BaseException] = {}

    def worker(name: str, session: Session) -> None:
        try:
            barrier.wait(timeout=10)
            job = JobSubmitter(session).submit("ingest", idempotency_key)
            session.commit()
            results[name] = job
        except BaseException as exc:  # noqa: BLE001 -- 需要把子线程异常带回主线程
            results[name] = exc

    thread_a = threading.Thread(target=worker, args=("a", session_a))
    thread_b = threading.Thread(target=worker, args=("b", session_b))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=15)
    thread_b.join(timeout=15)

    try:
        for name, result in results.items():
            if isinstance(result, BaseException):
                raise AssertionError(
                    f"submit() 在线程 {name} 中抛出异常"
                ) from result

        job_a, job_b = results["a"], results["b"]
        assert job_a.execution_id == job_b.execution_id

        with db_engine.connect() as check_conn:
            count = check_conn.execute(
                select(func.count())
                .select_from(CalculationJob)
                .where(CalculationJob.idempotency_key == idempotency_key)
            ).scalar_one()
        assert count == 1
    finally:
        session_a.close()
        session_b.close()
        conn_a.close()
        conn_b.close()
        # 手工清理：这条记录真正 commit 到了 db_engine 指向的库，不在任何
        # fixture 的回滚范围内，留着会污染同一会话里的后续测试。
        with db_engine.connect() as cleanup_conn:
            cleanup_conn.execute(
                delete(CalculationJob).where(
                    CalculationJob.idempotency_key == idempotency_key
                )
            )
            cleanup_conn.commit()


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
