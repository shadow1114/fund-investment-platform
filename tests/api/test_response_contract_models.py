from __future__ import annotations

import pytest
from pydantic import ValidationError

from fip.api.schemas import (
    EvaluationPayloadModel,
    FundPayloadModel,
    ScorePayloadModel,
)


def valid_fund_payload() -> dict[str, object]:
    return {
        "fund_id": "000001",
        "fund_name": "Demo Fund",
        "share_class": "A",
        "fund_classification": "EQUITY",
        "management_company_id": "MGR-1",
        "inception_date": "2020-01-01",
        "lifecycle_status": "NORMAL",
        "investment_eligibility": "FULLY_ELIGIBLE",
        "classification_version": "v1",
        "manager_ids": ["MAN-1"],
        "benchmark": {
            "benchmark_id": "BM-1",
            "benchmark_name": "CSI 300",
            "benchmark_type": "INDEX",
            "mapping_version": "v1",
            "components": [{"benchmark_id": "000300", "weight": 1.0}],
        },
        "fee_structure": [
            {
                "expense_type": "MANAGEMENT",
                "expense_rate": 0.01,
                "included_in_nav": "TRUE",
                "included_in_backtest": True,
                "inclusion_source": "PROSPECTUS",
            }
        ],
    }


def valid_evaluation_payload() -> dict[str, object]:
    return {
        "fund_id": "000001",
        "evaluation_period": "2024",
        "as_of_date": "2024-12-31",
        "evaluation_status": "PARTIAL",
        "evaluation_profile": "DEFAULT",
        "data_completeness": {"available": 1, "expected": 2},
        "factor_results": [
            {
                "factor_id": "RETURN_1Y",
                "window": "1Y",
                "raw_value": None,
                "normalized_value": None,
                "status": "UNAVAILABLE",
                "reason_code": "INSUFFICIENT_HISTORY",
                "direction": "HIGHER_IS_BETTER",
            }
        ],
    }


def valid_score_payload() -> dict[str, object]:
    return {
        "fund_id": "000001",
        "evaluation_period": "2024",
        "as_of_date": "2024-12-31",
        "total_score": None,
        "total_score_status": "UNAVAILABLE",
        "total_score_reason": "INSUFFICIENT_HISTORY",
        "sub_scores": {
            "return_score": None,
            "return_score_status": "UNAVAILABLE",
            "return_score_reason": "INSUFFICIENT_HISTORY",
            "risk_score": 1.0,
            "risk_score_status": "VALID",
            "risk_score_reason": None,
            "risk_adjusted_score": 1.0,
            "risk_adjusted_score_status": "VALID",
            "risk_adjusted_score_reason": None,
            "stability_score": 1.0,
            "stability_score_status": "VALID",
            "stability_score_reason": None,
            "relative_performance_score": 1.0,
            "relative_performance_score_status": "VALID",
            "relative_performance_score_reason": None,
        },
        "attribution": [],
        "data_completeness": {"available": 1, "expected": 2},
        "score_status": "PARTIAL",
    }


def test_fund_rejects_unknown_nested_benchmark_field() -> None:
    payload = valid_fund_payload()
    benchmark = payload["benchmark"]
    assert isinstance(benchmark, dict)
    benchmark["unexpected"] = "nope"
    with pytest.raises(ValidationError):
        FundPayloadModel.model_validate(payload)


def test_evaluation_preserves_unavailable_metric_reason() -> None:
    model = EvaluationPayloadModel.model_validate(valid_evaluation_payload())
    assert model.factor_results[0].status == "UNAVAILABLE"
    assert model.factor_results[0].reason_code == "INSUFFICIENT_HISTORY"


def test_score_models_nested_subscores_and_attribution() -> None:
    model = ScorePayloadModel.model_validate(valid_score_payload())
    assert model.sub_scores.return_score is None
    assert model.total_score_reason == "INSUFFICIENT_HISTORY"
