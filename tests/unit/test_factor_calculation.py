import datetime as dt

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.services.factor_service.calculation import (
    FactorCalculationInput,
    FactorMetricParameters,
    calculate_factor_run,
)
from fip.strategy_library.factor_types import ReturnObservation


class StubInputProvider:
    def __init__(self, inputs: tuple[FactorCalculationInput, ...]) -> None:
        self.inputs = inputs
        self.calls: list[tuple[str, int]] = []

    def load(self, context: DecisionExecutionContext, peer_group_snapshot_id: int):
        self.calls.append((context.decision_id, peer_group_snapshot_id))
        return self.inputs


def test_factor_run_calculates_all_fifteen_factors_from_pit_inputs():
    start = dt.date(2026, 1, 1)
    benchmark = tuple(
        ReturnObservation(start + dt.timedelta(days=index), 0.001 + (index % 3) * 0.0004)
        for index in range(60)
    )
    fund = tuple(
        ReturnObservation(point.effective_at, point.value * 1.1 + (index % 2) * 0.0002)
        for index, point in enumerate(benchmark)
    )
    risk_free = tuple(
        ReturnObservation(point.effective_at, 0.0001) for point in benchmark
    )
    provider = StubInputProvider(
        (
            FactorCalculationInput(
                share_class_id=101,
                window="3Y",
                fund_returns=fund,
                benchmark_returns=benchmark,
                risk_free_returns=risk_free,
                annualized_risk_free=0.02,
                daily_mar=0.0,
                adjustment_policy_version="adjusted-nav-v1",
                input_quality_summary={"quality": "EXACT"},
            ),
        )
    )
    context = DecisionExecutionContext(
        decision_id="factor-run-test",
        decision_at=dt.date(2026, 9, 8),
        data_as_of=dt.date(2026, 9, 8),
        strategy_version="strategy-v1",
        policy_version="evaluation-v1",
        code_version="code-v1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )

    result = calculate_factor_run(
        context,
        peer_group_snapshot_id=7,
        input_provider=provider,
        metric_version_id=11,
        parameters=FactorMetricParameters(
            annualization=252,
            minimum_observations=50,
            regression_minimum_observations=60,
            rolling_window=10,
            rolling_minimum_valid_points=3,
        ),
    )

    assert provider.calls == [("factor-run-test", 7)]
    assert result.decision_id == "factor-run-test"
    assert result.metric_version_id == 11
    assert {value.factor.factor_id for value in result.values} == {
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
    }
    assert all(value.share_class_id == 101 for value in result.values)
    assert all(value.factor.observations == 60 for value in result.values)