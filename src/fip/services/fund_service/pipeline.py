from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.services.factor_service.calculation import (
    FactorInputProvider,
    FactorMetricParameters,
    PersistedFactorRun,
    PitFactorInputProvider,
    calculate_and_save_factor_run,
)
from fip.services.factor_service.validation import (
    EffectivenessEvidence,
    validate_and_save_effectiveness_series,
)
from fip.services.fund_service.peer_group.service import PeerGroupStage, PeerGroupStageResult
from fip.services.fund_service.policy import EvaluationPolicy, ValidationPolicy
from fip.services.fund_service.ranking import RankingStageResult, rank_and_save
from fip.services.fund_service.scoring import ScoreCandidate, ScoringStageResult, calculate_and_save
from fip.services.fund_service.tier import TierStageResult, classify_and_save
from fip.services.fund_service.universe import UniverseRepository
from fip.strategy_library.universe import SelectionConditionResult
from fip.strategy_library.validation import EffectivenessThresholds

PeerGroupsT = TypeVar("PeerGroupsT")
FactorsT = TypeVar("FactorsT")
ScoresT = TypeVar("ScoresT")
RankingsT = TypeVar("RankingsT")
TiersT = TypeVar("TiersT")
UniverseT = TypeVar("UniverseT")


@dataclass(frozen=True, slots=True)
class EvaluationPipelineResult(
    Generic[PeerGroupsT, FactorsT, ScoresT, RankingsT, TiersT, UniverseT]
):
    peer_groups: PeerGroupsT
    factors: FactorsT
    scores: ScoresT
    rankings: RankingsT
    tiers: TiersT
    universe: UniverseT


@dataclass(frozen=True, slots=True)
class FactorStageResult:
    runs: tuple[PersistedFactorRun, ...]


class EffectivenessObservationProvider(Protocol):
    def load(
        self,
        context: DecisionExecutionContext,
        factor_run: PersistedFactorRun,
    ) -> Mapping[tuple[str, str], EffectivenessEvidence]: ...


class FactorPipelineStage:
    def __init__(
        self,
        session: Session,
        *,
        input_provider: FactorInputProvider,
        metric_version_id: int,
        evaluation_policy_version_id: int,
        factor_version_ids: Mapping[str, int],
        normalization_directions: Mapping[str, str],
        minimum_peer_sample: int,
        parameters: FactorMetricParameters,
        effectiveness_provider: EffectivenessObservationProvider,
        validation_policy_version_id: int,
        validation_sample_split: str,
        validation_thresholds: EffectivenessThresholds,
        beta_target_ranges: Mapping[str, tuple[float, float]] | None = None,
        require_both_segments: bool = True,
    ) -> None:
        self._session = session
        self._input_provider = input_provider
        self._metric_version_id = metric_version_id
        self._evaluation_policy_version_id = evaluation_policy_version_id
        self._factor_version_ids = factor_version_ids
        self._normalization_directions = normalization_directions
        self._minimum_peer_sample = minimum_peer_sample
        self._parameters = parameters
        self._effectiveness_provider = effectiveness_provider
        self._validation_policy_version_id = validation_policy_version_id
        self._validation_sample_split = validation_sample_split
        self._validation_thresholds = validation_thresholds
        self._beta_target_ranges = beta_target_ranges or {}
        self._require_both_segments = require_both_segments

    @classmethod
    def from_policy(
        cls,
        session: Session,
        *,
        policy: EvaluationPolicy,
        validation_policy: ValidationPolicy,
        metric_version_id: int,
        evaluation_policy_version_id: int,
        validation_policy_version_id: int,
        factor_version_ids: Mapping[str, int],
        normalization_directions: Mapping[str, str],
        parameters: FactorMetricParameters,
        effectiveness_provider: EffectivenessObservationProvider,
        validation_sample_split: str,
        window: str,
        lookback_calendar_days: int,
        risk_free_tenor: str,
        adjustment_policy_version: str,
    ) -> "FactorPipelineStage":
        return cls(
            session,
            input_provider=PitFactorInputProvider(
                session,
                window=window,
                lookback_calendar_days=lookback_calendar_days,
                risk_free_tenor=risk_free_tenor,
                annualization=parameters.annualization,
                daily_mar=float(policy.mar),
                adjustment_policy_version=adjustment_policy_version,
            ),
            metric_version_id=metric_version_id,
            evaluation_policy_version_id=evaluation_policy_version_id,
            factor_version_ids=factor_version_ids,
            normalization_directions=normalization_directions,
            minimum_peer_sample=policy.minimum_peer_group_size,
            parameters=parameters,
            effectiveness_provider=effectiveness_provider,
            validation_policy_version_id=validation_policy_version_id,
            validation_sample_split=validation_sample_split,
            validation_thresholds=EffectivenessThresholds(
                ic_mean_min=float(validation_policy.ic_mean_min),
                icir_abs_min=float(validation_policy.icir_abs_min),
                minimum_cross_sections=validation_policy.min_cross_sections,
                ic_std_ddof=validation_policy.ic_std_ddof,
                redundancy_threshold=float(validation_policy.redundancy_threshold),
            ),
            beta_target_ranges={
                profile: (float(bounds[0]), float(bounds[1]))
                for profile, bounds in policy.beta_target_ranges.items()
            },
            require_both_segments=validation_policy.require_both_segments,
        )

    def run(
        self, context: DecisionExecutionContext, peer_groups: PeerGroupStageResult
    ) -> FactorStageResult:
        runs: list[PersistedFactorRun] = []
        for group in peer_groups.groups:
            factor_run = calculate_and_save_factor_run(
                self._session,
                context,
                peer_group_snapshot_id=group.snapshot_id,
                input_provider=self._input_provider,
                metric_version_id=self._metric_version_id,
                evaluation_policy_version_id=self._evaluation_policy_version_id,
                factor_version_ids=self._factor_version_ids,
                normalization_directions=self._normalization_directions,
                minimum_peer_sample=self._minimum_peer_sample,
                parameters=self._parameters,
                beta_target_range=self._beta_target_ranges.get(
                    group.draft.key.classification_code.lower()
                ),
            )
            observations = self._effectiveness_provider.load(context, factor_run)
            factor_windows = sorted(
                {(value.factor_id, value.window) for value in factor_run.values}
            )
            for factor_id, window in factor_windows:
                validate_and_save_effectiveness_series(
                    self._session,
                    factor_version_id=self._factor_version_ids[factor_id],
                    peer_group_snapshot_id=group.snapshot_id,
                    evaluation_window=window,
                    sample_split=self._validation_sample_split,
                    validation_policy_version_id=self._validation_policy_version_id,
                    evidence=observations.get(
                        (factor_id, window),
                        EffectivenessEvidence((), (), "POSITIVE"),
                    ),
                    thresholds=self._validation_thresholds,
                    require_both_segments=self._require_both_segments,
                )
            runs.append(factor_run)
        return FactorStageResult(tuple(runs))


