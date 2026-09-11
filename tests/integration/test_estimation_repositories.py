import dataclasses
import datetime as dt
import threading
import time
import uuid

import numpy as np
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.models import FactorRun
from fip.services.fund_service.models import (
    FundEvaluation,
    FundUniverseSnapshot,
    PeerGroupSnapshot,
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
from fip.services.portfolio_service.estimation.repositories import (
    ApprovedEstimationProvider,
    EstimationBasisRejection,
    EstimationIntegrityError,
    EstimationResultBundle,
    EstimationRunConflict,
    EstimationRunIdentity,
    EstimationRunRepository,
    EstimationStateError,
)
from fip.strategy_library.estimation.encoding import canonical_checksum
from fip.strategy_library.estimation.types import (
    CovarianceEstimateResult,
    ReturnEstimateResult,
)
from fip.strategy_library.estimation.validation import ValidationResult

pytestmark = pytest.mark.integration


@pytest.fixture()
def repository_fixture(db_session):
    policies = {
        kind: PolicyVersion(policy_kind=kind, version_label=f"repository-{kind}", content={})
        for kind in ("evaluation", "estimation", "estimation_validation")
    }
    db_session.add_all(policies.values())
    db_session.flush()

    funds = tuple(
        Fund(
            fund_code=f"repository-{index}",
            product_name=f"Repository Fund {index}",
            grouping_status="CONFIRMED",
        )
        for index in range(2)
    )
    db_session.add_all(funds)
    db_session.flush()
    shares = tuple(
        FundShareClass(
            fund_id=fund.id,
            share_class_code="A",
            display_name=f"Repository Fund {index} A",
        )
        for index, fund in enumerate(funds)
    )
    db_session.add_all(shares)
    db_session.flush()

    peer_group = PeerGroupSnapshot(
        decision_id="repository-decision",
        classification_code="BOND",
        base_currency="CNY",
        policy_version_id=policies["evaluation"].id,
        decision_at=dt.date(2026, 9, 10),
        status="AVAILABLE",
        member_count=2,
    )
    db_session.add(peer_group)
    db_session.flush()
    factor_run = FactorRun(
        decision_id="repository-decision",
        peer_group_snapshot_id=peer_group.id,
        metric_version_id=policies["evaluation"].id,
        evaluation_policy_version_id=policies["evaluation"].id,
        input_quality_summary={},
    )
    db_session.add(factor_run)
    db_session.flush()
    evaluation = FundEvaluation(
        decision_id="repository-decision",
        peer_group_snapshot_id=peer_group.id,
        factor_run_id=factor_run.id,
        policy_version_id=policies["evaluation"].id,
    )
    db_session.add(evaluation)
    db_session.flush()
    universe = FundUniverseSnapshot(
        decision_id="repository-decision",
        evaluation_id=evaluation.id,
        policy_version_id=policies["evaluation"].id,
    )
    method = EstimationMethodVersion(
        method_code="PLAN3_M1",
        version_label="v1",
        implementation_path="fip.strategy_library.estimation",
        specification={},
    )
    parameters = EstimationParameterVersion(version_label="repository-v1", parameters={})
    db_session.add_all((universe, method, parameters))
    db_session.flush()

    identity = EstimationRunIdentity(
        decision_id="repository-decision",
        universe_snapshot_id=universe.id,
        estimation_method_version_id=method.id,
        estimation_parameter_version_id=parameters.id,
        estimation_policy_version_id=policies["estimation"].id,
        validation_policy_version_id=policies["estimation_validation"].id,
        code_version="code-v1",
    )
    order = tuple(share.id for share in shares)
    covariance = np.array([[0.04, 0.01], [0.01, 0.09]], dtype=np.float64)
    correlation = np.array([[1.0, 1.0 / 6.0], [1.0 / 6.0, 1.0]], dtype=np.float64)
    input_lineage = {"instrument_order": list(order), "numeric_scale": "ANNUALIZED"}
    bundle = EstimationResultBundle(
        return_basis="ABSOLUTE",
        instrument_order=order,
        return_estimate=ReturnEstimateResult(
            sample_mean_daily=np.array([0.0001, 0.0002]),
            target_daily=0.00015,
            shrinkage_intensity=0.25,
            shrunk_mu_annualized=np.array([0.04, 0.05]),
            annualized_mu=np.array([0.04, 0.05]),
            clipped=np.array([False, False]),
        ),
        covariance_estimate=CovarianceEstimateResult(
            sample_covariance_daily=covariance / 252.0,
            target_covariance_daily=covariance / 252.0,
            covariance=covariance,
            correlation=correlation,
            variance=np.array([0.04, 0.09]),
            volatility=np.array([0.2, 0.3]),
            shrinkage_intensity=0.4,
            sample_min_eigenvalue=0.03697224362268005,
            sample_max_eigenvalue=0.09302775637731995,
            sample_condition_number=2.516994241651881,
            final_min_eigenvalue=0.03807417596432748,
            final_max_eigenvalue=0.09192582403567252,
            final_condition_number=2.414387749896406,
        ),
        observation_count=24,
        dropped_dates_count=2,
        excluded_instruments=((999_999, "INSUFFICIENT_VALID_RETURNS"),),
        input_lineage=input_lineage,
        input_fingerprint=canonical_checksum(input_lineage),
        validations=(
            ValidationResult("MIN_T_OVER_N", "REJECT", "PASSED", "T=24, N=2"),
            ValidationResult("CONDITION_NUMBER", "WARNING", "FAILED", "warning threshold"),
        ),
    )
    return db_session, EstimationRunRepository(db_session), identity, bundle


def _complete(repository, identity, bundle, *, fingerprint=None):
    started = repository.start(identity)
    fingerprint = fingerprint or _aggregate_fingerprint(bundle)
    return repository.complete(started.run_id, (bundle,), fingerprint)


def _aggregate_fingerprint(*outcomes):
    return canonical_checksum(
        {
            outcome.return_basis: outcome.input_fingerprint
            for outcome in sorted(outcomes, key=lambda item: item.return_basis)
        }
    )


def _seed_concurrency_identity(db_engine):
    suffix = uuid.uuid4().hex[:10]
    session = Session(db_engine, future=True)
    policies = {
        kind: PolicyVersion(
            policy_kind=kind,
            version_label=f"concurrent-{suffix}-{index}",
            content={},
        )
        for index, kind in enumerate(("evaluation", "estimation", "estimation_validation"), start=1)
    }
    session.add_all(policies.values())
    session.flush()
    fund = Fund(
        fund_code=f"concurrent-{suffix}",
        product_name=f"Concurrent {suffix}",
        grouping_status="CONFIRMED",
    )
    session.add(fund)
    session.flush()
    share = FundShareClass(
        fund_id=fund.id,
        share_class_code="A",
        display_name=f"Concurrent {suffix} A",
    )
    session.add(share)
    session.flush()
    decision_id = f"concurrent-{suffix}"
    peer_group = PeerGroupSnapshot(
        decision_id=decision_id,
        classification_code="BOND",
        base_currency="CNY",
        policy_version_id=policies["evaluation"].id,
        decision_at=dt.date(2026, 9, 10),
        status="AVAILABLE",
        member_count=1,
    )
    session.add(peer_group)
    session.flush()
    factor_run = FactorRun(
        decision_id=decision_id,
        peer_group_snapshot_id=peer_group.id,
        metric_version_id=policies["evaluation"].id,
        evaluation_policy_version_id=policies["evaluation"].id,
        input_quality_summary={},
    )
    session.add(factor_run)
    session.flush()
    evaluation = FundEvaluation(
        decision_id=decision_id,
        peer_group_snapshot_id=peer_group.id,
        factor_run_id=factor_run.id,
        policy_version_id=policies["evaluation"].id,
    )
    session.add(evaluation)
    session.flush()
    universe = FundUniverseSnapshot(
        decision_id=decision_id,
        evaluation_id=evaluation.id,
        policy_version_id=policies["evaluation"].id,
    )
    method = EstimationMethodVersion(
        method_code=f"concurrent-{suffix}",
        version_label="v1",
        implementation_path="fip.strategy_library.estimation",
        specification={},
    )
    parameters = EstimationParameterVersion(version_label=f"concurrent-{suffix}", parameters={})
    session.add_all((universe, method, parameters))
    session.flush()
    identity = EstimationRunIdentity(
        decision_id=decision_id,
        universe_snapshot_id=universe.id,
        estimation_method_version_id=method.id,
        estimation_parameter_version_id=parameters.id,
        estimation_policy_version_id=policies["estimation"].id,
        validation_policy_version_id=policies["estimation_validation"].id,
        code_version="code-v1",
    )
    session.commit()
    session.close()
    return identity


def _cleanup_concurrency_identity(db_engine, identity):
    parameters = {"decision_id": identity.decision_id}
    statements = (
        "DELETE FROM portfolio.estimation_run WHERE decision_id = :decision_id",
        "DELETE FROM evaluation.fund_universe_snapshot WHERE decision_id = :decision_id",
        "DELETE FROM evaluation.fund_evaluation WHERE decision_id = :decision_id",
        "DELETE FROM factor.factor_run WHERE decision_id = :decision_id",
        "DELETE FROM evaluation.peer_group_snapshot WHERE decision_id = :decision_id",
        "DELETE FROM fund.fund_share_class WHERE fund_id IN "
        "(SELECT id FROM fund.fund WHERE fund_code = :decision_id)",
        "DELETE FROM fund.fund WHERE fund_code = :decision_id",
        "DELETE FROM portfolio.estimation_method_version "
        "WHERE id = :estimation_method_version_id",
        "DELETE FROM portfolio.estimation_parameter_version "
        "WHERE id = :estimation_parameter_version_id",
        "DELETE FROM governance.policy_version WHERE id IN "
        "(:estimation_policy_version_id, :validation_policy_version_id)",
        "DELETE FROM governance.policy_version WHERE version_label LIKE :evaluation_label",
    )
    parameters.update(
        {
            "estimation_method_version_id": identity.estimation_method_version_id,
            "estimation_parameter_version_id": identity.estimation_parameter_version_id,
            "estimation_policy_version_id": identity.estimation_policy_version_id,
            "validation_policy_version_id": identity.validation_policy_version_id,
            "evaluation_label": f"%{identity.decision_id.removeprefix('concurrent-')}%",
        }
    )
    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement), parameters)


