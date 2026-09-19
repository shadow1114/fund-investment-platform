from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.jobs.models import CalculationJob
from fip.platform.jobs.submitter import JobSubmitter


@dataclass
class OperationRecord:
    operation_id: str
    kind: str
    resource_id: str
    status: str = "RUNNING"
    result_ref: str | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class OperationRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._by_key: dict[str, OperationRecord] = {}
        self._by_id: dict[str, OperationRecord] = {}

    def submit(self, kind: str, resource_id: str, idempotency_key: str) -> OperationRecord:
        with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is not None:
                return existing
            record = OperationRecord(
                operation_id=f"OP-{uuid.uuid4().hex[:12].upper()}",
                kind=kind,
                resource_id=resource_id,
            )
            self._by_key[idempotency_key] = record
            self._by_id[record.operation_id] = record
            return record

    def get(self, operation_id: str) -> OperationRecord | None:
        return self._by_id.get(operation_id)


class PersistentOperationService:
    """PostgreSQL-backed operation adapter used by command and polling routes."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def submit(
        self, kind: str, resource_id: str, idempotency_key: str, *, decision_id: str | None = None
    ) -> OperationRecord:
        job = JobSubmitter(self._session).submit(
            job_type=kind, idempotency_key=idempotency_key, decision_id=decision_id
        )
        self._session.commit()
        return self._record(job, resource_id)

    def get(self, operation_id: str) -> OperationRecord | None:
        job = self._session.execute(
            select(CalculationJob).where(CalculationJob.execution_id == operation_id)
        ).scalar_one_or_none()
        return None if job is None else self._record(job, job.decision_id or "")

    @staticmethod
    def _record(job: CalculationJob, resource_id: str) -> OperationRecord:
        error = None
        if job.error_code or job.error_detail:
            error = {"code": job.error_code, "message": job.error_detail}
        return OperationRecord(
            operation_id=job.execution_id,
            kind=job.job_type,
            resource_id=resource_id,
            status=job.status,
            error=error,
            created_at=job.created_at,
        )
