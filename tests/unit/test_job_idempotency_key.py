import datetime as dt

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.jobs.submitter import decision_idempotency_key, ingest_idempotency_key


def _ctx(**kw):
    base = dict(
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
    base.update(kw)
    return DecisionExecutionContext(**base)


def test_decision_key_uses_the_three_business_dimensions():
    """业务层幂等键 = (decision_at, strategy_version, recompute_scope)。"""
    key = decision_idempotency_key(_ctx())
    assert key == "decision|2026-08-31|sv-1|FULL_PIPELINE"


def test_decision_key_is_stable_across_identical_contexts():
    assert decision_idempotency_key(_ctx()) == decision_idempotency_key(_ctx())


def test_decision_key_changes_with_strategy_version():
    assert decision_idempotency_key(_ctx()) != decision_idempotency_key(
        _ctx(strategy_version="sv-2")
    )


def test_decision_key_ignores_decision_id():
    """同一 (时点, 版本, 范围) 的重复提交必须命中同一个键。"""
    assert decision_idempotency_key(_ctx(decision_id="D-1")) == \
        decision_idempotency_key(_ctx(decision_id="D-2"))


def test_ingest_key_covers_dataset_subject_and_range():
    key = ingest_idempotency_key(
        "fund_nav", "000001", dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )
    assert key == "ingest|fund_nav|000001|2020-01-01|2020-12-31"
