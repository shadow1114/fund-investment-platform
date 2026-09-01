import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.jobs.models import CalculationJob, ExecutionStatus


def decision_idempotency_key(ctx: DecisionExecutionContext) -> str:
    """业务层幂等键（01-system-architecture §10.7）。

    键不含 decision_id —— 否则重复提交会因新 id 而产生新键，
    幂等失效。防的是『同一决策被重复计算』。
    """
    return (
        f"decision|{ctx.decision_at.isoformat()}|{ctx.strategy_version}"
        f"|{ctx.recompute_scope.value}"
    )


def ingest_idempotency_key(
    dataset: str, subject: str, date_from: dt.date, date_to: dt.date
) -> str:
    """灌数任务的幂等键，使长回补可断点续跑而不产生重复行。"""
    return f"ingest|{dataset}|{subject}|{date_from.isoformat()}|{date_to.isoformat()}"


# INFEASIBLE 是业务结果不是系统故障，不进入本表；BLOCKED 需人工修数据后重跑。
_RETRYABLE = {ExecutionStatus.FAILED}


class JobSubmitter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def submit(
        self,
        job_type: str,
        idempotency_key: str,
        decision_id: str | None = None,
    ) -> CalculationJob:
        """提交任务。相同幂等键的重复提交返回既有任务，不产生第二条记录。

        并发下也安全：`idempotency_key` 有数据库唯一约束兜底。先 SELECT
        是为常见的非并发路径省一次异常；真正撞上并发提交时，INSERT 会
        因唯一约束触发 IntegrityError —— 此时回滚到该次 INSERT 之前的
        SAVEPOINT，再按 idempotency_key 重新 SELECT 并返回胜出的既有行。
        若重新 SELECT 仍找不到该行，说明 IntegrityError 另有原因（例如
        其他约束冲突），此时必须重新抛出，不能静默吞掉。
        """
        existing = self._session.execute(
            select(CalculationJob).where(
                CalculationJob.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        job = CalculationJob(
            execution_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            job_type=job_type,
            decision_id=decision_id,
            status=ExecutionStatus.RUNNING.value,
            progress=0,
        )
        try:
            with self._session.begin_nested():
                self._session.add(job)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(CalculationJob).where(
                    CalculationJob.idempotency_key == idempotency_key
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return existing
        return job

    @staticmethod
    def is_retryable(job: CalculationJob) -> bool:
        """只有系统故障可幂等重试。

        把 BLOCKED（数据阻断）当作 FAILED 自动重试会反复撞同一堵墙；
        INFEASIBLE 属 Decision Status，根本不在本表（§10.5.4）。
        """
        return ExecutionStatus(job.status) in _RETRYABLE