def _wait_for_backend_lock(db_engine, backend_pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with db_engine.connect() as connection:
            wait_event_type = connection.execute(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                {"pid": backend_pid},
            ).scalar_one_or_none()
        if wait_event_type == "Lock":
            return
        time.sleep(0.01)
    raise AssertionError("worker backend did not block on the run row lock")


def test_start_is_idempotent_and_returns_existing_running_state(repository_fixture):
    db_session, repository, identity, _bundle = repository_fixture

    first = repository.start(identity)
    second = repository.start(identity)

    assert (first.status, first.should_execute) == ("RUNNING", True)
    assert (second.run_id, second.status, second.should_execute) == (
        first.run_id,
        "RUNNING",
        False,
    )
    assert db_session.scalar(select(func.count()).select_from(EstimationRun)) == 1


def test_concurrent_start_unique_key_race_returns_one_run(db_engine):
    identity = _seed_concurrency_identity(db_engine)
    barrier = threading.Barrier(2)
    seen_threads: set[str] = set()
    seen_lock = threading.Lock()
    results = {}

    def synchronize_after_initial_lookup(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        thread_name = threading.current_thread().name
        if (
            "portfolio.estimation_run" not in statement
            or "FOR UPDATE" not in statement
            or not thread_name.startswith("estimation-start-")
        ):
            return
        with seen_lock:
            if thread_name in seen_threads:
                return
            seen_threads.add(thread_name)
        barrier.wait(timeout=10)

    def worker(name):
        session = Session(db_engine, future=True)
        try:
            results[name] = EstimationRunRepository(session).start(identity)
            session.commit()
        except BaseException as exc:  # noqa: BLE001 - propagate thread failures
            results[name] = exc
        finally:
            session.close()

    event.listen(db_engine, "after_cursor_execute", synchronize_after_initial_lookup)
    threads = tuple(
        threading.Thread(target=worker, args=(name,), name=f"estimation-start-{name}")
        for name in ("a", "b")
    )
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        assert set(results) == {"a", "b"}
        for result in results.values():
            if isinstance(result, BaseException):
                raise AssertionError("concurrent start raised") from result
        first, second = results["a"], results["b"]
        assert first.run_id == second.run_id
        assert sorted((first.should_execute, second.should_execute)) == [False, True]
        with Session(db_engine, future=True) as check_session:
            assert (
                check_session.scalar(
                    select(func.count())
                    .select_from(EstimationRun)
                    .where(EstimationRun.decision_id == identity.decision_id)
                )
                == 1
            )
    finally:
        event.remove(db_engine, "after_cursor_execute", synchronize_after_initial_lookup)
        _cleanup_concurrency_identity(db_engine, identity)


def test_failed_run_is_returned_without_implicit_retry(repository_fixture):
    _db_session, repository, identity, _bundle = repository_fixture
    started = repository.start(identity)
    repository.fail(started.run_id, "CALCULATION_ERROR")

    repeated = repository.start(identity)

    assert (repeated.run_id, repeated.status, repeated.should_execute) == (
        started.run_id,
        "FAILED",
        False,
    )


def test_only_explicit_retry_reuses_failed_run(repository_fixture):
    db_session, repository, identity, _bundle = repository_fixture
    started = repository.start(identity)
    repository.fail(started.run_id, "CALCULATION_ERROR")

    retried = repository.retry_failed(started.run_id)

    assert (retried.run_id, retried.status, retried.should_execute) == (
        started.run_id,
        "RUNNING",
        True,
    )
    run = db_session.get(EstimationRun, started.run_id)
    assert run is not None
    assert run.error_code is None
    with pytest.raises(EstimationStateError):
        repository.retry_failed(started.run_id)


def test_retry_failed_waits_for_row_lock_and_rechecks_transition(db_engine):
    identity = _seed_concurrency_identity(db_engine)
    setup_session = Session(db_engine, future=True)
    started = EstimationRunRepository(setup_session).start(identity)
    setup_session.commit()
    EstimationRunRepository(setup_session).fail(started.run_id, "CALCULATION_ERROR")
    setup_session.commit()
    setup_session.close()

    blocker = Session(db_engine, future=True)
    worker_session = Session(db_engine, future=True)
    worker_backend_pid = worker_session.scalar(text("SELECT pg_backend_pid()"))
    assert worker_backend_pid is not None
    locked = blocker.execute(
        select(EstimationRun).where(EstimationRun.id == started.run_id).with_for_update()
    ).scalar_one()
    worker_query_started = threading.Event()
    worker_result = {}

    def observe_worker_query(_connection, _cursor, statement, _parameters, _context, _executemany):
        if (
            threading.current_thread().name == "estimation-retry-worker"
            and "portfolio.estimation_run" in statement
        ):
            worker_query_started.set()

    def retry_worker():
        try:
            worker_result["result"] = EstimationRunRepository(worker_session).retry_failed(
                started.run_id
            )
            worker_session.commit()
        except BaseException as exc:  # noqa: BLE001 - propagate thread failures
            worker_session.rollback()
            worker_result["result"] = exc

    event.listen(db_engine, "before_cursor_execute", observe_worker_query)
    thread = threading.Thread(target=retry_worker, name="estimation-retry-worker")
    try:
        thread.start()
        assert worker_query_started.wait(timeout=10)
        _wait_for_backend_lock(db_engine, worker_backend_pid)
        locked.status = "RUNNING"
        locked.error_code = None
        locked.completed_at = None
        blocker.commit()
        thread.join(timeout=15)
        assert not thread.is_alive()
        assert isinstance(worker_result.get("result"), EstimationStateError)
        with Session(db_engine, future=True) as check_session:
            run = check_session.get(EstimationRun, started.run_id)
            assert run is not None and run.status == "RUNNING"
    finally:
        if thread.is_alive():
            blocker.rollback()
            thread.join(timeout=5)
        event.remove(db_engine, "before_cursor_execute", observe_worker_query)
        blocker.close()
        worker_session.close()
        _cleanup_concurrency_identity(db_engine, identity)


def test_complete_persists_exact_bundle_and_does_not_duplicate(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture

    completed = _complete(repository, identity, bundle)
    repeated = repository.complete(completed.run_id, (bundle,), _aggregate_fingerprint(bundle))
    restarted = repository.start(identity)

    assert (completed.status, completed.approved_for_optimization) == (
        "COMPLETED_WITH_WARNING",
        True,
    )
    assert repeated == completed
    assert (restarted.run_id, restarted.status, restarted.should_execute) == (
        completed.run_id,
        "COMPLETED_WITH_WARNING",
        False,
    )
    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 2
    assert db_session.scalar(select(func.count()).select_from(RiskEstimate)) == 2
    assert db_session.scalar(select(func.count()).select_from(CovarianceEstimate)) == 1
    assert db_session.scalar(select(func.count()).select_from(EstimationValidationResult)) == 2


def test_failed_absolute_reject_validation_derives_rejected_unapproved_run(
    repository_fixture,
):
    _db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)
    failed_reject = dataclasses.replace(
        bundle,
        validations=bundle.validations
        + (ValidationResult("SIGMA_NOT_PSD", "REJECT", "FAILED", "negative eigenvalue"),),
    )

    finalized = repository.complete(
        started.run_id, (failed_reject,), _aggregate_fingerprint(failed_reject)
    )

    assert (finalized.status, finalized.approved_for_optimization) == ("REJECTED", False)


def test_failed_absolute_warning_validation_derives_completed_with_warning(
    repository_fixture,
):
    _db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)
    warning_only = dataclasses.replace(
        bundle,
        validations=(
            ValidationResult("MIN_T_OVER_N", "REJECT", "PASSED", "enough observations"),
            ValidationResult("NOT_COMPARABLE", "WARNING", "FAILED", "no factor candidate"),
        ),
    )

    finalized = repository.complete(
        started.run_id, (warning_only,), _aggregate_fingerprint(warning_only)
    )

    assert (finalized.status, finalized.approved_for_optimization) == (
        "COMPLETED_WITH_WARNING",
        True,
    )


def test_same_key_with_different_fingerprint_conflicts(repository_fixture):
    _db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)
    changed_lineage = {**bundle.input_lineage, "revision": 2}
    changed_bundle = dataclasses.replace(
        bundle,
        input_lineage=changed_lineage,
        input_fingerprint=canonical_checksum(changed_lineage),
    )

    with pytest.raises(EstimationRunConflict):
        repository.complete(
            completed.run_id,
            (changed_bundle,),
            _aggregate_fingerprint(changed_bundle),
        )


