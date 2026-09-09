import datetime as dt

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.calculation import (
    FactorCalculationInput,
    FactorMetricParameters,
    calculate_and_save_factor_run,
)
from fip.services.factor_service.models import (
    FactorDefinition,
    FactorRun,
    FactorValue,
    FactorVersion,
)
from fip.services.fund_service.models import PeerGroupSnapshot
from fip.strategy_library.factor_types import ReturnObservation

pytestmark = pytest.mark.integration

FACTOR_IDS = (
    "F-RET-001",
    "F-RET-002",
    "F-RISK-001",
    "F-RISK-002",
    "F-RISK-003",
    "F-RAP-001",
    "F-RAP-002",
    "F-RAP-003",
    "F-STAB-001",
    "F-STAB-005",
    "F-REL-002",
    "F-REL-003",
    "F-REL-004",
    "F-REL-005",
    "F-STAB-002",
)


class FixedInputProvider:
    def __init__(self, inputs: tuple[FactorCalculationInput, ...]) -> None:
        self.inputs = inputs
        self.calls = 0

    def load(self, _context, _peer_group_snapshot_id):
        self.calls += 1
        return self.inputs


def test_factor_run_calculates_normalizes_and_persists_idempotently(db_session):
    evaluation_policy = PolicyVersion(
        policy_kind="evaluation", version_label="factor-run-eval-v1", content={}
    )
    metric_policy = PolicyVersion(
        policy_kind="metric", version_label="factor-run-metric-v1", content={}
    )
    db_session.add_all((evaluation_policy, metric_policy))
    fund = Fund(fund_code="factor-run-fund", product_name="Factor Run", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    shares = tuple(
        FundShareClass(
            fund_id=fund.id,
            share_class_code=code,
            display_name=f"Factor Run {code}",
        )
        for code in ("A", "B")
    )
    db_session.add_all(shares)
    definitions = tuple(
        FactorDefinition(
            factor_id=factor_id,
            display_name=factor_id,
            usage="DISPLAY" if factor_id == "F-STAB-002" else "SCORING",
        )
        for factor_id in FACTOR_IDS
    )
    db_session.add_all(definitions)
    db_session.flush()
    versions = tuple(
        FactorVersion(
            factor_definition_id=definition.id,
            version_label="v1",
            parameters={"window": "3Y"},
        )
        for definition in definitions
    )
    db_session.add_all(versions)
    peer = PeerGroupSnapshot(
        decision_id="factor-run-decision",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=evaluation_policy.id,
        classification_code="ACTIVE_EQUITY",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=2,
    )
    db_session.add(peer)
    db_session.flush()
    start = dt.date(2026, 1, 1)
    benchmark = tuple(
        ReturnObservation(
            start + dt.timedelta(days=index),
            (-0.01, 0.005, 0.015)[index % 3],
        )
        for index in range(60)
    )
    risk_free = tuple(ReturnObservation(item.effective_at, 0.0001) for item in benchmark)
    provider = FixedInputProvider(
        tuple(
            FactorCalculationInput(
                share_class_id=share.id,
                window="3Y",
                fund_returns=tuple(
                    ReturnObservation(
                        item.effective_at,
                        item.value * multiplier + (index % 2) * 0.0002,
                    )
                    for index, item in enumerate(benchmark)
                ),
                benchmark_returns=benchmark,
                risk_free_returns=risk_free,
                annualized_risk_free=0.02,
                daily_mar=0.0,
                    adjustment_policy_version="adjusted-nav-v1",
                input_quality_summary={"quality": "EXACT"},
            )
            for share, multiplier in zip(shares, (1.1, 0.9), strict=True)
        )
    )
    context = DecisionExecutionContext(
        decision_id="factor-run-decision",
        decision_at=dt.date(2026, 9, 8),
        data_as_of=dt.date(2026, 9, 8),
        strategy_version="strategy-v1",
        policy_version="evaluation-v1",
        code_version="code-v1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    kwargs = {
        "peer_group_snapshot_id": peer.id,
        "input_provider": provider,
        "metric_version_id": metric_policy.id,
        "evaluation_policy_version_id": evaluation_policy.id,
        "factor_version_ids": {
            definition.factor_id: version.id
            for definition, version in zip(definitions, versions, strict=True)
        },
        "normalization_directions": {
            factor_id: (
                "LOWER_IS_BETTER"
                if factor_id in {"F-RISK-001", "F-RISK-002", "F-RISK-003", "F-REL-005"}
                else "HIGHER_IS_BETTER"
            )
            for factor_id in FACTOR_IDS
        },
        "minimum_peer_sample": 2,
        "parameters": FactorMetricParameters(252, 50, 60, 10, 3),
        "beta_target_range": (0.85, 1.15),
    }

    first = calculate_and_save_factor_run(db_session, context, **kwargs)
    second = calculate_and_save_factor_run(db_session, context, **kwargs)

    assert provider.calls == 2
    assert first.factor_run_id == second.factor_run_id
    assert [item.factor_value_id for item in first.values] == [
        item.factor_value_id for item in second.values
    ]
    assert db_session.query(FactorRun).count() == 1
    assert db_session.query(FactorValue).count() == 30
    assert {item.factor_id for item in first.values} == set(FACTOR_IDS)
    assert all(item.normalized_value is not None for item in first.values)
    persisted_values = db_session.query(FactorValue).all()
    assert all(item.input_lineage == {"quality": "EXACT"} for item in persisted_values)
    assert all(
        item.adjustment_policy_version == "adjusted-nav-v1" for item in persisted_values
    )