from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.factor_service.models import FactorEffectiveness
from fip.strategy_library.validation import (
    EffectivenessThresholds,
    FactorEffectivenessResult,
    validate_effectiveness,
    validate_effectiveness_series,
)


class FactorEffectivenessConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PersistedFactorEffectiveness:
    effectiveness_id: int
    verdict: str
    detail: dict[str, object]


@dataclass(frozen=True, slots=True)
class EffectivenessEvidence:
    ic_series: Sequence[float]
    layer_returns: Sequence[float]
    expected_direction: str
    redundant_with: tuple[str, float] | None = None
    recent_ic_series: Sequence[float] = ()
    recent_layer_returns: Sequence[float] = ()


def _save_effectiveness(
    session: Session,
    *,
    factor_version_id: int,
    peer_group_snapshot_id: int,
    evaluation_window: str,
    sample_split: str,
    validation_policy_version_id: int,
    result: FactorEffectivenessResult,
    detail: dict[str, object] | None = None,
) -> PersistedFactorEffectiveness:
    detail = asdict(result) if detail is None else detail
    existing = session.execute(
        select(FactorEffectiveness).where(
            FactorEffectiveness.factor_version_id == factor_version_id,
            FactorEffectiveness.peer_group_snapshot_id == peer_group_snapshot_id,
            FactorEffectiveness.evaluation_window == evaluation_window,
            FactorEffectiveness.sample_split == sample_split,
            FactorEffectiveness.validation_policy_version_id == validation_policy_version_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.verdict != result.verdict or existing.detail != detail:
            raise FactorEffectivenessConflict(
                "factor effectiveness key conflicts with different result"
            )
        return PersistedFactorEffectiveness(existing.id, existing.verdict, existing.detail)
    row = FactorEffectiveness(
        factor_version_id=factor_version_id,
        peer_group_snapshot_id=peer_group_snapshot_id,
        evaluation_window=evaluation_window,
        sample_split=sample_split,
        validation_policy_version_id=validation_policy_version_id,
        verdict=result.verdict,
        detail=detail,
    )
    session.add(row)
    session.flush()
    return PersistedFactorEffectiveness(row.id, row.verdict, row.detail)


def validate_and_save_effectiveness(
    session: Session,
    *,
    factor_version_id: int,
    peer_group_snapshot_id: int,
    evaluation_window: str,
    sample_split: str,
    validation_policy_version_id: int,
    observations: Sequence[tuple[float, float]],
    minimum_observations: int,
) -> PersistedFactorEffectiveness:
    result = validate_effectiveness(
        observations,
        minimum_observations=minimum_observations,
    )
    return _save_effectiveness(
        session,
        factor_version_id=factor_version_id,
        peer_group_snapshot_id=peer_group_snapshot_id,
        evaluation_window=evaluation_window,
        sample_split=sample_split,
        validation_policy_version_id=validation_policy_version_id,
        result=result,
    )


def validate_and_save_effectiveness_series(
    session: Session,
    *,
    factor_version_id: int,
    peer_group_snapshot_id: int,
    evaluation_window: str,
    sample_split: str,
    validation_policy_version_id: int,
    evidence: EffectivenessEvidence,
    thresholds: EffectivenessThresholds,
    require_both_segments: bool = False,
) -> PersistedFactorEffectiveness:
    full_history = validate_effectiveness_series(
        evidence.ic_series,
        layer_returns=evidence.layer_returns,
        expected_direction=evidence.expected_direction,
        thresholds=thresholds,
        redundant_with=evidence.redundant_with,
    )
    result = full_history
    detail: dict[str, object] | None = None
    if require_both_segments:
        recent_3y = validate_effectiveness_series(
            evidence.recent_ic_series,
            layer_returns=evidence.recent_layer_returns,
            expected_direction=evidence.expected_direction,
            thresholds=thresholds,
            redundant_with=evidence.redundant_with,
        )
        if full_history.verdict == "VALID" and recent_3y.verdict != "VALID":
            result = FactorEffectivenessResult(
                recent_3y.ic,
                recent_3y.icir,
                recent_3y.monotonic,
                recent_3y.redundancy_group,
                recent_3y.verdict,
                f"RECENT_3Y_{recent_3y.reason_code}",
            )
        detail = {
            **asdict(result),
            "segments": {
                "full_history": asdict(full_history),
                "recent_3y": asdict(recent_3y),
            },
            "require_both": True,
        }
    return _save_effectiveness(
        session,
        factor_version_id=factor_version_id,
        peer_group_snapshot_id=peer_group_snapshot_id,
        evaluation_window=evaluation_window,
        sample_split=sample_split,
        validation_policy_version_id=validation_policy_version_id,
        result=result,
        detail=detail,
    )