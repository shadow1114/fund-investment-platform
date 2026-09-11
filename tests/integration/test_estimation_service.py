import datetime as dt
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import func, select

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.data_service.models.market import FundNav
from fip.services.factor_service.models import FactorRun
from fip.services.fund_service.models import (
    FundEvaluation,
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupSnapshot,
)
from fip.services.portfolio_service.estimation import (
    ApprovedEstimationProvider,
    EstimationConfigurationError,
    EstimationService,
)
from fip.services.portfolio_service.estimation.models import (
    CovarianceEstimate,
    EstimationMethodVersion,
    EstimationParameterVersion,
    EstimationRun,
    EstimationValidationResult,
    ReturnEstimate,
    RiskEstimate,
)
from fip.services.portfolio_service.estimation.policy import (
    load_estimation_policy,
    load_estimation_validation_policy,
    persist_estimation_policy_version,
    persist_estimation_validation_policy_version,
)
from fip.services.portfolio_service.estimation.repositories import (
    EstimationRunConflict,
    EstimationRunRepository,
)
from fip.strategy_library.estimation.types import FactorRiskObservation

pytestmark = pytest.mark.integration


class NoFactorRiskCandidates:
    def load_candidates(self, share_class_id: int, decision_id: str):
        del share_class_id, decision_id
        return ()


class MutableFactorRiskCandidates:
    def __init__(self):
        self.candidates: tuple[FactorRiskObservation, ...] = ()

    def load_candidates(self, share_class_id: int, decision_id: str):
        del share_class_id, decision_id
        return self.candidates


def _utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC)


