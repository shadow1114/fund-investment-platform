import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.decision_data.pit import PitDataContext
from fip.services.factor_service.calculation import PersistedFactorRun
from fip.services.factor_service.models import (
    FactorDefinition,
    FactorEffectiveness,
    FactorValue,
    FactorVersion,
)
from fip.services.fund_service.models import (
    FundEvaluation,
    FundScore,
    FundScoreAttribution,
    PeerGroupSnapshot,
)
from fip.services.fund_service.policy import EvaluationPolicy
from fip.strategy_library.fund_data import expense_ratio
from fip.strategy_library.normalization import normalize_factor
from fip.strategy_library.scoring import (
    ScoringItem,
    TrackingErrorInput,
    calculate_score,
    calculate_tracking_error_scores,
)

_FACTOR_ID_BY_POLICY_METRIC = {
    "alpha": "F-REL-002",
    "beta": "F-REL-003",
    "information_ratio": "F-REL-004",
    "tracking_error": "F-REL-005",
    "maximum_drawdown": "F-RISK-003",
}


class ExpenseRatioProvider(Protocol):
    def load(
        self, context: DecisionExecutionContext, share_class_ids: Sequence[int]
    ) -> Mapping[int, float | None]: ...


class PitExpenseRatioProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load(
        self, context: DecisionExecutionContext, share_class_ids: Sequence[int]
    ) -> Mapping[int, float | None]:
        fees = PitDataContext(context, self._session).fees()
        return {
            share_class_id: (
                float(expense_ratio(points)) if (points := fees.current(share_class_id)) else None
            )
            for share_class_id in share_class_ids
        }


@dataclass(frozen=True, slots=True)
class ScoreCandidate:
    share_class_id: int
    items: Sequence[ScoringItem]


@dataclass(frozen=True, slots=True)
class PersistedScore:
    score_id: int
    share_class_id: int
    value: float | None
    status: str
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class ScoringStageResult:
    evaluation_id: int
    scores: tuple[PersistedScore, ...]


class EvaluationConflict(ValueError):
    pass


