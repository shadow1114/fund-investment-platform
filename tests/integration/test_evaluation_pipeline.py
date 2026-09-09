import datetime as dt

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.services.data_service.models.governance import DataProvider
from fip.services.fund_service.pipeline import EvaluationPipeline

pytestmark = pytest.mark.integration


def test_pipeline_rolls_back_prior_stage_when_later_stage_fails(db_session):
    def build_peer_groups(_context):
        db_session.add(DataProvider(provider_code="PIPELINE_TEST", display_name="Pipeline"))
        return ()

    def fail_factors(_context, _groups):
        raise RuntimeError("injected failure")

    pipeline = EvaluationPipeline(
        db_session,
        build_peer_groups=build_peer_groups,
        calculate_factors=fail_factors,
        calculate_scores=lambda _context, _groups, _factors: (),
        rank=lambda _context, _scores: (),
        classify_tiers=lambda _context, _rankings: (),
        build_universe=lambda _context, _tiers: (),
    )
    context = DecisionExecutionContext(
        decision_id="pipeline-test",
        decision_at=dt.date(2026, 9, 8),
        data_as_of=dt.date(2026, 9, 8),
        strategy_version="v1",
        policy_version="v1",
        code_version="test",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    with pytest.raises(RuntimeError, match="injected failure"):
        pipeline.run(context)
    assert db_session.query(DataProvider).filter_by(provider_code="PIPELINE_TEST").count() == 0
