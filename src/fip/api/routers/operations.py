from __future__ import annotations

from fastapi import APIRouter, Request

from fip.api.contracts import success
from fip.api.errors import NotFoundError
from fip.api.routers.commands import registry

router = APIRouter()


@router.get("/operations/{operation_id}", operation_id="getOperation")
def get_operation(operation_id: str, request: Request) -> dict[str, object]:
    record = registry.get(operation_id)
    if record is None:
        raise NotFoundError("operation", operation_id)
    data: dict[str, object] = {
        "operation_id": record.operation_id,
        "status": record.status,
        "progress": {"completed": 0, "total": 1, "unit": "operation"},
        "result_ref": record.result_ref,
        "failure": record.error,
    }
    return success(data, request_id=getattr(request.state, "request_id", None))