def test_complete_rejects_arbitrary_run_fingerprint(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)

    with pytest.raises(EstimationIntegrityError):
        repository.complete(started.run_id, (bundle,), "a" * 64)

    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 0


def test_approved_provider_recomputes_persisted_basis_aggregate(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)
    completed = repository.complete(
        started.run_id,
        (bundle,),
        _aggregate_fingerprint(bundle),
    )
    db_session.execute(
        text(
            """
            UPDATE portfolio.estimation_run
            SET input_lineage_fingerprint = :fingerprint
            WHERE id = :run_id
            """
        ),
        {"run_id": completed.run_id, "fingerprint": "a" * 64},
    )
    db_session.expire_all()

    with pytest.raises(EstimationIntegrityError):
        ApprovedEstimationProvider(db_session).load(completed.run_id)


def test_reject_persists_audit_bundle_but_never_approves(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)
    rejected_bundle = dataclasses.replace(
        bundle,
        validations=bundle.validations
        + (ValidationResult("SIGMA_NOT_PSD", "REJECT", "FAILED", "negative eigenvalue"),),
    )

    rejected = repository.reject(
        started.run_id,
        (rejected_bundle,),
        _aggregate_fingerprint(rejected_bundle),
    )

    assert (rejected.status, rejected.approved_for_optimization) == ("REJECTED", False)
    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 2
    with pytest.raises(EstimationIntegrityError):
        ApprovedEstimationProvider(db_session).load(started.run_id)


