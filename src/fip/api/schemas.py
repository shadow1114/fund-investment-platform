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

    model_config = ConfigDict(extra="forbid")

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
    id: str | None = None
    name: str | None = None
    user_id: str | None = None
    roles: list[str] | None = None
    capabilities: dict[str, bool] | None = None
    portfolio_name: str | None = None
    portfolio_type: str | None = None
    base_currency: str | None = None
    portfolio_version: str | None = None
    strategy_id: str | None = None
    decision_at: str | None = None
    universe_strategy: str | None = None
    member_count: int | None = None
    eligibility_rules_version: str | None = None
    scoring_policy_version: str | None = None
    points: list[dict[str, object]] | None = None
    members: list[dict[str, object]] | None = None
    excluded: list[dict[str, object]] | None = None
    progress: dict[str, object] | None = None
    result: dict[str, object] | None = None
    review: dict[str, object] | None = None
    target_weights: list[Weight] | None = None
    proposed_weights: list[Weight] | None = None
    final_weights: list[Weight] | None = None
    started_at: datetime | None = None
    nav_type: str | None = None
    adjustment_convention: str | None = None
    adjustment_rule_version: str | None = None
    unavailable_count: int | None = None
    date: str | None = None
    nav: float | None = None
    nav_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"] | None = None
    nav_reason: str | None = None
    owner_user_id: str | None = None
    viewer_user_ids: list[str] | None = None
    risk_profile: str | None = None
    portfolio_benchmark: dict[str, object] | None = None
    portfolio_rule_version: str | None = None
    fund_name: str | None = None
    fund_type: str | None = None
    inception_date: str | None = None
    aum: float | None = None
    lifecycle_status: str | None = None
    investment_eligibility: str | None = None
    classification_version: str | None = None
    manager_ids: list[str] | None = None
    benchmark: dict[str, object] | None = None
    fee_structure: list[dict[str, object]] | None = None
    share_class: str | None = None
    fund_classification: str | None = None
    management_company_id: str | None = None
    manager_id: str | None = None
    evaluation_period: str | None = None
    factor_results: list[dict[str, object]] | None = None
    sub_scores: dict[str, object] | None = None
    attribution: list[dict[str, object]] | None = None
    total_score: float | None = None
    total_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"] | None = None
    total_score_reason: str | None = None

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


class SessionPayloadModel(ReadPayloadModel):
    pass


class FundListPayloadModel(ReadPayloadModel):
    pass


class FundPayloadModel(ReadPayloadModel):
    pass


class NavSeriesPayloadModel(ReadPayloadModel):
    pass


class EvaluationPayloadModel(ReadPayloadModel):
    pass


class ScorePayloadModel(ReadPayloadModel):
    pass


class UniverseListPayloadModel(ReadPayloadModel):
    pass


class UniversePayloadModel(ReadPayloadModel):
    pass


class PortfolioListPayloadModel(ReadPayloadModel):
    pass


class PortfolioPayloadModel(ReadPayloadModel):
    pass


class OptimizationPayloadModel(ReadPayloadModel):
    pass


class DecisionPayloadModel(ReadPayloadModel):
    pass


class BacktestPayloadModel(ReadPayloadModel):
    pass


# Plan-7 strict domain payloads.  These classes intentionally sit beside the
# legacy common projection above until every route has been migrated to the
# operation registry; none of the domain models accepts arbitrary nested keys.
class FundSummaryModel(StrictModel):
    fund_id: str
    fund_name: str
    share_class: str
    fund_classification: str
    management_company_id: str
    inception_date: str
    lifecycle_status: Literal[
        "NORMAL", "SUSPENDED_SUBSCRIPTION", "LIQUIDATED", "MERGED", "TRANSFORMED", "UNKNOWN"
    ]
    investment_eligibility: Literal[
        "FULLY_ELIGIBLE", "HOLD_ONLY", "LIMITED", "EXIT_ONLY", "NOT_TRADABLE", "UNKNOWN"
    ]


class BenchmarkComponentModel(StrictModel):
    benchmark_id: str
    weight: float


class BenchmarkModel(StrictModel):
    benchmark_id: str
    benchmark_name: str
    benchmark_type: str
    mapping_version: str
    components: list[BenchmarkComponentModel] | None


class FeeModel(StrictModel):
    expense_type: str
    expense_rate: float
    included_in_nav: Literal["TRUE", "FALSE", "UNKNOWN"]
    included_in_backtest: bool
    inclusion_source: str


class FundModel(FundSummaryModel):
    classification_version: str
    manager_ids: list[str]
    benchmark: BenchmarkModel
    fee_structure: list[FeeModel]


class NavPointModel(StrictModel):
    date: str
    nav: float | None
    nav_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    nav_reason: str | None
    reason_code: str | None = None


class NavSeriesModel(StrictModel):
    fund_id: str
    points: list[NavPointModel]


class FactorResultModel(StrictModel):
    factor_id: str
    window: str
    raw_value: float | None
    normalized_value: float | None
    status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    reason_code: str | None
    direction: Literal["HIGHER_IS_BETTER", "LOWER_IS_BETTER", "UNKNOWN"]


class FundEvaluationModel(StrictModel):
    fund_id: str
    evaluation_period: str
    as_of_date: str
    evaluation_status: Literal["NOT_ELIGIBLE", "COMPLETED", "PARTIAL", "FAILED", "UNKNOWN"]
    evaluation_profile: str
    data_completeness: DataCompleteness
    factor_results: list[FactorResultModel]


class SubScoresModel(StrictModel):
    return_score: float | None
    return_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    return_score_reason: str | None
    risk_score: float | None
    risk_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    risk_score_reason: str | None
    risk_adjusted_score: float | None
    risk_adjusted_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    risk_adjusted_score_reason: str | None
    stability_score: float | None
    stability_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    stability_score_reason: str | None
    relative_performance_score: float | None
    relative_performance_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    relative_performance_score_reason: str | None


class ScoreAttributionModel(StrictModel):
    factor_id: str
    window: str | None = None
    raw_value: float | None
    normalized_value: float | None = None
    direction: Literal["HIGHER_IS_BETTER", "LOWER_IS_BETTER", "UNKNOWN"] | None = None
    status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    reason_code: str | None
    exclusion_reason: str | None = None
    effectiveness_verdict: Literal["VALID", "INVALID", "UNKNOWN"] | None = None
    weight: float
    original_weight: float | None = None
    weight_source: Literal["PROFILE_FIXED_V1", "OPTIMIZED", "UNKNOWN"] | None = None
    weighted_contribution: float | None = None
    sub_score: str | None = None
    reallocated_to: list[dict[str, float | str]] | None = None


class FundScoreModel(StrictModel):
    fund_id: str
    evaluation_period: str
    as_of_date: str
    total_score: float | None
    total_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    total_score_reason: str | None
    sub_scores: SubScoresModel
    attribution: list[ScoreAttributionModel]
    data_completeness: DataCompleteness
    score_status: Literal["COMPLETED", "PARTIAL", "VALIDATION_PENDING", "FAILED", "UNKNOWN"]


class FundListPayloadModel(FundSummaryModel):
    pass


class FundPayloadModel(FundModel):
    pass


class NavSeriesPayloadModel(NavSeriesModel):
    pass


class EvaluationPayloadModel(FundEvaluationModel):
    pass


class ScorePayloadModel(FundScoreModel):
    pass
