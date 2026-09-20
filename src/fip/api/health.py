from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from fip.api.observability import MetricsRegistry

router = APIRouter()


def database_ready(engine: Any) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        return True
    except Exception:  # noqa: BLE001 -- readiness must not expose driver details
        return False


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(request: Request) -> JSONResponse:
    if database_ready(request.app.state.api_engine):
        return JSONResponse({"status": "ready"})
    return JSONResponse(
        status_code=503,
        content={
            "data": None,
            "meta": {"request_id": getattr(request.state, "request_id", None)},
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Database is not ready",
                "details": {},
            },
        },
    )


@router.get("/metrics")
def metrics(request: Request) -> PlainTextResponse:
    registry: MetricsRegistry = request.app.state.metrics
    return PlainTextResponse(registry.render(), media_type="text/plain; version=0.0.4")
