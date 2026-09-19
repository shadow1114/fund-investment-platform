from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Request, status
from sqlalchemy.orm import Session

from fip.api.command_services import DecisionCommandService, validate_backtest_configuration
from fip.api.context import principal_from_request
from fip.api.contracts import success
from fip.api.errors import ForbiddenError, NotFoundError
from fip.api.operations import OperationRegistry, PersistentOperationService
from fip.services.portfolio_service.models import BacktestRecord, DecisionRecord, OptimizationRecord

# FastAPI's dependency/body declarations intentionally live in signatures.
# ruff: noqa: B008

router = APIRouter()
registry = OperationRegistry()


def _submit_operation(
    request: Request,
    kind: str,
    resource_id: str,
    idempotency_key: str,
    result_ref: str,
) -> Any:
    if getattr(request.app.state, "persistent_operations", False):
        session = Session(request.app.state.api_engine, future=True)
        try:
            return PersistentOperationService(session).submit(
                kind, resource_id, idempotency_key, result_ref=result_ref
            )
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
    if getattr(request.app.state, "persistent_operations", False):
        session = Session(request.app.state.api_engine, future=True)
        try:
            session.add(
                OptimizationRecord(
                    id=optimization_id,
                    portfolio_id=id,
                    payload={"optimization_status": "UNKNOWN", "request": payload},
                )
            )
            session.commit()
        finally:
            session.close()
    record = _submit_operation(
        request,
        "optimization",
        optimization_id,
        _key(request),
        f"/api/v1/portfolios/{id}/optimizations/{optimization_id}",
    )
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
    validate_backtest_configuration(payload)
    backtest_id = f"BT-{uuid.uuid4().hex[:12].upper()}"
    if getattr(request.app.state, "persistent_operations", False):
        session = Session(request.app.state.api_engine, future=True)
        try:
            session.add(BacktestRecord(id=backtest_id, status="CREATED", payload=payload))
            session.commit()
        finally:
            session.close()
    return success(
        {"backtest_id": backtest_id, "status": "CREATED", "created_at": datetime.now(UTC)},
        request_id=_request_id(request),
    )


@router.post("/backtests/{id}/validate-configuration", operation_id="validateBacktest")
def validate_backtest(
    id: str, request: Request, payload: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    result = validate_backtest_configuration(payload)
    return success({"backtest_id": id, **result}, request_id=_request_id(request))


@router.post(
    "/backtests/{id}/runs", operation_id="runBacktest", status_code=status.HTTP_202_ACCEPTED
)
def run_backtest(id: str, request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    record = _submit_operation(
        request, "backtest", id, _key(request), f"/api/v1/backtests/{id}/result"
    )
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
    session = (
        Session(request.app.state.api_engine, future=True)
        if getattr(request.app.state, "persistent_operations", False)
        else None
    )
    try:
        action = str(payload.get("action", payload.get("decision_status", "")))
        original_weights: Any = payload.get("proposed_weights", [])
        if session is not None:
            snapshot = session.get(DecisionRecord, decision_id)
            if snapshot is None:
                raise NotFoundError("decision", decision_id)
            original_weights = snapshot.payload.get("proposed_weights", [])
        final_weights: Any = (
            payload.get("overridden_weights")
            if action == "OVERRIDDEN"
            else original_weights
            if action == "APPROVED"
            else None
        )
        result = DecisionCommandService(session).review(
            decision_id,
            action,
            payload.get("reason"),
            principal.user_id,
            original_weights,
            final_weights,
            _request_id(request),
        )
        if session is not None:
            snapshot = session.get(DecisionRecord, decision_id)
            if snapshot is None:
                raise NotFoundError("decision", decision_id)
            snapshot.payload = {
                **snapshot.payload,
                "decision_status": result["decision_status"],
                "review": {
                    "action": result["decision_status"],
                    "reason": result["reason"],
                    "reviewed_by": result["reviewed_by"],
                    "reviewed_at": result["reviewed_at"],
                },
                "final_weights": result["final_weights"],
            }
            session.commit()
    finally:
        if session is not None:
            session.close()
    audit_id = result.pop("audit_id")
    return success(result, request_id=_request_id(request), audit_id=audit_id)
