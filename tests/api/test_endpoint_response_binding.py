from __future__ import annotations

from typing import get_args, get_origin

from fip.api.app import create_app
from fip.api.schemas import (
    BacktestBiasCheckPayloadModel,
    BacktestCreatedPayloadModel,
    BacktestPerformanceModel,
    BacktestResultPayloadModel,
    BacktestRunPayloadModel,
    BacktestStatusModel,
    BacktestValidationModel,
    DecisionPayloadModel,
    DecisionReviewOutcomeModel,
    EvaluationPayloadModel,
    FundListPayloadModel,
    FundPayloadModel,
    NavSeriesPayloadModel,
    OptimizationPayloadModel,
    OptimizationSubmissionModel,
    PortfolioListPayloadModel,
    PortfolioPayloadModel,
    ScorePayloadModel,
    UniverseListPayloadModel,
    UniversePayloadModel,
)


def _route_models() -> dict[str, object]:
    app = create_app(strict_contracts=True)
    return {
        route.operation_id: route.response_model
        for route in app.routes
        if getattr(route, "operation_id", None)
    }


def test_every_domain_operation_has_a_specific_response_model() -> None:
    models = _route_models()
    expected = {
        "listFunds": list[FundListPayloadModel],
        "getFund": FundPayloadModel,
        "getFundNavSeries": NavSeriesPayloadModel,
        "getFundEvaluations": EvaluationPayloadModel,
        "getFundScores": ScorePayloadModel,
        "listUniverses": list[UniverseListPayloadModel],
        "getUniverse": UniversePayloadModel,
        "listPortfolios": list[PortfolioListPayloadModel],
        "getPortfolio": PortfolioPayloadModel,
        "submitOptimization": OptimizationSubmissionModel,
        "getOptimization": OptimizationPayloadModel,
        "getDecision": DecisionPayloadModel,
        "reviewDecision": DecisionReviewOutcomeModel,
        "createBacktest": BacktestCreatedPayloadModel,
        "validateBacktest": BacktestValidationModel,
        "runBacktest": BacktestRunPayloadModel,
        "getBacktestStatus": BacktestStatusModel,
        "getBacktestResult": BacktestResultPayloadModel,
        "getBacktestPerformance": BacktestPerformanceModel,
        "getBacktestBiasCheck": BacktestBiasCheckPayloadModel,
    }
    for operation_id, item_type in expected.items():
        envelope = models[operation_id]
        data_annotation = envelope.__pydantic_fields__["data"].annotation
        assert data_annotation == item_type
