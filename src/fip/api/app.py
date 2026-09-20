from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.utils import create_model_field
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from fip.api.contracts import ErrorBody, ErrorEnvelope, ResponseMeta
from fip.api.errors import ApiError
from fip.api.routers import commands, operations, reads
from fip.api.schemas import (
    BacktestPayloadModel,
    DecisionPayloadModel,
    EvaluationPayloadModel,
    FundListPayloadModel,
    FundPayloadModel,
    NavSeriesPayloadModel,
    OptimizationPayloadModel,
    PortfolioListPayloadModel,
    PortfolioPayloadModel,
    ScorePayloadModel,
    SessionPayloadModel,
    TypedEnvelope,
    UniverseListPayloadModel,
    UniversePayloadModel,
)
from fip.settings import settings


def _frozen_openapi() -> dict[str, Any]:
    import yaml

    path = Path(__file__).parents[3] / "frontend" / "openapi" / "m17.yaml"
    return cast(dict[str, Any], yaml.safe_load(path.read_text()))


def create_api_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def create_app(
    *,
    settings_override: Any | None = None,
    persistent_operations: bool = False,
    strict_contracts: bool = False,
) -> FastAPI:
    runtime_settings = settings_override or settings
    engine = create_api_engine(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Fund Investment Platform M1.7 Frontend API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.api_engine = engine
    app.state.settings = runtime_settings
    app.state.persistent_operations = persistent_operations

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        body = ErrorEnvelope(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                details=exc.details if isinstance(exc.details, dict) else {},
            ),
            meta=ResponseMeta(request_id=getattr(request.state, "request_id", None)),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorEnvelope(
            error=ErrorBody(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": exc.errors()},
            ),
            meta=ResponseMeta(request_id=getattr(request.state, "request_id", None)),
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    app.include_router(reads.router, prefix="/api/v1")
    app.include_router(commands.router, prefix="/api/v1")
    app.include_router(operations.router, prefix="/api/v1")
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.response_model_exclude_none = True
    if strict_contracts:
        models: dict[str, object] = {
            "getSession": SessionPayloadModel,
            "listFunds": list[FundListPayloadModel],
            "getFund": FundPayloadModel,
            "getFundNavSeries": NavSeriesPayloadModel,
            "getFundEvaluations": EvaluationPayloadModel,
            "getFundScores": ScorePayloadModel,
            "listUniverses": list[UniverseListPayloadModel],
            "getUniverse": UniversePayloadModel,
            "listPortfolios": list[PortfolioListPayloadModel],
            "getPortfolio": PortfolioPayloadModel,
            "getOptimization": OptimizationPayloadModel,
            "getDecision": DecisionPayloadModel,
            "getBacktestStatus": BacktestPayloadModel,
            "getBacktestResult": BacktestPayloadModel,
            "getBacktestPerformance": BacktestPayloadModel,
            "getBacktestBiasCheck": BacktestPayloadModel,
        }
        for route in app.routes:
            operation_id = getattr(route, "operation_id", None)
            if isinstance(route, APIRoute) and operation_id in models:
                model_type: Any = models[operation_id]
                envelope = TypedEnvelope[model_type]
                route.response_model = envelope
                route.response_field = create_model_field(
                    name=f"Response_{route.unique_id}", type_=envelope, mode="serialization"
                )

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = _frozen_openapi()
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


app = create_app(persistent_operations=True, strict_contracts=True)
