from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from fip.api.contracts import success
from fip.api.errors import NotFoundError
from fip.api.operations import PersistentOperationService
from fip.api.routers.commands import registry
from fip.api.schemas import OperationModel, TypedEnvelope

router = APIRouter()


@router.get(
    "/operations/{operation_id}",
    operation_id="getOperation",
    response_model=TypedEnvelope[OperationModel],
)
def get_operation(operation_id: str, request: Request) -> dict[str, object]:
    session: Session | None = None
    if getattr(request.app.state, "persistent_operations", False):
        session = Session(request.app.state.api_engine, future=True)
        try:
            record = PersistentOperationService(session).get(operation_id)
        finally:
            session.close()
    else:
        record = registry.get(operation_id)
    if record is None:
        raise NotFoundError("operation", operation_id)
    data: dict[str, object] = {
        "operation_id": record.operation_id,
        "status": record.status,
        "progress": {
            "completed": getattr(record, "progress", 0),
            "total": None,
            "unit": "operation",
        },
        "result_ref": getattr(record, "result_ref", None),
        "failure": (
            {
                "code": record.error.get("code", "OPERATION_FAILED"),
                "message": record.error.get("message") or "Operation did not complete successfully",
            }
            if record.error
            else None
        ),
    }
    return success(data, request_id=getattr(request.state, "request_id", None))
