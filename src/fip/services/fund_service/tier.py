from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.fund_service.models import FundTier
from fip.services.fund_service.ranking import RankingStageResult
from fip.strategy_library.tier import classify_tier


@dataclass(frozen=True, slots=True)
class PersistedTier:
    tier_id: int
    share_class_id: int
    tier: str | None
    status: str


@dataclass(frozen=True, slots=True)
class TierStageResult:
    evaluation_id: int
    tiers: tuple[PersistedTier, ...]


class TierConflict(ValueError):
    pass


def classify_and_save(
    session: Session, stage: RankingStageResult, *, minimum_sample: int
) -> TierStageResult:
    n_effective = sum(item.status == "AVAILABLE" for item in stage.rankings)
    persisted: list[PersistedTier] = []
    for item in stage.rankings:
        result = classify_tier(
            rank=item.rank,
            n_effective=n_effective,
            minimum_sample=minimum_sample,
        )
        row = session.execute(
            select(FundTier).where(
                FundTier.evaluation_id == stage.evaluation_id,
                FundTier.share_class_id == item.share_class_id,
            )
        ).scalar_one_or_none()
        if row is None:
            row = FundTier(
                evaluation_id=stage.evaluation_id,
                share_class_id=item.share_class_id,
                tier=result.tier,
                status=result.status,
            )
            session.add(row)
            session.flush()
        elif row.tier != result.tier or row.status != result.status:
            raise TierConflict("tier key conflicts with different result")
        persisted.append(
            PersistedTier(row.id, item.share_class_id, result.tier, result.status)
        )
    return TierStageResult(stage.evaluation_id, tuple(persisted))