class ScoreCandidateProvider(Protocol):
    def load(
        self,
        context: DecisionExecutionContext,
        factor_run: PersistedFactorRun,
    ) -> Sequence[ScoreCandidate]: ...


@dataclass(frozen=True, slots=True)
class ScoringPipelineResult:
    stages: tuple[ScoringStageResult, ...]


class ScoringPipelineStage:
    def __init__(
        self,
        session: Session,
        *,
        candidate_provider: ScoreCandidateProvider,
        policy_version_id: int,
        minimum_factors: int,
        minimum_completeness: float,
    ) -> None:
        self._session = session
        self._candidate_provider = candidate_provider
        self._policy_version_id = policy_version_id
        self._minimum_factors = minimum_factors
        self._minimum_completeness = minimum_completeness

    def run(
        self,
        context: DecisionExecutionContext,
        peer_groups: PeerGroupStageResult,
        factors: FactorStageResult,
    ) -> ScoringPipelineResult:
        if len(peer_groups.groups) != len(factors.runs):
            raise ValueError("peer group and factor run counts differ")
        stages = tuple(
            calculate_and_save(
                self._session,
                decision_id=context.decision_id,
                peer_group_snapshot_id=group.snapshot_id,
                factor_run_id=factor_run.factor_run_id,
                policy_version_id=self._policy_version_id,
                candidates=self._candidate_provider.load(context, factor_run),
                minimum_factors=self._minimum_factors,
                minimum_completeness=self._minimum_completeness,
            )
            for group, factor_run in zip(peer_groups.groups, factors.runs, strict=True)
        )
        return ScoringPipelineResult(stages)


@dataclass(frozen=True, slots=True)
class RankingPipelineResult:
    stages: tuple[RankingStageResult, ...]


class RankingPipelineStage:
    def __init__(self, session: Session, *, minimum_sample: int) -> None:
        self._session = session
        self._minimum_sample = minimum_sample

    def run(
        self, _context: DecisionExecutionContext, scores: ScoringPipelineResult
    ) -> RankingPipelineResult:
        return RankingPipelineResult(
            tuple(
                rank_and_save(self._session, stage, minimum_sample=self._minimum_sample)
                for stage in scores.stages
            )
        )


