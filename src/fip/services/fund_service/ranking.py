import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.fund_service.models import FundRanking
from fip.services.fund_service.scoring import ScoringStageResult
from fip.strategy_library.ranking import rank_peer_group


@dataclass(frozen=True, slots=True)
class PersistedRanking:
    ranking_id: int
    share_class_id: int
    rank: float | None
    status: str


@dataclass(frozen=True, slots=True)
class RankingStageResult:
    evaluation_id: int
    rankings: tuple[PersistedRanking, ...]


class RankingConflict(ValueError):
    pass


def rank_and_save(
    session: Session, stage: ScoringStageResult, *, minimum_sample: int
) -> RankingStageResult:
    results = rank_peer_group(
        tuple((score.share_class_id, score.value) for score in stage.scores),
        minimum_sample,
    )
    persisted: list[PersistedRanking] = []
    for result in results:
        row = session.execute(
            select(FundRanking).where(
                FundRanking.evaluation_id == stage.evaluation_id,
                FundRanking.share_class_id == result.share_class_id,
            )
        ).scalar_one_or_none()
        if row is None:
            row = FundRanking(
                evaluation_id=stage.evaluation_id,
                share_class_id=result.share_class_id,
                rank=result.rank,
                status=result.status,
            )
            session.add(row)
            session.flush()
        else:
            stored_rank = None if row.rank is None else float(row.rank)
            rank_matches = (
                stored_rank is None
                and result.rank is None
                or stored_rank is not None
                and result.rank is not None
                and math.isclose(stored_rank, result.rank, rel_tol=0.0, abs_tol=1e-10)
            )
            if not rank_matches or row.status != result.status:
                raise RankingConflict("ranking key conflicts with different result")
        persisted.append(
            PersistedRanking(row.id, result.share_class_id, result.rank, result.status)
        )
    return RankingStageResult(stage.evaluation_id, tuple(persisted))