from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from fip.api.errors import InvalidQueryError
from fip.services.data_service.models.governance import AuditLog


class DecisionCommandService:
    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def review(
        self,
        decision_id: str,
        action: str,
        reason: str | None,
        principal_id: str,
        original_weights: Any,
        final_weights: Any,
        request_id: str | None,
    ) -> dict[str, Any]:
        if action not in {"APPROVED", "REJECTED", "OVERRIDDEN"}:
            raise InvalidQueryError("action must be APPROVED, REJECTED, or OVERRIDDEN")
        if action == "OVERRIDDEN" and not reason:
            raise InvalidQueryError("reason is required for OVERRIDDEN reviews")
        audit_id = f"AUD-{decision_id}-{principal_id}"
        if self._session is not None:
            audit = AuditLog(
                resource_type="decision",
                resource_id=decision_id,
                action=action,
                operator=principal_id,
                detail={"reason": reason, "request_id": request_id},
            )
            self._session.add(audit)
            self._session.flush()
            audit_id = str(audit.id)
        return {
            "decision_id": decision_id,
            "decision_status": action,
            "reviewed_by": principal_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "original_weights": original_weights,
            "final_weights": final_weights,
            "audit_id": audit_id,
        }


def validate_backtest_configuration(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"start_date", "end_date", "universe_id"}
    missing = sorted(required - payload.keys())
    if missing:
        raise InvalidQueryError(f"Missing backtest fields: {', '.join(missing)}")
    if payload["start_date"] > payload["end_date"]:
        raise InvalidQueryError("start_date must not be after end_date")
    return {"validation_status": "PASS", "errors": []}
