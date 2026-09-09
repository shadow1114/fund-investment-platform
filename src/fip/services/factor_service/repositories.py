from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.factor_service.models import FactorRun


class FactorRunConflict(ValueError):
    pass


class FactorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_run(
        self,
        *,
        decision_id: str,
        peer_group_snapshot_id: int,
        metric_version_id: int,
        evaluation_policy_version_id: int | None,
        input_quality_summary: dict[str, object],
    ) -> int:
        existing = self._session.execute(
            select(FactorRun).where(
                FactorRun.decision_id == decision_id,
                FactorRun.peer_group_snapshot_id == peer_group_snapshot_id,
                FactorRun.metric_version_id == metric_version_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.input_quality_summary != input_quality_summary:
                raise FactorRunConflict("factor run idempotency key conflicts with different input")
            return existing.id
        row = FactorRun(
            decision_id=decision_id,
            peer_group_snapshot_id=peer_group_snapshot_id,
            metric_version_id=metric_version_id,
            evaluation_policy_version_id=evaluation_policy_version_id,
            input_quality_summary=input_quality_summary,
        )
        self._session.add(row)
        self._session.flush()
        return row.id
