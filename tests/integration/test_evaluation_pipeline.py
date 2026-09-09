import datetime as dt

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import DataProvider, PolicyVersion
from fip.services.factor_service.calculation import FactorCalculationInput, FactorMetricParameters
from fip.services.factor_service.models import (
    FactorDefinition,
    FactorEffectiveness,
    FactorRun,
    FactorValue,
    FactorVersion,
)
from fip.services.factor_service.validation import EffectivenessEvidence
from fip.services.fund_service.models import (
    FundEvaluation,
    FundRanking,
    FundScore,
    FundTier,
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupSnapshot,
)
from fip.services.fund_service.peer_group.models import PeerGroupCandidate, PeerGroupKey
from fip.services.fund_service.peer_group.service import PeerGroupStage
from fip.services.fund_service.pipeline import (
    EvaluationPipeline,
    EvaluationPipelineStages,
    FactorPipelineStage,
    RankingPipelineStage,
    ScoringPipelineStage,
    TierPipelineStage,
    UniversePipelineStage,
    assemble_evaluation_pipeline,
)
from fip.services.fund_service.scoring import DatabaseScoreCandidateProvider
from fip.services.fund_service.universe import TierUniverseCandidateProvider
from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.validation import EffectivenessThresholds

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


class FixedPeerCandidateProvider:
    def __init__(self, share_class_ids):
        self._share_class_ids = share_class_ids

    def load(self, _context):
        return tuple(
            PeerGroupCandidate(
                share_class_id,
                PeerGroupKey("ACTIVE_EQUITY", "CNY"),
                "CONFIRMED",
            )
            for share_class_id in self._share_class_ids
        )


class FixedFactorInputProvider:
    def __init__(self, inputs):
        self._inputs = inputs

    def load(self, _context, _peer_group_snapshot_id):
        return self._inputs


class FixedEffectivenessProvider:
    def load(self, _context, factor_run):
        return {
            (value.factor_id, value.window): EffectivenessEvidence(
                (0.1, 0.2, 0.3),
                (0.01, 0.02, 0.03, 0.04, 0.05),
                "POSITIVE",
                recent_ic_series=(0.1, 0.2, 0.3),
                recent_layer_returns=(0.01, 0.02, 0.03, 0.04, 0.05),
            )
            for value in factor_run.values
        }


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


def test_assembled_pipeline_persists_the_complete_evaluation_chain(db_session):
    evaluation_policy = PolicyVersion(
        policy_kind="evaluation", version_label="pipeline-evaluation-v1", content={}
    )
    metric_policy = PolicyVersion(
        policy_kind="metric", version_label="pipeline-metric-v1", content={}
    )
    validation_policy = PolicyVersion(
        policy_kind="validation", version_label="pipeline-validation-v1", content={}
    )
    db_session.add_all((evaluation_policy, metric_policy, validation_policy))
    fund = Fund(fund_code="pipeline-fund", product_name="Pipeline", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    shares = tuple(
        FundShareClass(
            fund_id=fund.id,
            share_class_code=code,
            display_name=f"Pipeline {code}",
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
    db_session.flush()
    evaluation_policy_id = evaluation_policy.id
    metric_policy_id = metric_policy.id
    validation_policy_id = validation_policy.id
    share_ids = tuple(share.id for share in shares)
    factor_version_ids = {
        definition.factor_id: version.id
        for definition, version in zip(definitions, versions, strict=True)
    }
    db_session.commit()

    start = dt.date(2026, 1, 1)
    benchmark = tuple(
        ReturnObservation(
            start + dt.timedelta(days=index),
            (-0.01, 0.005, 0.015)[index % 3],
        )
        for index in range(60)
    )
    risk_free = tuple(ReturnObservation(item.effective_at, 0.0001) for item in benchmark)
    factor_inputs = tuple(
        FactorCalculationInput(
            share_class_id=share_class_id,
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
        for share_class_id, multiplier in zip(share_ids, (1.1, 0.9), strict=True)
    )
    directions = {
        factor_id: (
            "LOWER_IS_BETTER"
            if factor_id in {"F-RISK-001", "F-RISK-002", "F-RISK-003", "F-REL-005"}
            else "HIGHER_IS_BETTER"
        )
        for factor_id in FACTOR_IDS
    }
    sample_split = "2025-01-01/2026-09-08"
    stages = EvaluationPipelineStages(
        peer_groups=PeerGroupStage(
            db_session,
            candidate_provider=FixedPeerCandidateProvider(share_ids),
            supported_profiles={"ACTIVE_EQUITY": "active_equity"},
            policy_version_id=evaluation_policy_id,
        ),
        factors=FactorPipelineStage(
            db_session,
            input_provider=FixedFactorInputProvider(factor_inputs),
            metric_version_id=metric_policy_id,
            evaluation_policy_version_id=evaluation_policy_id,
            factor_version_ids=factor_version_ids,
            normalization_directions=directions,
            minimum_peer_sample=2,
            parameters=FactorMetricParameters(252, 50, 60, 10, 3),
            effectiveness_provider=FixedEffectivenessProvider(),
            validation_policy_version_id=validation_policy_id,
            validation_sample_split=sample_split,
            validation_thresholds=EffectivenessThresholds(0.02, 0.3, 3, 1, 0.8),
            beta_target_ranges={"active_equity": (0.85, 1.15)},
        ),
        scoring=ScoringPipelineStage(
            db_session,
            candidate_provider=DatabaseScoreCandidateProvider(
                db_session,
                weights={"F-REL-002": 0.6, "F-RISK-003": 0.4},
                directions=directions,
                validation_policy_version_id=validation_policy_id,
                sample_split=sample_split,
            ),
            policy_version_id=evaluation_policy_id,
            minimum_factors=2,
            minimum_completeness=1.0,
        ),
        ranking=RankingPipelineStage(db_session, minimum_sample=2),
        tier=TierPipelineStage(db_session, minimum_sample=2),
        universe=UniversePipelineStage(
            db_session,
            candidate_provider=TierUniverseCandidateProvider(("A",)),
            policy_version_id=evaluation_policy_id,
        ),
    )
    context = DecisionExecutionContext(
        decision_id="assembled-pipeline",
        decision_at=dt.date(2026, 9, 8),
        data_as_of=dt.date(2026, 9, 8),
        strategy_version="strategy-v1",
        policy_version="pipeline-evaluation-v1",
        code_version="code-v1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )

    pipeline = assemble_evaluation_pipeline(db_session, stages)
    result = pipeline.run(context)
    repeated = pipeline.run(context)

    assert len(result.peer_groups.groups) == 1
    assert result == repeated
    assert db_session.query(PeerGroupSnapshot).count() == 1
    assert db_session.query(FactorRun).count() == 1
    assert db_session.query(FactorValue).count() == 30
    assert db_session.query(FactorEffectiveness).count() == 15
    assert all(
        row.detail["icir"] is not None for row in db_session.query(FactorEffectiveness).all()
    )
    assert db_session.query(FundEvaluation).count() == 1
    assert db_session.query(FundScore).count() == 2
    assert db_session.query(FundRanking).count() == 2
    assert db_session.query(FundTier).count() == 2
    assert db_session.query(FundUniverseSnapshot).count() == 1
    assert db_session.query(FundUniverseMember).count() == 2