def seed_estimation_service(
    db_session,
    *,
    decision_id: str = "service-decision",
    minimum_t_over_n: int = 3,
    factor_risk_provider=None,
):
    version_suffix = decision_id[-12:]
    context = DecisionExecutionContext(
        decision_id=decision_id,
        decision_at=dt.date(2026, 1, 31),
        data_as_of=dt.date(2026, 1, 31),
        strategy_version="strategy-v1",
        policy_version="policy-v1",
        code_version="code-v1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    estimation_policy = replace(
        load_estimation_policy(Path("config/policy/estimation/v1.yaml"), RuntimeMode.BACKTEST),
        version=f"est-{version_suffix}",
        lookback_trading_days=20,
        minimum_t_over_n=minimum_t_over_n,
        warning_t_over_n=max(5, minimum_t_over_n),
    )
    validation_policy = replace(
        load_estimation_validation_policy(
            Path("config/policy/estimation/validation_v1.yaml"), RuntimeMode.BACKTEST
        ),
        version=f"val-{version_suffix}",
        minimum_t_over_n=minimum_t_over_n,
        warning_t_over_n=max(5, minimum_t_over_n),
    )
    evaluation_policy = PolicyVersion(
        policy_kind="evaluation",
        version_label=f"eval-{version_suffix}",
        content={},
    )
    db_session.add(evaluation_policy)
    db_session.flush()
    estimation_policy_version_id = persist_estimation_policy_version(db_session, estimation_policy)
    validation_policy_version_id = persist_estimation_validation_policy_version(
        db_session, validation_policy
    )
    method = EstimationMethodVersion(
        method_code="PLAN3_M1",
        version_label=f"method-{version_suffix}",
        implementation_path="fip.strategy_library.estimation",
        specification={
            "returns": "HISTORICAL_MEAN_JAMES_STEIN",
            "covariance": "LEDOIT_WOLF_CONSTANT_CORRELATION",
        },
    )
    parameters = EstimationParameterVersion(
        version_label=f"params-{version_suffix}",
        parameters={
            "lookback_trading_days": estimation_policy.lookback_trading_days,
            "annualization_factor": estimation_policy.annualization_factor,
        },
    )
    db_session.add_all((method, parameters))

    funds = tuple(
        Fund(
            fund_code=f"{decision_id}-fund-{index}",
            product_name=f"Service Fund {index}",
            grouping_status="CONFIRMED",
        )
        for index in range(4)
    )
    db_session.add_all(funds)
    db_session.flush()
    shares = tuple(
        FundShareClass(
            fund_id=fund.id,
            share_class_code="A",
            display_name=f"Service Fund {index} A",
        )
        for index, fund in enumerate(funds)
    )
    db_session.add_all(shares)
    db_session.flush()

    days = tuple(dt.date(2026, 1, 2) + dt.timedelta(days=index) for index in range(21))
    returns = np.asarray(
        [
            (
                0.0010 + 0.00030 * np.sin(index),
                0.0008 + 0.00040 * np.cos(0.7 * index),
                0.0012 + 0.00025 * np.sin(1.3 * index + 0.2),
                0.0005 + 0.00035 * np.cos(1.7 * index + 0.3),
            )
            for index in range(20)
        ],
        dtype=np.float64,
    )
    levels = np.full((21, 4), 100.0, dtype=np.float64)
    for index in range(20):
        levels[index + 1] = levels[index] * (1.0 + returns[index])
    db_session.add_all(
        FundNav(
            share_class_id=share.id,
            effective_at=day,
            version=1,
            unit_nav=Decimal(str(levels[day_index, share_index])),
            available_at=_utc(day + dt.timedelta(days=1)),
            availability_quality="INFERRED",
            published_at=None,
            provider_available_at=None,
            ingested_at=_utc(dt.date(2026, 1, 30)),
        )
        for share_index, share in enumerate(shares)
        for day_index, day in enumerate(days)
    )

    peer_group = PeerGroupSnapshot(
        decision_id=decision_id,
        decision_at=context.decision_at,
        policy_version_id=evaluation_policy.id,
        classification_code="ACTIVE_EQUITY",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=len(shares),
    )
    db_session.add(peer_group)
    db_session.flush()
    factor_run = FactorRun(
        decision_id=decision_id,
        peer_group_snapshot_id=peer_group.id,
        metric_version_id=evaluation_policy.id,
        evaluation_policy_version_id=evaluation_policy.id,
        input_quality_summary={},
    )
    db_session.add(factor_run)
    db_session.flush()
    evaluation = FundEvaluation(
        decision_id=decision_id,
        peer_group_snapshot_id=peer_group.id,
        factor_run_id=factor_run.id,
        policy_version_id=evaluation_policy.id,
    )
    db_session.add(evaluation)
    db_session.flush()
    snapshot = FundUniverseSnapshot(
        decision_id=decision_id,
        evaluation_id=evaluation.id,
        policy_version_id=evaluation_policy.id,
    )
    db_session.add(snapshot)
    db_session.flush()
    db_session.add_all(
        FundUniverseMember(
            snapshot_id=snapshot.id,
            share_class_id=share.id,
            status="SELECTED",
        )
        for share in reversed(shares)
    )
    db_session.commit()

    service = EstimationService(
        db_session,
        estimation_policy=estimation_policy,
        validation_policy=validation_policy,
        estimation_method_version_id=method.id,
        estimation_parameter_version_id=parameters.id,
        estimation_policy_version_id=estimation_policy_version_id,
        validation_policy_version_id=validation_policy_version_id,
        adjustment_policy_version="adjusted-nav-v1",
        factor_risk_provider=factor_risk_provider or NoFactorRiskCandidates(),
    )
    return service, context, snapshot.id, tuple(sorted(share.id for share in shares))


@pytest.fixture()
def service_fixture(db_session):
    return seed_estimation_service(db_session)


def test_absolute_success_and_excess_input_rejection_is_warning(db_session, service_fixture):
    service, context, snapshot_id, expected_order = service_fixture

    result = service.run(context, snapshot_id)

    assert result.status == "COMPLETED_WITH_WARNING"
    assert result.approved_for_optimization is True
    assert result.basis_statuses == {"ABSOLUTE": "COMPLETED_WITH_WARNING", "EXCESS": "REJECTED"}
    approved = ApprovedEstimationProvider(db_session).load(result.run_id)
    assert approved.return_basis == "ABSOLUTE"
    assert approved.instrument_order == expected_order
    assert approved.order == expected_order
    assert np.array_equal(approved.Sigma, approved.covariance)
    assert approved.mu.shape == (4,)
    assert approved.Sigma.shape == (4, 4)


