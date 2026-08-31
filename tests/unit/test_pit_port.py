import datetime as dt
import inspect
import re

import pytest

from fip.platform.decision_data import pit as pit_module
from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.current import CurrentViewContext
from fip.platform.decision_data.pit import NavPitRepository, PitDataContext


def _ctx():
    return DecisionExecutionContext(
        decision_id="D-1",
        decision_at=dt.date(2026, 8, 31),
        data_as_of=dt.date(2026, 8, 31),
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.LIVE,
    )


def test_pit_context_binds_decision_at_at_construction():
    """PIT-A2：decision_at 在构造期绑定，而非查询期传入。"""
    ctx = PitDataContext(context=_ctx(), session=object())
    assert ctx.decision_at == dt.date(2026, 8, 31)


def test_pit_context_cannot_be_built_without_execution_context():
    """PIT-A2：缺 decision_at 时在【构造期】即失败，而不是查询期。"""
    with pytest.raises(TypeError):
        PitDataContext(session=object())  # type: ignore[call-arg]


def test_repository_methods_do_not_accept_a_time_parameter():
    """时点不是方法参数 —— 否则调用方可以省略它。"""
    sig = inspect.signature(NavPitRepository.adjusted_nav_series)
    forbidden = {"decision_at", "as_of", "as_of_date", "available_at"}
    assert not (set(sig.parameters) & forbidden)


def test_no_unconstrained_latest_access_path():
    """PIT-A3：PIT 模块中不得存在『取最新 / 取当前』的方法。"""
    pattern = re.compile(r"\b(get|fetch|load|read)_(latest|current|newest)\b")
    assert not pattern.search(inspect.getsource(pit_module)), \
        "PIT 模块出现了无约束的取最新路径"


def test_pit_and_current_contexts_are_not_interchangeable():
    """PIT-A4：两种视图在接口层面区分，互不兼容。"""
    assert not issubclass(CurrentViewContext, PitDataContext)
    assert not issubclass(PitDataContext, CurrentViewContext)
    assert not hasattr(CurrentViewContext, "decision_at")