def test_reject_persists_input_rejection_without_fabricating_numeric_results(
    repository_fixture,
):
    db_session, repository, identity, _bundle = repository_fixture
    started = repository.start(identity)
    lineage = {
        "instrument_order": [101, 202],
        "status": "REJECTED",
        "rejection_reason": "INSUFFICIENT_COMPLETE_CASES",
    }
    rejection = EstimationBasisRejection(
        return_basis="ABSOLUTE",
        reason_code="INSUFFICIENT_COMPLETE_CASES",
        input_lineage=lineage,
        input_fingerprint=canonical_checksum(lineage),
        observation_count=3,
        dropped_dates_count=5,
        excluded_instruments=((101, "INSUFFICIENT_VALID_RETURNS"),),
    )

    rejected = repository.reject(
        started.run_id,
        (),
        _aggregate_fingerprint(rejection),
        basis_rejections=(rejection,),
    )

    assert (rejected.status, rejected.approved_for_optimization) == ("REJECTED", False)
    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 0
    assert db_session.scalar(select(func.count()).select_from(RiskEstimate)) == 0
    assert db_session.scalar(select(func.count()).select_from(CovarianceEstimate)) == 0
    audit = db_session.scalar(
        select(EstimationValidationResult).where(
            EstimationValidationResult.run_id == started.run_id,
            EstimationValidationResult.return_basis == "ABSOLUTE",
            EstimationValidationResult.code == "BASIS_INPUT_REJECTED",
        )
    )
    assert audit is not None
    assert audit.status == "FAILED"
    assert audit.detail["reason_code"] == "INSUFFICIENT_COMPLETE_CASES"
    assert audit.detail["input_lineage"] == lineage