class DatabaseScoreCandidateProvider:
    def __init__(
        self,
        session: Session,
        *,
        weights: Mapping[str, float],
        directions: Mapping[str, str],
        validation_policy_version_id: int,
        sample_split: str,
        profile_weights: Mapping[str, Mapping[str, float]] | None = None,
        profile_by_classification: Mapping[str, str] | None = None,
        expense_ratio_provider: ExpenseRatioProvider | None = None,
        minimum_peer_sample: int = 30,
    ) -> None:
        self._session = session
        self._weights = weights
        self._directions = directions
        self._validation_policy_version_id = validation_policy_version_id
        self._sample_split = sample_split
        self._profile_weights = profile_weights
        self._profile_by_classification = profile_by_classification or {}
        self._expense_ratio_provider = expense_ratio_provider
        self._minimum_peer_sample = minimum_peer_sample

    @classmethod
    def from_policy(
        cls,
        session: Session,
        *,
        policy: EvaluationPolicy,
        validation_policy_version_id: int,
        sample_split: str,
        profile_by_classification: Mapping[str, str],
        expense_ratio_provider: ExpenseRatioProvider,
    ) -> "DatabaseScoreCandidateProvider":
        return cls(
            session,
            weights={},
            directions={
                "F-REL-002": "HIGHER_IS_BETTER",
                "F-REL-003": "TARGET_RANGE",
                "F-REL-004": "HIGHER_IS_BETTER",
                "F-REL-005": "PROFILE_RULE",
                "F-RISK-003": "LOWER_IS_BETTER",
                "expense_ratio": "LOWER_IS_BETTER",
            },
            validation_policy_version_id=validation_policy_version_id,
            sample_split=sample_split,
            profile_weights={
                profile: {metric: float(weight) for metric, weight in weights.items()}
                for profile, weights in policy.profile_weights.items()
            },
            profile_by_classification=profile_by_classification,
            expense_ratio_provider=expense_ratio_provider,
            minimum_peer_sample=policy.minimum_peer_group_size,
        )

    def load(
        self,
        _context: DecisionExecutionContext,
        factor_run: PersistedFactorRun,
    ) -> Sequence[ScoreCandidate]:
        snapshot = self._session.get(PeerGroupSnapshot, factor_run.peer_group_snapshot_id)
        if snapshot is None:
            raise ValueError(f"peer group snapshot {factor_run.peer_group_snapshot_id} not found")
        profile = self._profile_by_classification.get(
            snapshot.classification_code,
            snapshot.classification_code.lower(),
        )
        weights = self._weights
        if self._profile_weights is not None:
            policy_weights = self._profile_weights[profile]
            weights = {
                _FACTOR_ID_BY_POLICY_METRIC.get(metric, metric): weight
                for metric, weight in policy_weights.items()
            }
        rows = self._session.execute(
            select(FactorValue, FactorDefinition.factor_id)
            .join(FactorVersion, FactorValue.factor_version_id == FactorVersion.id)
            .join(FactorDefinition, FactorVersion.factor_definition_id == FactorDefinition.id)
            .where(FactorValue.factor_run_id == factor_run.factor_run_id)
        ).all()
        effectiveness_rows = self._session.execute(
            select(FactorEffectiveness).where(
                FactorEffectiveness.peer_group_snapshot_id
                == factor_run.peer_group_snapshot_id,
                FactorEffectiveness.sample_split == self._sample_split,
                FactorEffectiveness.validation_policy_version_id
                == self._validation_policy_version_id,
            )
        ).scalars()
        effectiveness = {
            (row.factor_version_id, row.evaluation_window): row.verdict
            for row in effectiveness_rows
        }
        grouped: dict[int, list[ScoringItem]] = defaultdict(list)
        factor_rows: dict[int, dict[str, FactorValue]] = defaultdict(dict)
        for value, factor_id in rows:
            factor_rows[value.share_class_id][factor_id] = value
            if factor_id not in weights:
                continue
            grouped[value.share_class_id].append(
                ScoringItem(
                    metric_id=factor_id,
                    normalized_value=(
                        None if value.normalized_value is None else float(value.normalized_value)
                    ),
                    configured_weight=weights[factor_id],
                    effectiveness=effectiveness.get(
                        (value.factor_version_id, value.window),
                        "VALIDATION_PENDING",
                    ),
                    raw_value=None if value.raw_value is None else float(value.raw_value),
                    direction=self._directions[factor_id],
                    window=value.window,
                    reason_code=value.reason_code,
                )
            )
        if weights.get("F-REL-005", 0) > 0:
            tracking_scores = calculate_tracking_error_scores(
                tuple(
                    TrackingErrorInput(
                        share_class_id,
                        _numeric_value(values.get("F-REL-005"), "raw_value"),
                        _numeric_value(values.get("F-REL-005"), "normalized_value"),
                        information_ratio=_numeric_value(values.get("F-REL-004"), "raw_value"),
                        sharpe=_numeric_value(values.get("F-RAP-001"), "raw_value"),
                    )
                    for share_class_id, values in sorted(factor_rows.items())
                ),
                profile=profile,
                minimum_sample=self._minimum_peer_sample,
            )
            tracking_by_share = {item.share_class_id: item for item in tracking_scores}
            for share_class_id, items in grouped.items():
                grouped[share_class_id] = [
                    replace(
                        item,
                        interaction_value=tracking_by_share[share_class_id].interaction_value,
                        reason_code=tracking_by_share[share_class_id].reason_code,
                    )
                    if item.metric_id == "F-REL-005"
                    else item
                    for item in items
                ]
        if self._expense_ratio_provider is not None and weights.get("expense_ratio", 0) > 0:
            expense_values = self._expense_ratio_provider.load(
                _context,
                tuple(sorted(factor_rows)),
            )
            normalized_expenses = normalize_factor(
                tuple(
                    (share_class_id, value)
                    for share_class_id, value in expense_values.items()
                    if value is not None
                ),
                "LOWER_IS_BETTER",
                self._minimum_peer_sample,
            )
            normalized_by_share = {item.share_class_id: item for item in normalized_expenses}
            for share_class_id in sorted(factor_rows):
                raw_value = expense_values.get(share_class_id)
                normalized = normalized_by_share.get(share_class_id)
                grouped[share_class_id].append(
                    ScoringItem(
                        "expense_ratio",
                        None if normalized is None else normalized.normalized_value,
                        weights["expense_ratio"],
                        "VALID",
                        raw_value=raw_value,
                        direction="LOWER_IS_BETTER",
                        reason_code=(
                            "EXPENSE_RATIO_UNAVAILABLE"
                            if raw_value is None
                            else None if normalized is None else normalized.reason_code
                        ),
                    )
                )
        return tuple(
            ScoreCandidate(share_class_id, tuple(sorted(items, key=lambda item: item.metric_id)))
            for share_class_id, items in sorted(grouped.items())
        )


def _numeric_value(value: FactorValue | None, field: str) -> float | None:
    if value is None:
        return None
    raw = getattr(value, field)
    return None if raw is None else float(raw)


