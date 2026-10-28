from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, model_serializer

from fip.services.data_service.classification.models import ClassificationSnapshot


class ClassificationPayloadModel(ClassificationSnapshot):
    revision_id: int
    version: int
    valid_from: str
    valid_to: str | None = None
    available_at: str
    classified_at: str
    availability_quality: str
    source_summary: list[str]
    trading_eligibility: dict[str, Any]
    published_at: str | None = None
    provider_available_at: str | None = None
    ingested_at: str | None = None


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


class FundIngestionSubmissionModel(StrictModel):
    operation_id: str
    fund_id: str
    fund_ids: list[str]
    dataset: Literal["BASIC_INFO", "NAV"]
    status: Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED"]


class FundIngestionTaskModel(StrictModel):
    operation_id: str
    fund_id: str
    fund_ids: list[str]
    dataset: Literal["BASIC_INFO", "NAV"]
    source: str
    actor: str
    status: Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED"]
    task_status: Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED"] | None = None
    requested_count: int
    success_count: int | None = None
    failure_count: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    items: list[dict[str, Any]]
    failure: str | None = None


class FundBasicInfoHistoryModel(StrictModel):
    fund_id: str
    version: int
    raw_fields: dict[str, Any]
    normalized_fields: dict[str, Any]
    source: str
    adapter_version: str
    library_version: str
    available_at: datetime
    availability_quality: Literal["INFERRED"]


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

    classification: ClassificationPayloadModel | None = None
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


class UniverseListPayloadModel(ReadPayloadModel):
    pass


class PortfolioListPayloadModel(ReadPayloadModel):
    pass


class BacktestPayloadModel(ReadPayloadModel):
    pass


# Plan-7 strict domain payloads.  These classes intentionally sit beside the
# legacy common projection above until every route has been migrated to the
# operation registry; none of the domain models accepts arbitrary nested keys.
class FundSummaryModel(StrictModel):
    classification: ClassificationPayloadModel | None = None
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


class UniverseSummaryModel(StrictModel):
    universe_id: str
    strategy_id: str
    decision_at: str
    universe_strategy: Literal["A", "B", "UNKNOWN"]
    member_count: int
    eligibility_rules_version: str
    scoring_policy_version: str | None


class UniverseConditionModel(StrictModel):
    condition: str
    actual: Any
    result: Literal["PASS", "FAIL", "UNKNOWN"]
    gap: float | None = None


class UniverseMemberModel(StrictModel):
    fund_id: str
    selection_status: Literal["SELECTED", "REJECTED", "UNKNOWN"]
    total_score: float | None
    total_score_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    total_score_reason: str | None
    rank: int | None
    rank_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    rank_reason: str | None
    percentile: float | None
    percentile_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    percentile_reason: str | None
    fund_tier: str | None = None
    investment_eligibility: Literal[
        "FULLY_ELIGIBLE", "HOLD_ONLY", "LIMITED", "EXIT_ONLY", "NOT_TRADABLE", "UNKNOWN"
    ]
    passed_conditions: list[UniverseConditionModel]
    failed_conditions: list[UniverseConditionModel]


class UniverseModel(StrictModel):
    universe_id: str
    decision_at: str
    universe_strategy: Literal["A", "B", "UNKNOWN"]
    members: list[UniverseMemberModel]
    excluded: list[UniverseMemberModel]


class UniversePayloadModel(UniverseModel):
    pass


class PortfolioSummaryModel(StrictModel):
    portfolio_id: str
    portfolio_name: str
    portfolio_type: str
    status: Literal["DRAFT", "ACTIVE", "SUSPENDED", "CLOSED", "UNKNOWN"]
    base_currency: str
    portfolio_version: str


class PortfolioModel(PortfolioSummaryModel):
    risk_profile: str
    portfolio_benchmark: BenchmarkModel
    portfolio_rule_version: str


class PortfolioPayloadModel(PortfolioModel):
    pass


class WeightModel(StrictModel):
    fund_id: str
    weight: float


class OptimizationRequestModel(StrictModel):
    decision_at: str
    universe_id: str
    portfolio_rule_version: str
    return_estimate_version: str
    risk_model_version: str
    mode: Literal["REBALANCE"]


