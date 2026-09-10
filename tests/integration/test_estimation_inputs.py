import datetime as dt
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.models.benchmark import (
    BenchmarkComponent,
    BenchmarkDefinition,
    BenchmarkIndex,
    BenchmarkIndexValue,
    BenchmarkMapping,
)
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationHistory,
    FundShareClass,
)
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.data_service.models.market import FundNav
from fip.services.factor_service.repositories import FactorRepository
from fip.services.fund_service.models import (
    FundEvaluation,
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupSnapshot,
)
from fip.services.portfolio_service.estimation.inputs import EstimationInputAssembler
from fip.services.portfolio_service.estimation.policy import load_estimation_policy

pytestmark = pytest.mark.integration

SWITCH_DATE = dt.date(2026, 1, 9)
MISSING_COMPONENT_DATES = (dt.date(2026, 1, 5), dt.date(2026, 1, 6))
UNAVAILABLE_COMPONENT_DATE = dt.date(2026, 1, 4)


def _utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC)


def _times(available_at: dt.date) -> dict[str, object]:
    return {
        "available_at": _utc(available_at),
        "availability_quality": "INFERRED",
        "published_at": None,
        "provider_available_at": None,
        "ingested_at": _utc(dt.date(2026, 1, 15)),
    }


def _context() -> DecisionExecutionContext:
    decision_at = dt.date(2026, 1, 15)
    return DecisionExecutionContext(
        decision_id="D-ESTIMATION-INPUTS",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="strategy-v1",
        policy_version="policy-v1",
        code_version="code-v1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def _add_index(
    session,
    *,
    symbol: str,
    index_type: str,
    levels: dict[dt.date, str],
) -> BenchmarkIndex:
    index = BenchmarkIndex(
        provider_code="TEST",
        provider_symbol=symbol,
        display_name=symbol,
        currency="CNY",
        index_type=index_type,
    )
    session.add(index)
    session.flush()
    session.add_all(
        BenchmarkIndexValue(
            index_id=index.id,
            effective_at=day,
            version=1,
            value=Decimal(value),
            **_times(day + dt.timedelta(days=1)),
        )
        for day, value in levels.items()
    )
    return index


def _add_benchmark(
    session,
    *,
    code: str,
    components: tuple[tuple[BenchmarkIndex, str], ...],
) -> BenchmarkDefinition:
    benchmark = BenchmarkDefinition(benchmark_code=code, display_name=code)
    session.add(benchmark)
    session.flush()
    session.add_all(
        BenchmarkComponent(
            benchmark_id=benchmark.id,
            index_id=index.id,
            weight=Decimal(weight),
        )
        for index, weight in components
    )
    return benchmark


