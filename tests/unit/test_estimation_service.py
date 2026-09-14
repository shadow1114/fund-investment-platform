"""Service boundary regressions independent of the PostgreSQL test fixture."""

import datetime as dt
import json
from contextlib import nullcontext
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.portfolio_service.estimation.inputs import EstimationBasisInput
from fip.services.portfolio_service.estimation.models import (
    EstimationMethodVersion,
    EstimationParameterVersion,
)
from fip.services.portfolio_service.estimation.policy import (
    estimation_parameter_content,
    load_estimation_policy,
    load_estimation_validation_policy,
)
from fip.services.portfolio_service.estimation.repositories import (
    EstimationRunRepository,
    StartRunResult,
)
from fip.services.portfolio_service.estimation.service import (
    EstimationConfigurationError,
    EstimationService,
    _aggregate_factor_results,
)
from fip.strategy_library.estimation.validation import ValidationResult


class VersionSession:
    """Only the ORM lookup boundary is replaced; policy/version validation is real."""

    def __init__(self, rows):
        self.rows = rows

    def get(self, model, row_id):
        return self.rows[model, row_id]

    def in_transaction(self):
        return False

    def begin(self):
        return nullcontext()


class NoCandidates:
    def load_candidates(self, share_class_id, decision_id):
        return ()


@pytest.fixture()
def service():
    policy = load_estimation_policy(Path("config/policy/estimation/v1.yaml"), RuntimeMode.BACKTEST)
    validation = load_estimation_validation_policy(
        Path("config/policy/estimation/validation_v1.yaml"), RuntimeMode.BACKTEST
    )
    method = EstimationMethodVersion(
        id=1,
        method_code="PLAN3_M1",
        implementation_path="fip.strategy_library.estimation",
        specification={
            "returns": "HISTORICAL_MEAN_JAMES_STEIN",
            "covariance": "LEDOIT_WOLF_CONSTANT_CORRELATION",
            "formula_version": "PLAN3_D4A_GAMMA_T_V1",
            "instrument_order": "SHARE_CLASS_ID_ASC",
        },
    )
    parameter_content = estimation_parameter_content(policy)
    rows = {
        (EstimationMethodVersion, 1): method,
        (EstimationParameterVersion, 2): EstimationParameterVersion(
            id=2, parameters=parameter_content
        ),
        (PolicyVersion, 3): PolicyVersion(
            policy_kind="estimation",
            version_label=policy.version,
            content=json.loads(json.dumps(asdict(policy), default=str)),
        ),
        (PolicyVersion, 4): PolicyVersion(
            policy_kind="estimation_validation",
            version_label=validation.version,
            content=json.loads(json.dumps(asdict(validation), default=str)),
        ),
    }
    return EstimationService(
        VersionSession(rows),
        estimation_policy=policy,
        validation_policy=validation,
        estimation_method_version_id=1,
        estimation_parameter_version_id=2,
        estimation_policy_version_id=3,
        validation_policy_version_id=4,
        adjustment_policy_version="v1",
        factor_risk_provider=NoCandidates(),
    )


def context(mode=RuntimeMode.BACKTEST):
    return DecisionExecutionContext(
        decision_id="unit-estimation",
        decision_at=dt.date(2026, 1, 31),
        data_as_of=dt.date(2026, 1, 31),
        strategy_version="v1",
        policy_version="v1",
        code_version="v1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=mode,
    )


def test_parameter_version_captures_the_return_basis_contract(service):
    parameters = estimation_parameter_content(service._estimation_policy)

    assert parameters["primary_return_basis"] == "ABSOLUTE"
    assert parameters["secondary_return_bases"] == ["EXCESS"]


def basis(name, matrix):
    order = tuple(range(1, matrix.shape[1] + 1))
    dates = tuple(dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(len(matrix)))
    return EstimationBasisInput(
        return_basis=name,
        status="AVAILABLE",
        rejection_reason=None,
        matrix=matrix,
        instrument_order=order,
        observation_dates=dates,
        excluded_instruments=(),
        dropped_dates=(),
        lineage={
            "instrument_order": list(order),
            "numeric_scale": "ANNUALIZED",
            "data_completeness": {"observation_count": len(matrix)},
        },
        observation_fingerprint="f" * 64,
        basis_fingerprint="a" * 64,
    )


@pytest.mark.parametrize("degenerate", ["zero_variance", "three_members"])
@pytest.mark.parametrize("rejected_basis", ["ABSOLUTE", "EXCESS"])
def test_numerical_rejection_preserves_other_basis(service, degenerate, rejected_basis):
    good = np.random.default_rng(42).normal(0.001, 0.01, (24, 4))
    bad = good[:, :3] if degenerate == "three_members" else np.zeros((24, 4))
    inputs = tuple(
        basis(name, bad if name == rejected_basis else good) for name in ("ABSOLUTE", "EXCESS")
    )
    bundles, rejections, statuses = service._calculate_outcomes(context(), inputs)
    assert len(bundles) == len(rejections) == 1
    assert statuses[rejected_basis] == "REJECTED"
    assert rejections[0].reason_code == "NUMERICAL_INPUT_REJECTED"
    assert rejections[0].input_lineage["numerical_rejection"]["message"]
    assert bundles[0].return_basis != rejected_basis