def _attribution_detail(item: ScoringItem, result_value: float | None) -> dict[str, object]:
    included = (
        result_value is not None
        and item.effectiveness == "VALID"
        and item.scoring_value is not None
        and item.configured_weight > 0
    )
    return {
        "metric_id": item.metric_id,
        "factor_id": item.metric_id,
        "window": item.window,
        "raw_value": item.raw_value,
        "normalized_value": item.normalized_value,
        "interaction_value": item.interaction_value,
        "direction": item.direction,
        "configured_weight": item.configured_weight,
        "effective_weight": None,
        "weighted_contribution": None,
        "effectiveness": item.effectiveness,
        "reason_code": item.reason_code,
        "verdict": (
            "INCLUDED"
            if included
            else "VALIDATION_PENDING"
            if item.effectiveness == "VALIDATION_PENDING"
            else "UNAVAILABLE"
            if item.scoring_value is None
            else "EXCLUDED"
        ),
    }


def calculate_and_save(
    session: Session,
    *,
    decision_id: str,
    peer_group_snapshot_id: int,
    factor_run_id: int,
    policy_version_id: int,
    candidates: Sequence[ScoreCandidate],
    minimum_factors: int,
    minimum_completeness: float,
) -> ScoringStageResult:
    evaluation = session.execute(
        select(FundEvaluation).where(
            FundEvaluation.decision_id == decision_id,
            FundEvaluation.peer_group_snapshot_id == peer_group_snapshot_id,
        )
    ).scalar_one_or_none()
    if evaluation is None:
        evaluation = FundEvaluation(
            decision_id=decision_id,
            peer_group_snapshot_id=peer_group_snapshot_id,
            factor_run_id=factor_run_id,
            policy_version_id=policy_version_id,
        )
        session.add(evaluation)
        session.flush()
    elif (
        evaluation.factor_run_id != factor_run_id
        or evaluation.policy_version_id != policy_version_id
    ):
        raise EvaluationConflict("evaluation key conflicts with different versions")
    persisted: list[PersistedScore] = []
    for candidate in candidates:
        result = calculate_score(
            candidate.items,
            minimum_factors=minimum_factors,
            minimum_completeness=minimum_completeness,
        )
        score = session.execute(
            select(FundScore).where(
                FundScore.evaluation_id == evaluation.id,
                FundScore.share_class_id == candidate.share_class_id,
            )
        ).scalar_one_or_none()
        if score is None:
            score = FundScore(
                evaluation_id=evaluation.id,
                share_class_id=candidate.share_class_id,
                value=result.value,
                status=result.status,
                reason_code=result.reason_code,
                data_completeness=result.data_completeness,
                weight_source="PROFILE_FIXED_V1",
            )
            session.add(score)
            session.flush()
        else:
            stored_value = None if score.value is None else float(score.value)
            value_matches = (
                stored_value is None
                and result.value is None
                or stored_value is not None
                and result.value is not None
                and math.isclose(stored_value, result.value, rel_tol=0.0, abs_tol=1e-10)
            )
            if (
                not value_matches
                or score.status != result.status
                or score.reason_code != result.reason_code
                or not math.isclose(
                    float(score.data_completeness),
                    result.data_completeness,
                    rel_tol=0.0,
                    abs_tol=1e-10,
                )
                or score.weight_source != "PROFILE_FIXED_V1"
            ):
                raise EvaluationConflict("score key conflicts with different result")
        usable = [
            item
            for item in candidate.items
            if result.value is not None
            and item.effectiveness == "VALID"
            and item.scoring_value is not None
            and item.configured_weight > 0
        ]
        weight_total = sum(item.configured_weight for item in usable)
        for item in candidate.items:
            detail = _attribution_detail(item, result.value)
            if item in usable and item.scoring_value is not None:
                effective_weight = item.configured_weight / weight_total
                detail["effective_weight"] = effective_weight
                detail["weighted_contribution"] = item.scoring_value * effective_weight
            attribution = session.execute(
                select(FundScoreAttribution).where(
                    FundScoreAttribution.fund_score_id == score.id,
                    FundScoreAttribution.metric_id == item.metric_id,
                )
            ).scalar_one_or_none()
            if attribution is None:
                session.add(
                    FundScoreAttribution(
                        fund_score_id=score.id,
                        metric_id=item.metric_id,
                        detail=detail,
                    )
                )
            elif attribution.detail != detail:
                raise EvaluationConflict("score attribution conflicts with different result")
        persisted.append(
            PersistedScore(
                score_id=score.id,
                share_class_id=candidate.share_class_id,
                value=result.value,
                status=result.status,
                reason_code=result.reason_code,
            )
        )
    session.flush()
    return ScoringStageResult(evaluation.id, tuple(persisted))