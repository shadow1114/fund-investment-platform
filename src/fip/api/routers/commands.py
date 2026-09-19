from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Request, status
from sqlalchemy.orm import Session

from fip.api.context import principal_from_request
from fip.api.contracts import success
from fip.api.errors import ApiError, ForbiddenError
from fip.api.operations import OperationRegistry, PersistentOperationService

# FastAPI's dependency/body declarations intentionally live in signatures.
# ruff: noqa: B008

router = APIRouter()
registry = OperationRegistry()


def _submit_operation(
    request: Request,
    kind: str,
    resource_id: str,
    idempotency_key: str,
) -> Any:
    if getattr(request.app.state, "persistent_operations", False):
        session = Session(request.app.state.api_engine, future=True)
        try:
            return PersistentOperationService(session).submit(kind, resource_id, idempotency_key)
        finally:
            session.close()
    return registry.submit(kind, resource_id, idempotency_key)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _key(request: Request) -> str:
    return request.headers.get("Idempotency-Key", f"request:{uuid.uuid4().hex}")


@router.post(
    "/portfolios/{id}/optimizations",
    operation_id="submitOptimization",
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_optimization(
    id: str, request: Request, payload: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    optimization_id = f"OPT-{uuid.uuid4().hex[:12].upper()}"
    record = _submit_operation(request, "optimization", optimization_id, _key(request))
    return success(
        {
            "operation_id": record.operation_id,
            "optimization_id": record.resource_id,
            "status": record.status,
        },
        request_id=_request_id(request),
    )


@router.post("/backtests", operation_id="createBacktest", status_code=status.HTTP_201_CREATED)
def create_backtest(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    backtest_id = f"BT-{uuid.uuid4().hex[:12].upper()}"
    return success(
        {"backtest_id": backtest_id, "status": "CREATED"}, request_id=_request_id(request)
    )


@router.post("/backtests/{id}/validate-configuration", operation_id="validateBacktest")
def validate_backtest(
    id: str, request: Request, payload: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    return success(
        {"backtest_id": id, "validation_status": "PASS"}, request_id=_request_id(request)
    )


@router.post(
    "/backtests/{id}/runs", operation_id="runBacktest", status_code=status.HTTP_202_ACCEPTED
)
def run_backtest(id: str, request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    record = _submit_operation(request, "backtest", id, _key(request))
    return success(
        {"operation_id": record.operation_id, "backtest_id": id, "status": record.status},
        request_id=_request_id(request),
    )


@router.post("/decisions/{decision_id}/review", operation_id="reviewDecision")
def review_decision(
    decision_id: str,
    request: Request,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    principal = principal_from_request(request)
    if not principal.can_review_decisions:
        raise ForbiddenError()
    decision_status = payload.get("decision_status")
    if decision_status not in {"APPROVED", "REJECTED", "OVERRIDDEN"}:
        raise ApiError(
            422, "VALIDATION_ERROR", "decision_status must be APPROVED, REJECTED, or OVERRIDDEN"
        )
    if decision_status == "OVERRIDDEN" and not payload.get("reason"):
        raise ApiError(422, "VALIDATION_ERROR", "reason is required for OVERRIDDEN reviews")
    return success(
        {
            "decision_id": decision_id,
            "decision_status": decision_status,
            "reviewed_by": principal.user_id,
            "reason": payload.get("reason"),
            "original_weights": payload.get("original_weights", {}),
            "final_weights": payload.get("final_weights", {}),
        },
        request_id=_request_id(request),
        audit_id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
    )