def test_complete_can_audit_rejected_excess_without_mixing_it_into_approval(
    repository_fixture,
):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)
    lineage = {
        "instrument_order": list(bundle.instrument_order),
        "status": "REJECTED",
        "rejection_reason": "BENCHMARK_UNAVAILABLE",
    }
    rejection = EstimationBasisRejection(
        return_basis="EXCESS",
        reason_code="BENCHMARK_UNAVAILABLE",
        input_lineage=lineage,
        input_fingerprint=canonical_checksum(lineage),
        observation_count=0,
        dropped_dates_count=4,
        excluded_instruments=(),
    )

    completed = repository.complete(
        started.run_id,
        (bundle,),
        _aggregate_fingerprint(bundle, rejection),
        basis_rejections=(rejection,),
    )

    assert (completed.status, completed.approved_for_optimization) == (
        "COMPLETED_WITH_WARNING",
        True,
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(CovarianceEstimate)
            .where(CovarianceEstimate.return_basis == "EXCESS")
        )
        == 0
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(EstimationValidationResult)
            .where(EstimationValidationResult.return_basis == "EXCESS")
        )
        == 1
    )


def test_fail_rejects_final_runs_and_never_saves_partial_results(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)

    with pytest.raises(EstimationStateError):
        repository.fail(completed.run_id, "LATE_ERROR")

    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda bundle: dataclasses.replace(
            bundle,
            return_estimate=dataclasses.replace(
                bundle.return_estimate,
                annualized_mu=np.array([0.04]),
            ),
        ),
        lambda bundle: dataclasses.replace(
            bundle,
            covariance_estimate=dataclasses.replace(
                bundle.covariance_estimate,
                covariance=np.eye(3),
            ),
        ),
        lambda bundle: dataclasses.replace(
            bundle,
            input_lineage={"instrument_order": list(reversed(bundle.instrument_order))},
        ),
        lambda bundle: dataclasses.replace(
            bundle,
            instrument_order=(bundle.instrument_order[0], bundle.instrument_order[0]),
        ),
    ],
)
def test_complete_rejects_dimension_order_or_member_mismatch_before_save(
    repository_fixture, mutate
):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)

    with pytest.raises(EstimationIntegrityError):
        repository.complete(
            started.run_id,
            (mutate(bundle),),
            _aggregate_fingerprint(bundle),
        )

    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 0
    run = db_session.get(EstimationRun, started.run_id)
    assert run is not None and run.status == "RUNNING"