class OptimizationModel(StrictModel):
    optimization_id: str
    optimization_status: Literal[
        "OPTIMAL", "INFEASIBLE", "UNBOUNDED", "NOT_CONVERGED", "NUMERICAL_ERROR", "UNKNOWN"
    ]
    target_weights: list[WeightModel] | None
    objective_value: float | None
    objective_value_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    objective_value_reason: str | None
    binding_constraints: list[str]
    conflicting_constraints: list[str]
    shadow_prices: dict[str, float]
    post_optimization_risk: PostOptimizationRiskModel
    excluded_candidates: list[dict[str, str]]
    solve_path: str


class PostOptimizationRiskModel(StrictModel):
    portfolio_volatility: float | None
    portfolio_volatility_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    portfolio_volatility_reason: str | None


class OptimizationPayloadModel(OptimizationModel):
    pass


class DecisionReviewModel(StrictModel):
    action: Literal["APPROVED", "REJECTED", "OVERRIDDEN", "UNKNOWN"]
    reason: str
    reviewed_by: str
    reviewed_at: datetime


class DecisionModel(StrictModel):
    decision_id: str
    portfolio_id: str
    optimization_id: str
    decision_status: Literal[
        "PROPOSED", "APPROVED", "REJECTED", "OVERRIDDEN", "EXPIRED", "SUPERSEDED", "UNKNOWN"
    ]
    proposed_weights: list[WeightModel]
    review: DecisionReviewModel | None
    final_weights: list[WeightModel] | None


class DecisionPayloadModel(DecisionModel):
    pass


class MoneyModel(StrictModel):
    amount: str
    currency: str


class ValidationIssueModel(StrictModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class BacktestCreatedPayloadModel(StrictModel):
    backtest_id: str
    status: Literal["CREATED", "UNKNOWN"]
    created_at: datetime


class BacktestValidationModel(StrictModel):
    validation_result: Literal["PASS", "PASS_WITH_WARNINGS", "UNKNOWN"]
    warm_up_end_date: str
    effective_period: dict[str, str]
    in_sample_length_days: int
    out_of_sample_length_days: int
    warnings: list[ValidationIssueModel]
    blocking_issues: list[ValidationIssueModel]


class BacktestRunPayloadModel(StrictModel):
    operation_id: str
    backtest_id: str
    status: Literal["RUNNING", "UNKNOWN"]


class BacktestStatusProgressModel(StrictModel):
    current_decision_date: str | None
    completed_periods: int
    total_periods: int | None
    total_periods_is_estimate: bool


class BacktestStatusModel(StrictModel):
    backtest_id: str
    status: Literal[
        "CREATED",
        "VALIDATING_CONFIGURATION",
        "RUNNING",
        "VALIDATING_RESULTS",
        "COMPLETED",
        "FAILED",
        "INVALID",
        "CANCELLED",
        "ABORTED",
        "UNKNOWN",
    ]
    validation_status: Literal["VALID", "WARNING", "INVALID", "UNKNOWN"] | None
    progress: BacktestStatusProgressModel
    started_at: datetime | None


class PerformanceMetricsModel(StrictModel):
    total_return: float
    annualized_return: float
    volatility: float
    max_drawdown: float
    sharpe_ratio: float | None
    sharpe_ratio_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    sharpe_ratio_reason: str | None


class BacktestSummaryModel(StrictModel):
    portfolio: PerformanceMetricsModel
    benchmark: PerformanceMetricsModel
    equal_weight_baseline: PerformanceMetricsModel | None
    equal_weight_baseline_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    equal_weight_baseline_reason: str | None


class ExcessReturnModel(StrictModel):
    vs_benchmark: float | None
    vs_benchmark_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    vs_benchmark_reason: str | None
    vs_equal_weight: float | None
    vs_equal_weight_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    vs_equal_weight_reason: str | None


SignificanceStatus = Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]


class SignificanceLayerBaseModel(StrictModel):
    passed: bool | None
    passed_status: SignificanceStatus
    passed_reason: str | None