@dataclass(frozen=True, slots=True)
class TierPipelineResult:
    stages: tuple[TierStageResult, ...]


class TierPipelineStage:
    def __init__(self, session: Session, *, minimum_sample: int) -> None:
        self._session = session
        self._minimum_sample = minimum_sample

    def run(
        self, _context: DecisionExecutionContext, rankings: RankingPipelineResult
    ) -> TierPipelineResult:
        return TierPipelineResult(
            tuple(
                classify_and_save(self._session, stage, minimum_sample=self._minimum_sample)
                for stage in rankings.stages
            )
        )


class UniverseCandidateProvider(Protocol):
    def load(
        self,
        context: DecisionExecutionContext,
        tiers: TierStageResult,
    ) -> Sequence[tuple[int, SelectionConditionResult]]: ...


@dataclass(frozen=True, slots=True)
class UniversePipelineResult:
    snapshot_ids: tuple[int, ...]


class UniversePipelineStage:
    def __init__(
        self,
        session: Session,
        *,
        candidate_provider: UniverseCandidateProvider,
        policy_version_id: int,
    ) -> None:
        self._repository = UniverseRepository(session)
        self._candidate_provider = candidate_provider
        self._policy_version_id = policy_version_id

    def run(
        self, context: DecisionExecutionContext, tiers: TierPipelineResult
    ) -> UniversePipelineResult:
        return UniversePipelineResult(
            tuple(
                self._repository.save(
                    decision_id=context.decision_id,
                    evaluation_id=stage.evaluation_id,
                    policy_version_id=self._policy_version_id,
                    members=self._candidate_provider.load(context, stage),
                )
                for stage in tiers.stages
            )
        )


@dataclass(frozen=True, slots=True)
class EvaluationPipelineStages:
    peer_groups: PeerGroupStage
    factors: FactorPipelineStage
    scoring: ScoringPipelineStage
    ranking: RankingPipelineStage
    tier: TierPipelineStage
    universe: UniversePipelineStage


class EvaluationPipeline(Generic[PeerGroupsT, FactorsT, ScoresT, RankingsT, TiersT, UniverseT]):
    """Coordinates the frozen Plan-2 stages in one database transaction."""

    def __init__(
        self,
        session: Session,
        *,
        build_peer_groups: Callable[[DecisionExecutionContext], PeerGroupsT],
        calculate_factors: Callable[[DecisionExecutionContext, PeerGroupsT], FactorsT],
        calculate_scores: Callable[[DecisionExecutionContext, PeerGroupsT, FactorsT], ScoresT],
        rank: Callable[[DecisionExecutionContext, ScoresT], RankingsT],
        classify_tiers: Callable[[DecisionExecutionContext, RankingsT], TiersT],
        build_universe: Callable[[DecisionExecutionContext, TiersT], UniverseT],
    ) -> None:
        self._session = session
        self._build_peer_groups = build_peer_groups
        self._calculate_factors = calculate_factors
        self._calculate_scores = calculate_scores
        self._rank = rank
        self._classify_tiers = classify_tiers
        self._build_universe = build_universe

    def run(
        self, context: DecisionExecutionContext
    ) -> EvaluationPipelineResult[PeerGroupsT, FactorsT, ScoresT, RankingsT, TiersT, UniverseT]:
        with self._session.begin():
            peer_groups = self._build_peer_groups(context)
            factors = self._calculate_factors(context, peer_groups)
            scores = self._calculate_scores(context, peer_groups, factors)
            rankings = self._rank(context, scores)
            tiers = self._classify_tiers(context, rankings)
            universe = self._build_universe(context, tiers)
        return EvaluationPipelineResult(peer_groups, factors, scores, rankings, tiers, universe)


def assemble_evaluation_pipeline(
    session: Session, stages: EvaluationPipelineStages
) -> EvaluationPipeline[
    PeerGroupStageResult,
    FactorStageResult,
    ScoringPipelineResult,
    RankingPipelineResult,
    TierPipelineResult,
    UniversePipelineResult,
]:
    return EvaluationPipeline(
        session,
        build_peer_groups=stages.peer_groups.run,
        calculate_factors=stages.factors.run,
        calculate_scores=stages.scoring.run,
        rank=stages.ranking.run,
        classify_tiers=stages.tier.run,
        build_universe=stages.universe.run,
    )