def test_complete_rejects_input_fingerprint_that_does_not_match_lineage(
    repository_fixture,
):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)

    mismatched = dataclasses.replace(bundle, input_fingerprint="b" * 64)
    with pytest.raises(EstimationIntegrityError):
        repository.complete(
            started.run_id,
            (mismatched,),
            _aggregate_fingerprint(mismatched),
        )

    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 0


def test_complete_rejects_nonannualized_result_bundle(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)
    lineage = {**bundle.input_lineage, "numeric_scale": "QUARTERLY"}
    nonannualized = dataclasses.replace(
        bundle,
        input_lineage=lineage,
        input_fingerprint=canonical_checksum(lineage),
    )

    with pytest.raises(EstimationIntegrityError):
        repository.complete(
            started.run_id,
            (nonannualized,),
            _aggregate_fingerprint(nonannualized),
        )

    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 0


def test_complete_normalizes_malformed_scalar_to_integrity_error(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    started = repository.start(identity)
    malformed_returns = dataclasses.replace(bundle.return_estimate, target_daily="bad")

    with pytest.raises(EstimationIntegrityError):
        repository.complete(
            started.run_id,
            (dataclasses.replace(bundle, return_estimate=malformed_returns),),  # type: ignore[arg-type]
            _aggregate_fingerprint(bundle),
        )

    assert db_session.scalar(select(func.count()).select_from(ReturnEstimate)) == 0


def test_approved_provider_returns_absolute_annualized_bundle_and_version_closure(
    repository_fixture,
):
    db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)

    approved = ApprovedEstimationProvider(db_session).load(completed.run_id)

    assert approved.run_id == completed.run_id
    assert approved.return_basis == "ABSOLUTE"
    assert approved.instrument_order == bundle.instrument_order
    assert np.array_equal(approved.mu, np.array([0.04, 0.05]))
    assert np.array_equal(approved.covariance, bundle.covariance_estimate.covariance)
    assert approved.estimation_method_version_id == identity.estimation_method_version_id
    assert approved.estimation_parameter_version_id == identity.estimation_parameter_version_id
    assert approved.estimation_policy_version_id == identity.estimation_policy_version_id
    assert approved.validation_policy_version_id == identity.validation_policy_version_id
    assert approved.code_version == identity.code_version


