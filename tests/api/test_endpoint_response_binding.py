from __future__ import annotations

import pytest

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


def test_company_options_operation_is_strictly_bound() -> None:
    models = _route_models()
    binding = models["listFundManagementCompanies"]
    data_annotation = binding.__pydantic_fields__["data"].annotation
    assert "FundManagementCompanyPayloadModel" in str(data_annotation)


def test_strict_runtime_field_uses_the_same_model_as_the_route_contract() -> None:
    app = create_app(strict_contracts=True)
    for operation_id in ("listFunds", "listFundManagementCompanies"):
        route = next(
            route
            for route in app.routes
            if getattr(route, "operation_id", None) == operation_id
        )
        assert route.secure_cloned_response_field.type_ is route.response_model


def test_fund_list_payload_accepts_new_list_fields_and_nullable_company() -> None:
    from pydantic import ValidationError

    payload = FundListPayloadModel.model_validate(
        {
            "fund_id": "F-001",
            "fund_name": "示例基金",
            "share_class": "A",
            "fund_classification": "UNKNOWN",
            "management_company_id": None,
            "inception_date": "2020-01-01",
            "lifecycle_status": "UNKNOWN",
            "investment_eligibility": "UNKNOWN",
            "share_class_id": "101",
            "fund_code": "000001",
            "fund_company": None,
            "sub_status": "开放",
            "manager_ids": [],
        }
    )

    assert payload.fund_company is None
    assert payload.share_class_id == "101"
    assert payload.fund_code == "000001"
    assert FundListPayloadModel.model_validate(
        {
            **payload.model_dump(),
            "sub_status": "UNKNOWN",
        }
    ).sub_status == "UNKNOWN"
    with pytest.raises(ValidationError):
        FundListPayloadModel.model_validate(
            {
                "fund_id": "F-001",
                "fund_name": "示例基金",
                "share_class": "A",
                "fund_classification": "UNKNOWN",
                "management_company_id": None,
                "inception_date": None,
                "lifecycle_status": "UNKNOWN",
                "investment_eligibility": "UNKNOWN",
                "share_class_id": "101",
                "fund_code": "１２３４５６",
                "fund_company": None,
                "sub_status": "开放",
                "manager_ids": [],
            }
        )


def test_list_only_fields_do_not_widen_generic_read_payload() -> None:
    from pydantic import ValidationError

    from fip.api.schemas import ReadPayloadModel

    assert not {"share_class_id", "fund_code", "fund_company", "sub_status"} & set(
        ReadPayloadModel.model_fields
    )
    with pytest.raises(ValidationError):
        ReadPayloadModel.model_validate({"share_class_id": "101"})


def test_list_funds_strict_meta_recognizes_subscription_status_source() -> None:
    from pydantic import ValidationError

    from fip.api.schemas import FundListMetaModel

    fields = {
        "generated_at": "2026-11-03T00:00:00Z",
        "as_of_date": "2026-11-03",
        "data_version": "api-v1",
        "versions": {},
        "is_point_in_time": False,
        "availability_quality_distribution": {
            "EXACT": 0,
            "DERIVED": 0,
            "INFERRED": 0,
        },
        "pagination": {"page": 1, "page_size": 20, "total_items": 1, "total_pages": 1},
        "subscription_status_source": "PLACEHOLDER",
    }
    meta = FundListMetaModel.model_validate(fields)

    assert meta.subscription_status_source == "PLACEHOLDER"
    with pytest.raises(ValidationError):
        FundListMetaModel.model_validate(
            {**fields, "subscription_status_source": "LIVE_PROVIDER"}
        )
