from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any


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