def test_approved_provider_rejects_corrupted_checksum(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)
    db_session.execute(
        text(
            """
            UPDATE portfolio.covariance_estimate
            SET covariance_payload = jsonb_set(
                covariance_payload, '{checksum}', to_jsonb(CAST(:checksum AS text))
            )
            WHERE run_id = :run_id AND return_basis = 'ABSOLUTE'
            """
        ),
        {"run_id": completed.run_id, "checksum": "f" * 64},
    )
    db_session.expire_all()

    with pytest.raises(EstimationIntegrityError):
        ApprovedEstimationProvider(db_session).load(completed.run_id)


@pytest.mark.parametrize("corrupted_value", [0.04, "0.040"])
def test_approved_provider_rejects_noncanonical_matrix_numbers(repository_fixture, corrupted_value):
    db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)
    covariance = db_session.scalar(
        select(CovarianceEstimate).where(
            CovarianceEstimate.run_id == completed.run_id,
            CovarianceEstimate.return_basis == "ABSOLUTE",
        )
    )
    assert covariance is not None
    payload = dict(covariance.covariance_payload)
    lower_triangle = list(payload["lower_triangle"])
    lower_triangle[0] = corrupted_value
    payload["lower_triangle"] = lower_triangle
    core = {key: value for key, value in payload.items() if key != "checksum"}
    payload["checksum"] = canonical_checksum(core)
    covariance.covariance_payload = payload
    db_session.flush()
    db_session.expire_all()

    with pytest.raises(EstimationIntegrityError):
        ApprovedEstimationProvider(db_session).load(completed.run_id)