@pytest.fixture()
def estimation_fixture(db_session):
    context = _context()
    policy = replace(
        load_estimation_policy(Path("config/policy/estimation/v1.yaml"), RuntimeMode.BACKTEST),
        lookback_trading_days=10,
    )
    governance = PolicyVersion(
        policy_kind="evaluation",
        version_label="estimation-input-fixture-v1",
        content={},
    )
    db_session.add(governance)
    db_session.flush()

    funds = (
        Fund(fund_code="EST-IN-1", product_name="Estimation 1", grouping_status="CONFIRMED"),
        Fund(fund_code="EST-IN-2", product_name="Estimation 2", grouping_status="CONFIRMED"),
    )
    db_session.add_all(funds)
    db_session.flush()
    shares = (
        FundShareClass(fund_id=funds[0].id, share_class_code="A", display_name="Estimation 1 A"),
        FundShareClass(fund_id=funds[1].id, share_class_code="A", display_name="Estimation 2 A"),
    )
    db_session.add_all(shares)
    db_session.flush()
    db_session.add_all(
        (
            FundClassificationHistory(
                fund_id=funds[0].id,
                classification_scheme="FIP_INTERNAL_L2",
                classification_code="HYBRID",
                valid_from=dt.date(2025, 1, 1),
                valid_to=None,
                **_times(dt.date(2025, 1, 1)),
            ),
            FundClassificationHistory(
                fund_id=funds[1].id,
                classification_scheme="FIP_INTERNAL_L2",
                classification_code="BOND",
                valid_from=dt.date(2025, 1, 1),
                valid_to=None,
                **_times(dt.date(2025, 1, 1)),
            ),
        )
    )

    days = tuple(dt.date(2026, 1, day) for day in range(2, 13))
    nav_levels = (
        tuple(str(100 + 2 * offset) for offset in range(len(days))),
        tuple(str(200 + 3 * offset) for offset in range(len(days))),
    )
    db_session.add_all(
        FundNav(
            share_class_id=share.id,
            effective_at=day,
            version=1,
            unit_nav=Decimal(value),
            **_times(day + dt.timedelta(days=1)),
        )
        for share, levels in zip(shares, nav_levels, strict=True)
        for day, value in zip(days, levels, strict=True)
    )

    old_equity = _add_index(
        db_session,
        symbol="OLD-EQUITY",
        index_type="TOTAL_RETURN",
        levels={day: str(100 + 2 * offset) for offset, day in enumerate(days[:7])},
    )
    old_bond = _add_index(
        db_session,
        symbol="OLD-BOND",
        index_type="FULL_PRICE",
        # Deliberately absent on 2026-01-05 and 2026-01-06: the composite must
        # be unavailable, rather than filled or recalculated using OLD-EQUITY.
        levels={
            day: str(200 + 2 * offset)
            for offset, day in enumerate(days[:7])
            if day not in MISSING_COMPONENT_DATES
        },
    )
    new_equity = _add_index(
        db_session,
        symbol="NEW-EQUITY",
        index_type="TOTAL_RETURN",
        levels={day: str(300 + 3 * offset) for offset, day in enumerate(days[7:])},
    )
    new_bond = _add_index(
        db_session,
        symbol="NEW-BOND",
        index_type="FULL_PRICE",
        levels={day: str(400 + 4 * offset) for offset, day in enumerate(days[7:])},
    )
    bond_only = _add_index(
        db_session,
        symbol="BOND-ONLY",
        index_type="FULL_PRICE",
        levels={day: str(500 + 5 * offset) for offset, day in enumerate(days)},
    )
    hybrid_v1 = _add_benchmark(
        db_session,
        code="EST-HYBRID-V1",
        components=((old_equity, "0.6"), (old_bond, "0.4")),
    )
    hybrid_v2 = _add_benchmark(
        db_session,
        code="EST-HYBRID-V2",
        components=((new_equity, "0.5"), (new_bond, "0.5")),
    )
    bond = _add_benchmark(
        db_session,
        code="EST-BOND",
        components=((bond_only, "1"),),
    )
    db_session.add_all(
        (
            BenchmarkMapping(
                benchmark_id=hybrid_v1.id,
                share_class_id=None,
                classification_code="HYBRID",
                mapping_source="CLASSIFICATION",
                mapping_version="hybrid-v1",
                valid_from=dt.date(2025, 1, 1),
                valid_to=SWITCH_DATE,
                **_times(dt.date(2025, 1, 1)),
            ),
            BenchmarkMapping(
                benchmark_id=hybrid_v2.id,
                share_class_id=None,
                classification_code="HYBRID",
                mapping_source="CLASSIFICATION",
                mapping_version="hybrid-v2",
                valid_from=SWITCH_DATE,
                valid_to=None,
                **_times(dt.date(2025, 12, 1)),
            ),
            BenchmarkMapping(
                benchmark_id=bond.id,
                share_class_id=None,
                classification_code="BOND",
                mapping_source="CLASSIFICATION",
                mapping_version="bond-v1",
                valid_from=dt.date(2025, 1, 1),
                valid_to=None,
                **_times(dt.date(2025, 1, 1)),
            ),
        )
    )

    peer = PeerGroupSnapshot(
        decision_id=context.decision_id,
        decision_at=context.decision_at,
        policy_version_id=governance.id,
        classification_code="ACTIVE_EQUITY",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=2,
    )
    db_session.add(peer)
    db_session.flush()
    factor_run_id = FactorRepository(db_session).save_run(
        decision_id=context.decision_id,
        peer_group_snapshot_id=peer.id,
        metric_version_id=governance.id,
        evaluation_policy_version_id=governance.id,
        input_quality_summary={},
    )
    evaluation = FundEvaluation(
        decision_id=context.decision_id,
        peer_group_snapshot_id=peer.id,
        factor_run_id=factor_run_id,
        policy_version_id=governance.id,
    )
    db_session.add(evaluation)
    db_session.flush()
    snapshot = FundUniverseSnapshot(
        decision_id=context.decision_id,
        evaluation_id=evaluation.id,
        policy_version_id=governance.id,
    )
    db_session.add(snapshot)
    db_session.flush()
    # Reverse insertion order proves the assembler consumes the explicit ordered read.
    db_session.add_all(
        FundUniverseMember(snapshot_id=snapshot.id, share_class_id=share.id, status="SELECTED")
        for share in reversed(shares)
    )
    db_session.flush()
    return context, snapshot.id, policy, tuple(share.id for share in shares), old_bond.id