def test_unhandled_failure_rolls_back_results_and_marks_run_failed(
    db_session, service_fixture, monkeypatch
):
    service, context, snapshot_id, _expected_order = service_fixture
    original = EstimationRunRepository._save_bundle
    save_count = 0

    def save_then_fail(repository, run_id, bundle):
        nonlocal save_count
        original(repository, run_id, bundle)
        save_count += 1
        if save_count == 1:
            repository._session.flush()
            raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(EstimationRunRepository, "_save_bundle", save_then_fail)

    with pytest.raises(RuntimeError, match="injected persistence failure"):
        service.run(context, snapshot_id)

    run = db_session.scalar(
        select(EstimationRun).where(EstimationRun.decision_id == context.decision_id)
    )
    assert run is not None
    assert run.status == "FAILED"
    assert run.approved_for_optimization is False
    assert run.error_code == "RUNTIME_ERROR"
    for model in (
        ReturnEstimate,
        RiskEstimate,
        CovarianceEstimate,
        EstimationValidationResult,
    ):
        assert (
            db_session.scalar(select(func.count()).select_from(model).where(model.run_id == run.id))
            == 0
        )


def test_absolute_input_rejection_always_rejects_run(db_session):
    service, context, snapshot_id, _expected_order = seed_estimation_service(
        db_session,
        decision_id="absolute-rejection",
        minimum_t_over_n=6,
    )

    result = service.run(context, snapshot_id)

    assert result.status == "REJECTED"
    assert result.approved_for_optimization is False
    assert result.basis_statuses["ABSOLUTE"] == "REJECTED"


def test_existing_final_run_is_returned_only_after_lineage_is_rebuilt(db_session):
    service, context, snapshot_id, expected_order = seed_estimation_service(
        db_session, decision_id="lineage-rebuild"
    )
    first = service.run(context, snapshot_id)
    changed_nav = db_session.scalar(
        select(FundNav).where(FundNav.share_class_id == expected_order[0]).limit(1)
    )
    assert changed_nav is not None
    changed_nav.unit_nav = changed_nav.unit_nav + Decimal("1")
    db_session.commit()

    with pytest.raises(EstimationRunConflict):
        service.run(context, snapshot_id)

    persisted = db_session.get(EstimationRun, first.run_id)
    assert persisted is not None
    assert persisted.status == first.status
    assert persisted.input_lineage_fingerprint == first.input_lineage_fingerprint


def test_service_rejects_policy_content_that_no_longer_matches_immutable_version(
    db_session,
):
    service, context, snapshot_id, _expected_order = seed_estimation_service(
        db_session, decision_id="policy-content"
    )
    row = db_session.scalar(select(PolicyVersion).where(PolicyVersion.policy_kind == "estimation"))
    assert row is not None
    row.content = {}
    db_session.commit()

    with pytest.raises(EstimationConfigurationError, match="content"):
        service.run(context, snapshot_id)

    assert db_session.scalar(select(func.count()).select_from(EstimationRun)) == 0


def test_factor_cross_check_candidates_are_part_of_idempotency_lineage(db_session):
    factor_risk_provider = MutableFactorRiskCandidates()
    service, context, snapshot_id, _expected_order = seed_estimation_service(
        db_session,
        decision_id="factor-lineage",
        factor_risk_provider=factor_risk_provider,
    )
    service.run(context, snapshot_id)
    factor_risk_provider.candidates = (
        FactorRiskObservation(
            factor_run_id=901,
            factor_value_id=902,
            factor_version_id=903,
            volatility=0.25,
            window="20D",
            observation_fingerprint="different-observation-window",
            return_type="SIMPLE",
            ddof=1,
            annualization=252,
            status="AVAILABLE",
        ),
    )

    with pytest.raises(EstimationRunConflict):
        service.run(context, snapshot_id)