class StatisticalSignificanceLayerModel(SignificanceLayerBaseModel):
    bootstrap_ci_lower_vs_benchmark: float | None
    bootstrap_ci_lower_vs_benchmark_status: SignificanceStatus
    bootstrap_ci_lower_vs_benchmark_reason: str | None
    bootstrap_ci_lower_vs_equal_weight: float | None
    bootstrap_ci_lower_vs_equal_weight_status: SignificanceStatus
    bootstrap_ci_lower_vs_equal_weight_reason: str | None


class EffectSizeSignificanceLayerModel(SignificanceLayerBaseModel):
    ir_vs_benchmark: float | None
    ir_vs_benchmark_status: SignificanceStatus
    ir_vs_benchmark_reason: str | None
    ir_vs_equal_weight: float | None
    ir_vs_equal_weight_status: SignificanceStatus
    ir_vs_equal_weight_reason: str | None
    delta_sharpe_vs_benchmark: float | None
    delta_sharpe_vs_benchmark_status: SignificanceStatus
    delta_sharpe_vs_benchmark_reason: str | None
    delta_sharpe_vs_equal_weight: float | None
    delta_sharpe_vs_equal_weight_status: SignificanceStatus
    delta_sharpe_vs_equal_weight_reason: str | None


class RobustnessSignificanceLayerModel(SignificanceLayerBaseModel):
    outperform_ratio_vs_benchmark: float | None
    outperform_ratio_vs_benchmark_status: SignificanceStatus
    outperform_ratio_vs_benchmark_reason: str | None
    outperform_ratio_vs_equal_weight: float | None
    outperform_ratio_vs_equal_weight_status: SignificanceStatus
    outperform_ratio_vs_equal_weight_reason: str | None


class EconomicSignificanceLayerModel(SignificanceLayerBaseModel):
    annualized_return_improvement_vs_benchmark: float | None
    annualized_return_improvement_vs_benchmark_status: SignificanceStatus
    annualized_return_improvement_vs_benchmark_reason: str | None
    annualized_return_improvement_vs_equal_weight: float | None
    annualized_return_improvement_vs_equal_weight_status: SignificanceStatus
    annualized_return_improvement_vs_equal_weight_reason: str | None
    max_drawdown_improvement_vs_benchmark: float | None
    max_drawdown_improvement_vs_benchmark_status: SignificanceStatus
    max_drawdown_improvement_vs_benchmark_reason: str | None
    max_drawdown_improvement_vs_equal_weight: float | None
    max_drawdown_improvement_vs_equal_weight_status: SignificanceStatus
    max_drawdown_improvement_vs_equal_weight_reason: str | None


class SignificanceLayersModel(StrictModel):
    statistical: StatisticalSignificanceLayerModel
    effect_size: EffectSizeSignificanceLayerModel
    robustness: RobustnessSignificanceLayerModel
    economic: EconomicSignificanceLayerModel


class SignificanceVerdictModel(StrictModel):
    overall: Literal["SIGNIFICANT", "NOT_SIGNIFICANT", "CANNOT_DETERMINE", "UNKNOWN"]
    thresholds_status: Literal["CALIBRATED", "PENDING_CALIBRATION", "UNKNOWN"]
    layers: SignificanceLayersModel


class BacktestResultModel(StrictModel):
    backtest_id: str
    status: str
    validation_status: Literal["VALID", "WARNING", "INVALID", "UNKNOWN"]
    backtest_mode: Literal["HISTORICAL_FIDELITY", "CURRENT_RULE", "UNKNOWN"]
    period: dict[str, str]
    initial_capital: MoneyModel
    final_value: MoneyModel
    summary: BacktestSummaryModel
    excess_return: ExcessReturnModel
    significance_verdict: SignificanceVerdictModel
    validation_summary: dict[str, list[str]]


class BacktestResultPayloadModel(BacktestResultModel):
    pass


class SeriesPointModel(StrictModel):
    date: str
    value: float | int | str | None
    value_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    value_reason: str | None


