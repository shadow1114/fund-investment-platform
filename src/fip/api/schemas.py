from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Weight(StrictModel):
    fund_id: str
    weight: float


class ResponseMetaModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    api_version: str = "v1"
    request_id: str | None = None
    generated_at: datetime


class EmptyErrorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: None = None


class OptimizationSubmissionModel(StrictModel):
    operation_id: str
    status: Literal["RUNNING", "UNKNOWN"]
    optimization_id: str


class DecisionReviewOutcomeModel(StrictModel):
    decision_id: str
    decision_status: Literal["APPROVED", "REJECTED", "OVERRIDDEN", "UNKNOWN"]
    reviewed_by: str
    reviewed_at: datetime
    reason: str
    original_weights: list[Weight]
    final_weights: list[Weight] | None


class BacktestCreatedModel(StrictModel):
    backtest_id: str
    status: Literal["CREATED", "UNKNOWN"]
    created_at: datetime


class MetricTriple(StrictModel):
    value: float | None
    status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    reason: str | None


class DataCompleteness(StrictModel):
    available: int
    expected: int


class SuccessEnvelopeModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: Any
    meta: dict[str, Any]
    error: None = None
