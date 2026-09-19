from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, model_serializer


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
    as_of_date: str
    data_version: str
    versions: dict[str, str]
    is_point_in_time: bool
    availability_quality_distribution: dict[str, float]
    pagination: PaginationModel | None = None


class PaginationModel(StrictModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


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


class BacktestRunModel(StrictModel):
    operation_id: str
    backtest_id: str
    status: Literal["RUNNING", "UNKNOWN"]


class OperationModel(StrictModel):
    operation_id: str
    status: Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED", "UNKNOWN"]
    progress: OperationProgress | None
    result_ref: str | None
    failure: OperationFailure | None


class OperationProgress(StrictModel):
    completed: int
    total: int | None
    unit: str


class OperationFailure(StrictModel):
    code: str
    message: str


class MetricTriple(StrictModel):
    value: float | None
    status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    reason: str | None


class DataCompleteness(StrictModel):
    available: int
    expected: int


class ReadPayloadModel(BaseModel):
    """Typed common projection shared by frozen read resources.

    Resource-specific fields remain available through the explicit extension
    surface, while identifiers, statuses, nullable metrics, and completeness
    blocks are validated at the HTTP boundary.
    """

    model_config = ConfigDict(extra="allow")

    fund_id: str | None = None
    universe_id: str | None = None
    portfolio_id: str | None = None
    optimization_id: str | None = None
    decision_id: str | None = None
    backtest_id: str | None = None
    operation_id: str | None = None
    status: str | None = None
    validation_status: str | None = None
    evaluation_status: str | None = None
    score_status: str | None = None
    selection_status: Literal["SELECTED", "REJECTED", "UNKNOWN"] | None = None
    metric_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"] | None = None
    data_completeness: DataCompleteness | None = None

    @model_serializer(mode="wrap")
    def serialize_present_fields(self, handler):  # type: ignore[no-untyped-def]
        value = handler(self)
        return {
            key: item
            for key, item in value.items()
            if key in self.model_fields_set or item is not None
        }


class SuccessEnvelopeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ReadPayloadModel | list[ReadPayloadModel]
    meta: ResponseMetaModel
    error: None = None


T = TypeVar("T")


class TypedEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    data: T
    meta: ResponseMetaModel
    error: None = None


class ReadEnvelopeModel(SuccessEnvelopeModel):
    """Strict envelope used by all frozen read endpoints."""