def _assembler(db_session) -> EstimationInputAssembler:
    return EstimationInputAssembler(
        db_session,
        adjustment_policy_version="adjusted-nav-v1",
        estimation_method_version="method-v1",
        estimation_parameter_version="parameter-v1",
        validation_policy_version="validation-v1",
    )


class _UnavailableQualityBenchmarkRepository:
    def __init__(self, delegate, unavailable_index_id: int) -> None:
        self._delegate = delegate
        self._unavailable_index_id = unavailable_index_id

    def resolve_history(self, share_class_id, classification_code, date_from, date_to):
        return self._delegate.resolve_history(
            share_class_id, classification_code, date_from, date_to
        )

    def index_series(self, index_id, date_from, date_to):
        observations = self._delegate.index_series(index_id, date_from, date_to)
        return tuple(
            (
                day,
                value,
                version,
                "UNAVAILABLE"
                if index_id == self._unavailable_index_id
                and day == UNAVAILABLE_COMPONENT_DATE
                else quality,
            )
            for day, value, version, quality in observations
        )


def test_basis_inputs_are_independently_aligned(db_session, estimation_fixture):
    context, snapshot_id, policy, share_class_ids, _old_bond_id = estimation_fixture

    absolute, excess = _assembler(db_session).load(context, snapshot_id, policy)

    assert absolute.return_basis == "ABSOLUTE"
    assert excess.return_basis == "EXCESS"
    assert absolute.status == "AVAILABLE"
    assert excess.status == "AVAILABLE"
    assert absolute.instrument_order == tuple(sorted(share_class_ids))
    assert excess.instrument_order == tuple(sorted(share_class_ids))
    assert absolute.observation_dates != excess.observation_dates
    assert SWITCH_DATE in absolute.observation_dates
    assert SWITCH_DATE not in excess.observation_dates
    assert set(MISSING_COMPONENT_DATES) <= set(absolute.observation_dates)
    assert not set(MISSING_COMPONENT_DATES) & set(excess.observation_dates)
    assert absolute.matrix.shape == (10, 2)
    # Exact acceptance boundary: T=6 and N=2, so T == 3N is available.
    assert excess.matrix.shape == (6, 2)
    assert excess.rejection_reason is None
    assert SWITCH_DATE in excess.dropped_dates
    assert excess.lineage["warnings"] == [
        {
            "code": "BENCHMARK_MAPPING_SWITCH",
            "dates": [SWITCH_DATE.isoformat()],
        }
    ]
    np.testing.assert_allclose(excess.matrix[0, 0], 0.02 - (142 / 140 - 1))

    # The BOND fund must use its own PIT classification fallback, not the peer
    # group's ACTIVE_EQUITY classification or the first fund's HYBRID mapping.
    assert excess.lineage["instruments"][str(share_class_ids[1])]["classification"][
        "classification_code"
    ] == "BOND"
    assert excess.lineage["instruments"][str(share_class_ids[1])]["benchmark_segments"][0][
        "mapping_version"
    ] == "bond-v1"


