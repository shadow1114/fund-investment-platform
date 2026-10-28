from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from fip.platform.jobs.models import CalculationJob, ExecutionStatus


@dataclass(frozen=True)
class JobContext:
    job: CalculationJob
    session: Session
    worker_id: str
    now: datetime


@dataclass(frozen=True)
class JobOutcome:
    status: str
    result_ref: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def running(cls) -> JobOutcome:
        return cls(ExecutionStatus.RUNNING.value)

    @classmethod
    def completed(cls, result_ref: str | None = None) -> JobOutcome:
        return cls(ExecutionStatus.COMPLETED.value, result_ref=result_ref)

    @classmethod
    def blocked(cls, code: str, message: str) -> JobOutcome:
        return cls(ExecutionStatus.BLOCKED.value, error_code=code, error_message=message)

    @classmethod
    def failed(cls, code: str, message: str) -> JobOutcome:
        return cls(ExecutionStatus.FAILED.value, error_code=code, error_message=message)


JobHandler = Callable[[JobContext], JobOutcome]


class JobExecutor:
    def __init__(
        self,
        handlers: Mapping[str, JobHandler] | None = None,
        *,
        lease_seconds: int = 60,
    ) -> None:
        self._handlers: dict[str, JobHandler] = dict(handlers or {})
        self._lease_seconds = lease_seconds

    def register(self, job_type: str, handler: JobHandler) -> None:
        if job_type in self._handlers:
            raise ValueError(f"handler already registered for {job_type}")
        self._handlers[job_type] = handler

    def outcome_for(self, job_type: str, context: JobContext | None = None) -> JobOutcome:
        handler = self._handlers.get(job_type)
        if handler is None:
            return JobOutcome.failed("HANDLER_UNAVAILABLE", f"No handler registered for {job_type}")
        if context is None:
            raise ValueError("context is required for a registered handler")
        return handler(context)

    def claim_one(self, session: Session, worker_id: str, now: datetime) -> CalculationJob | None:
        stmt = (
            select(CalculationJob)
            .where(
                CalculationJob.status == ExecutionStatus.RUNNING.value,
                or_(
                    CalculationJob.lease_expires_at.is_(None),
                    CalculationJob.lease_expires_at <= now,
                ),
            )
            .order_by(CalculationJob.created_at, CalculationJob.id)
            .with_for_update(skip_locked=True)
        )
        job = session.execute(stmt).scalars().first()
        if job is None:
            return None
        job.claimed_by = worker_id
        job.lease_expires_at = now + timedelta(seconds=self._lease_seconds)
        if job.started_at is None:
            job.started_at = now
        session.flush()
        return job

    def execute_one(self, session: Session, worker_id: str, now: datetime) -> JobOutcome | None:
        job = self.claim_one(session, worker_id, now)
        if job is None:
            return None
        context = JobContext(job=job, session=session, worker_id=worker_id, now=now)
        try:
            with session.begin_nested():
                outcome = self.outcome_for(job.job_type, context)
        except Exception as error:
            outcome = JobOutcome(
                ExecutionStatus.RUNNING.value,
                error_code="HANDLER_EXCEPTION",
                error_message=f"{type(error).__name__}: {error}",
            )
        job.status = outcome.status
        if outcome.result_ref is not None:
            job.result_ref = outcome.result_ref
        job.error_code = outcome.error_code
        job.error_detail = outcome.error_message
        job.last_error_at = now if outcome.error_code else None
        job.finished_at = now if outcome.status != ExecutionStatus.RUNNING.value else None
        job.claimed_by = None
        job.lease_expires_at = None
        session.flush()
        return outcome
