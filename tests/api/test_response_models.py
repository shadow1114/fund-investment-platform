from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from fip.api.schemas import (
    BacktestCreatedModel,
    DataCompleteness,
    DecisionReviewOutcomeModel,
    MetricTriple,
    OptimizationSubmissionModel,
    ReadPayloadModel,
)


def test_frozen_command_models_require_contract_fields() -> None:
    assert OptimizationSubmissionModel(
        operation_id="OP-1", status="RUNNING", optimization_id="OPT-1"
    )
    assert BacktestCreatedModel(backtest_id="BT-1", status="CREATED", created_at=datetime.now(UTC))
    assert DataCompleteness(available=1, expected=2)
    assert MetricTriple(value=None, status="UNKNOWN", reason="NOT_DECLARED")


def test_review_model_rejects_nullable_reason_and_unknown_status() -> None:
    with pytest.raises(ValidationError):
        DecisionReviewOutcomeModel(
            decision_id="D-1",
            decision_status="APPROVED",
            reviewed_by="u-1",
            reviewed_at=datetime.now(UTC),
            reason=None,
            original_weights=[],
            final_weights=None,
        )
    with pytest.raises(ValidationError):
        MetricTriple(value=1.0, status="BAD", reason=None)
    with pytest.raises(ValidationError):
        OptimizationSubmissionModel(
            operation_id="OP-1", status="RUNNING", optimization_id="OPT-1", extra="x"
        )


def test_read_payload_rejects_unknown_top_level_fields_and_metric_status() -> None:
    with pytest.raises(ValidationError):
        ReadPayloadModel(fund_id="000001", unexpected="x")
    with pytest.raises(ValidationError):
        ReadPayloadModel(fund_id="000001", nav_status="BROKEN")
