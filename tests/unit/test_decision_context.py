import dataclasses
import datetime as dt

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)


def _ctx(**overrides):
    base = dict(
        decision_id="D-2026-0831-01",
        decision_at=dt.date(2026, 8, 31),
        data_as_of=dt.date(2026, 8, 31),
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.LIVE,
    )
    base.update(overrides)
    return DecisionExecutionContext(**base)


def test_context_is_frozen():
    """上下文在链路起点创建后贯穿全程，不得在中途被改写（DEC-1）。"""
    ctx = _ctx()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.decision_at = dt.date(2026, 9, 1)  # type: ignore[misc]


def test_decision_at_is_required():
    with pytest.raises(TypeError):
        DecisionExecutionContext(  # type: ignore[call-arg]
            decision_id="D-1",
            data_as_of=dt.date(2026, 8, 31),
            strategy_version="sv-1",
            policy_version="pv-1",
            code_version="cv-1",
            trigger_type=TriggerType.PERIODIC,
            recompute_scope=RecomputeScope.FULL_PIPELINE,
            runtime_mode=RuntimeMode.LIVE,
        )


def test_data_as_of_cannot_exceed_decision_at():
    """data_as_of 晚于 decision_at 即为未来信息泄漏。"""
    with pytest.raises(ValueError, match="data_as_of"):
        _ctx(data_as_of=dt.date(2026, 9, 1))


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        (TriggerType.PERIODIC, RecomputeScope.FULL_PIPELINE),
        (TriggerType.ELIGIBILITY_EVENT, RecomputeScope.FROM_UNIVERSE),
        (TriggerType.DRIFT, RecomputeScope.FROM_RISK),
        (TriggerType.CONSTRAINT_BREACH, RecomputeScope.FROM_CONSTRUCTION),
    ],
)
def test_scope_is_determined_by_trigger_type(trigger, expected):
    """重算深度由触发类型决定，不得在运行时动态调整（FR-REBAL-001 BR-2）。"""
    assert DecisionExecutionContext.scope_for(trigger) is expected


def test_mismatched_scope_is_rejected():
    with pytest.raises(ValueError, match="recompute_scope"):
        _ctx(trigger_type=TriggerType.DRIFT,
             recompute_scope=RecomputeScope.FULL_PIPELINE)