@pytest.mark.parametrize("source", ["estimation", "validation"])
def test_live_injected_provisional_policy_fails_gate(service, source):
    attribute = "_estimation_policy" if source == "estimation" else "_validation_policy"
    setattr(service, attribute, replace(getattr(service, attribute), provisional_parameters=("x",)))
    good = np.random.default_rng(42).normal(0.001, 0.01, (24, 4))
    bundles, _, statuses = service._calculate_outcomes(
        context(RuntimeMode.LIVE), (basis("ABSOLUTE", good), basis("EXCESS", good))
    )
    assert statuses == {"ABSOLUTE": "REJECTED", "EXCESS": "REJECTED"}
    for bundle in bundles:
        gate = next(item for item in bundle.validations if item.code == "RUNTIME_ELIGIBILITY")
        assert gate.status == "FAILED" and "x" in gate.detail and "LIVE" in gate.detail


def test_live_provisional_rejection_keeps_runtime_eligibility_audit_evidence(service):
    service._estimation_policy = replace(
        service._estimation_policy, provisional_parameters=("window.lookback_trading_days",)
    )
    rejected = replace(
        basis("ABSOLUTE", np.empty((0, 0))),
        status="REJECTED",
        rejection_reason="INSUFFICIENT_COMPLETE_CASES",
    )

    bundles, rejections, statuses = service._calculate_outcomes(
        context(RuntimeMode.LIVE), (rejected,)
    )

    assert bundles == ()
    assert statuses == {"ABSOLUTE": "REJECTED"}
    audit = rejections[0].validations
    assert len(audit) == 1
    assert audit[0].code == "RUNTIME_ELIGIBILITY"
    assert audit[0].status == "FAILED"
    assert "window.lookback_trading_days" in audit[0].detail


@pytest.mark.parametrize("experimental", [False, True])
def test_backtest_provisional_requires_explicit_opt_in(service, experimental):
    service._estimation_policy = replace(service._estimation_policy, provisional_parameters=("x",))
    service._allow_experimental = experimental
    good = np.random.default_rng(42).normal(0.001, 0.01, (24, 4))
    bundles, _, _ = service._calculate_outcomes(context(), (basis("ABSOLUTE", good),))
    gate = next(item for item in bundles[0].validations if item.code == "RUNTIME_ELIGIBILITY")
    assert gate.status == ("PASSED" if experimental else "FAILED")


@pytest.mark.parametrize(
    "field,value",
    [
        ("implementation_path", "wrong.module"),
        ("method_code", "OTHER_METHOD"),
        ("specification", {"returns": "CAPM", "covariance": "SAMPLE"}),
    ],
)
def test_wrong_method_identity_is_rejected(service, field, value):
    setattr(service._session.get(EstimationMethodVersion, 1), field, value)
    with pytest.raises(EstimationConfigurationError, match="method"):
        service._validated_versions()


@pytest.mark.parametrize(
    "field,value",
    [
        ("annualization_factor", 12),
        ("lookback_trading_days", 63),
        ("covariance_shrinkage_target", "IDENTITY"),
        ("observation_frequency", "MONTHLY"),
        ("primary_return_basis", "EXCESS"),
    ],
)
def test_mismatched_parameter_version_is_rejected(service, field, value):
    service._session.get(EstimationParameterVersion, 2).parameters[field] = value
    with pytest.raises(EstimationConfigurationError, match="parameter"):
        service._validated_versions()


@pytest.mark.parametrize("status", ["PASSED", "FAILED"])
def test_factor_aggregation_retains_selected_ids_and_details(status):
    detail = "factor_value_id=91, factor_run_id=8, factor_version_id=6, relative_error=0.0"
    result = _aggregate_factor_results(
        (
            (11, ValidationResult("FACTOR_RISK_CROSS_CHECK", "REJECT", status, detail)),
            (
                12,
                ValidationResult(
                    "NOT_COMPARABLE",
                    "WARNING",
                    "FAILED",
                    "matching_factor_value_ids=[]",
                ),
            ),
        )
    )
    assert detail in result.detail
    assert "matching_factor_value_ids=[]" in result.detail


@pytest.mark.parametrize("status", ["FAILED", "RUNNING", "PENDING"])
def test_ordinary_run_returns_nonfinal_existing_state_without_calculating(
    service, monkeypatch, status
):
    monkeypatch.setattr(
        EstimationRunRepository, "start", lambda self, identity: StartRunResult(17, status, False)
    )
    monkeypatch.setattr(
        EstimationRunRepository,
        "retry_failed",
        lambda self, run_id: pytest.fail(f"ordinary run must not retry {run_id}"),
    )
    result = service.run(context(), 20)
    assert result.run_id == 17 and result.status == status
    assert not result.approved_for_optimization
