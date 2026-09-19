from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from fip.services.data_service.models.governance import AuditLog


class AuditWriter:
    """Small application boundary for governance audit persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def review(
        self,
        *,
        decision_id: str,
        actor: str,
        action: str,
        reason: str,
        request_id: str | None,
        details: dict[str, Any] | None = None,
    ) -> str:
        audit = AuditLog(
            resource_type="decision",
            resource_id=decision_id,
            action=action,
            operator=actor,
            detail={"reason": reason, "request_id": request_id, **(details or {})},
        )
        self.session.add(audit)
        self.session.flush()
        return str(audit.id)
