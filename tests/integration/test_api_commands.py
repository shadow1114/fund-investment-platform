from __future__ import annotations

from fip.api.command_services import DecisionCommandService
from fip.services.data_service.models.governance import AuditLog


def test_decision_review_persists_audit_row(db_session) -> None:
    result = DecisionCommandService(db_session).review(
        "D-API-1",
        "APPROVED",
        "reviewed against approved snapshot",
        "reviewer-1",
        [{"fund_id": "F-1", "weight": 1.0}],
        [{"fund_id": "F-1", "weight": 1.0}],
        "req-1",
    )
    db_session.flush()
    row = db_session.get(AuditLog, int(result["audit_id"]))
    assert row is not None
    assert row.resource_id == "D-API-1"
    assert row.action == "APPROVED"
    assert row.operator == "reviewer-1"