class CumulativeReturnSeriesModel(StrictModel):
    portfolio: list[SeriesPointModel]
    benchmark: list[SeriesPointModel]
    equal_weight_baseline: list[SeriesPointModel] | None
    equal_weight_baseline_status: Literal["VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN"]
    equal_weight_baseline_reason: str | None


class BacktestSeriesModel(StrictModel):
    portfolio_value: list[SeriesPointModel]
    cumulative_return: CumulativeReturnSeriesModel
    drawdown: list[SeriesPointModel]
    rolling_sharpe: list[SeriesPointModel]
    rolling_excess_return: list[SeriesPointModel]


class BacktestPerformanceModel(StrictModel):
    segment: Literal["FULL", "IN_SAMPLE", "OUT_OF_SAMPLE", "UNKNOWN"]
    series: BacktestSeriesModel


class BiasCheckModel(StrictModel):
    status: Literal["PASS", "FAIL", "NOT_VERIFIED", "PARTIALLY_MODELED", "NOT_MODELED", "UNKNOWN"]
    violations: list[str] | None = None
    reason: str | None = None
    affected_periods: int | None = None
    availability_quality_distribution: dict[str, float] | None = None
    unmodeled_costs: list[str] | None = None


class PointInTimeBiasCheckModel(BiasCheckModel):
    availability_quality_distribution: dict[str, float]


class TransactionCostBiasCheckModel(BiasCheckModel):
    unmodeled_costs: list[str]


class BacktestBiasChecksModel(StrictModel):
    look_ahead_bias: BiasCheckModel
    survivorship_bias: BiasCheckModel
    tradability_bias: BiasCheckModel
    point_in_time: PointInTimeBiasCheckModel
    transaction_cost: TransactionCostBiasCheckModel
    subscription_redemption_lag: BiasCheckModel


class BacktestBiasCheckModel(StrictModel):
    backtest_id: str
    checks: BacktestBiasChecksModel
    snapshot_summary: dict[str, Any]
    data_limitations: list[str]


class BacktestBiasCheckPayloadModel(BacktestBiasCheckModel):
    pass


class PositionViewModel(StrictModel):
    fund_id: str
    state: str
    shares: float
    cost_basis: float
    market_price: float
    market_value: float
    weight: float
    holding_days: int


class LivePortfolioViewModel(StrictModel):
    portfolio_id: str
    as_of_date: str
    status: str
    cash_balance: float
    total_equity: float
    has_pending_execution: bool
    target_positions: list[PositionViewModel]
    pending_positions: list[PositionViewModel]
    actual_positions: list[PositionViewModel]
    last_rebalanced_at: str | None = None


class ExecutionReportRequest(StrictModel):
    report_id: str
    fund_id: str
    direction: Literal["BUY", "SELL"]
    requested_shares: float
    filled_shares: float
    filled_price: float
    fee: float = 0.0
    status: Literal["SUBMITTED", "PARTIALLY_FILLED", "FILLED", "REJECTED", "EXPIRED"]
    rebalance_id: str | None = None


class ExecutionReportResponse(StrictModel):
    report_id: str
    portfolio_id: str
    status: str
    has_pending_execution: bool
    total_equity: float
    cash_balance: float


class EvaluateRebalanceRequest(StrictModel):
    decision_at: str
    prices: dict[str, float]
    fund_drift_threshold: float = 0.03
    category_drift_threshold: float = 0.05
    min_trade_threshold: float = 0.005
    fee_rate: float = 0.0015
    expected_annualized_improvement: float = 0.02


class RebalanceTradeViewModel(StrictModel):
    fund_id: str
    direction: str
    target_weight: float
    current_weight: float
    weight_delta: float
    target_shares: float
    delta_shares: float
    estimated_amount: float
    eligibility_status: str
    is_filtered: bool
    unachieved_reason: str | None = None


class RebalanceProposalViewModel(StrictModel):
    is_triggered: bool
    trigger_types: list[str]
    primary_trigger: str | None
    recompute_scope: str | None
    decision_outcome: str
    turnover: float
    estimated_cost: float
    expected_improvement: float
    trades: list[RebalanceTradeViewModel]
    unachieved_targets: dict[str, str]
    explainability_summary: str