def test_lineage_and_fingerprints_cover_the_pit_inputs(db_session, estimation_fixture):
    context, snapshot_id, policy, share_class_ids, _old_bond_id = estimation_fixture

    absolute, excess = _assembler(db_session).load(context, snapshot_id, policy)
    repeated_absolute, repeated_excess = _assembler(db_session).load(
        context, snapshot_id, policy
    )

    assert absolute.observation_fingerprint == repeated_absolute.observation_fingerprint
    assert excess.observation_fingerprint == repeated_excess.observation_fingerprint
    assert absolute.basis_fingerprint == repeated_absolute.basis_fingerprint
    assert excess.basis_fingerprint == repeated_excess.basis_fingerprint
    assert absolute.basis_fingerprint != excess.basis_fingerprint
    assert absolute.lineage["universe_snapshot_id"] == snapshot_id
    assert absolute.lineage["adjustment_policy_version"] == "adjusted-nav-v1"
    assert absolute.lineage["estimation_method_version"] == "method-v1"
    assert absolute.lineage["estimation_parameter_version"] == "parameter-v1"
    assert absolute.lineage["estimation_policy_version"] == "v1"
    assert absolute.lineage["validation_policy_version"] == "validation-v1"
    assert absolute.lineage["code_version"] == context.code_version
    assert absolute.lineage["observation_fingerprint"] == absolute.observation_fingerprint
    assert absolute.lineage["window"] == {
        "lookback_trading_days": 10,
        "type": "ROLLING",
    }
    assert absolute.lineage["forecast_horizon"] == "QUARTER"
    assert absolute.lineage["numeric_scale"] == "ANNUALIZED"
    assert absolute.lineage["return_basis"] == "ABSOLUTE"
    assert excess.lineage["return_basis"] == "EXCESS"
    assert excess.lineage["benchmark_switch_dates"] == [SWITCH_DATE.isoformat()]
    assert excess.lineage["instruments"][str(share_class_ids[0])]["nav_observations"][0] == {
        "share_class_id": share_class_ids[0],
        "effective_at": "2026-01-02",
        "value": "100.00000000",
        "version": 1,
        "availability_quality": "INFERRED",
        "chain_availability_quality": "INFERRED",
    }
    first_segment = excess.lineage["instruments"][str(share_class_ids[0])][
        "benchmark_segments"
    ][0]
    assert [item["weight"] for item in first_segment["components"]] == [
        "0.60000000",
        "0.40000000",
    ]
    assert (
        first_segment["index_observations"][1]["observations"][-1]["effective_at"]
        == "2026-01-08"
    )
    assert np.isfinite(absolute.matrix).all()
    assert np.isfinite(excess.matrix).all()


def test_basis_below_three_times_n_is_explicitly_rejected(db_session, estimation_fixture):
    context, snapshot_id, policy, share_class_ids, _old_bond_id = estimation_fixture
    short_policy = replace(policy, lookback_trading_days=5)

    absolute, excess = _assembler(db_session).load(context, snapshot_id, short_policy)

    for basis in (absolute, excess):
        assert basis.status == "REJECTED"
        assert basis.rejection_reason == "INSUFFICIENT_COMPLETE_CASES"
        assert basis.matrix.shape == (0, 0)
        assert basis.instrument_order == ()
        assert basis.observation_dates == ()
        assert basis.lineage["instrument_order"] == list(sorted(share_class_ids))
        assert basis.lineage["status"] == "REJECTED"
        assert basis.lineage["rejection_reason"] == "INSUFFICIENT_COMPLETE_CASES"
    assert absolute.lineage["data_completeness"]["observation_count"] == 5
    assert len(absolute.lineage["observation_dates"]) == 5
    assert excess.lineage["data_completeness"]["observation_count"] == 4


def test_unavailable_index_observation_breaks_composite_chain(
    db_session, estimation_fixture, monkeypatch
):
    context, snapshot_id, policy, _share_class_ids, old_bond_id = estimation_fixture
    real_benchmarks = PitDataContext.benchmarks

    def benchmarks_with_unavailable_observation(pit):
        return _UnavailableQualityBenchmarkRepository(real_benchmarks(pit), old_bond_id)

    monkeypatch.setattr(
        PitDataContext,
        "benchmarks",
        benchmarks_with_unavailable_observation,
    )

    absolute, excess = _assembler(db_session).load(
        context,
        snapshot_id,
        replace(policy, minimum_t_over_n=2),
    )

    assert absolute.status == "AVAILABLE"
    assert excess.status == "AVAILABLE"
    assert UNAVAILABLE_COMPONENT_DATE in absolute.observation_dates
    assert UNAVAILABLE_COMPONENT_DATE not in excess.observation_dates
    unavailable_observation = excess.lineage["instruments"][
        str(absolute.instrument_order[0])
    ]["benchmark_segments"][0]["index_observations"][1]["observations"][2]
    assert unavailable_observation == {
        "effective_at": UNAVAILABLE_COMPONENT_DATE.isoformat(),
        "value": "204.00000000",
        "version": 1,
        "availability_quality": "UNAVAILABLE",
    }