@pytest.mark.parametrize(
    ("model", "field", "noncanonical"),
    [
        (ReturnEstimate, "sample_mean", "0.00010"),
        (ReturnEstimate, "shrinkage_target", "0.000150"),
        (ReturnEstimate, "shrinkage_intensity", "0.250"),
        (ReturnEstimate, "mu_before_clip", "0.040"),
        (ReturnEstimate, "mu", "0.040"),
        (RiskEstimate, "variance", "0.040"),
        (RiskEstimate, "volatility", "0.20"),
    ],
)
def test_approved_provider_rejects_noncanonical_per_fund_numeric_strings(
    repository_fixture, model, field, noncanonical
):
    db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)
    row = db_session.scalars(
        select(model).where(
            model.run_id == completed.run_id,
            model.return_basis == "ABSOLUTE",
        )
    ).first()
    assert row is not None
    setattr(row, field, noncanonical)
    db_session.flush()
    db_session.expire_all()

    with pytest.raises(EstimationIntegrityError):
        ApprovedEstimationProvider(db_session).load(completed.run_id)


def test_approved_provider_rejects_lineage_fingerprint_corruption(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)
    db_session.execute(
        text(
            """
            UPDATE portfolio.covariance_estimate
            SET input_lineage = jsonb_set(input_lineage, '{numeric_scale}', '"CORRUPTED"')
            WHERE run_id = :run_id AND return_basis = 'ABSOLUTE'
            """
        ),
        {"run_id": completed.run_id},
    )
    db_session.expire_all()

    with pytest.raises(EstimationIntegrityError):
        ApprovedEstimationProvider(db_session).load(completed.run_id)


def test_approved_provider_cannot_mix_basis_or_run(repository_fixture):
    db_session, repository, identity, bundle = repository_fixture
    completed = _complete(repository, identity, bundle)
    db_session.execute(
        text(
            """
            UPDATE portfolio.covariance_estimate
            SET return_basis = 'EXCESS'
            WHERE run_id = :run_id AND return_basis = 'ABSOLUTE'
            """
        ),
        {"run_id": completed.run_id},
    )
    db_session.expire_all()

    with pytest.raises(EstimationIntegrityError):
        ApprovedEstimationProvider(db_session).load(completed.run_id)


def test_repository_exposes_no_business_result_update_api(repository_fixture):
    _db_session, repository, _identity, _bundle = repository_fixture
    assert not any(name.startswith("update") for name in dir(repository))
