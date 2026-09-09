from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext


@dataclass(frozen=True, slots=True)
class EvaluationPipelineResult:
    peer_groups: object
    factors: object
    scores: object
    rankings: object
    tiers: object
    universe: object


class EvaluationPipeline:
    """Coordinates the frozen Plan-2 stages in one database transaction."""

    def __init__(
        self,
        session: Session,
        *,
        build_peer_groups: Callable[[DecisionExecutionContext], object],
        calculate_factors: Callable[[DecisionExecutionContext, object], object],
        calculate_scores: Callable[[DecisionExecutionContext, object, object], object],
        rank: Callable[[DecisionExecutionContext, object], object],
        classify_tiers: Callable[[DecisionExecutionContext, object], object],
        build_universe: Callable[[DecisionExecutionContext, object], object],
    ) -> None:
        self._session = session
        self._build_peer_groups = build_peer_groups
        self._calculate_factors = calculate_factors
        self._calculate_scores = calculate_scores
        self._rank = rank
        self._classify_tiers = classify_tiers
        self._build_universe = build_universe

    def run(self, context: DecisionExecutionContext) -> EvaluationPipelineResult:
        with self._session.begin():
            peer_groups = self._build_peer_groups(context)
            factors = self._calculate_factors(context, peer_groups)
            scores = self._calculate_scores(context, peer_groups, factors)
            rankings = self._rank(context, scores)
            tiers = self._classify_tiers(context, rankings)
            universe = self._build_universe(context, tiers)
        return EvaluationPipelineResult(peer_groups, factors, scores, rankings, tiers, universe)
