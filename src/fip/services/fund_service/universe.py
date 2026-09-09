from collections.abc import Sequence

from sqlalchemy.orm import Session

from fip.services.fund_service.models import (
    FundUniverseMember,
    FundUniverseSnapshot,
    SelectionConditionRecord,
)
from fip.strategy_library.universe import SelectionConditionResult


class UniverseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        *,
        decision_id: str,
        evaluation_id: int,
        policy_version_id: int,
        members: Sequence[tuple[int, SelectionConditionResult]],
    ) -> int:
        snapshot = FundUniverseSnapshot(
            decision_id=decision_id,
            evaluation_id=evaluation_id,
            policy_version_id=policy_version_id,
        )
        self._session.add(snapshot)
        self._session.flush()
        for share_class_id, result in members:
            member = FundUniverseMember(
                snapshot_id=snapshot.id,
                share_class_id=share_class_id,
                status=result.status,
            )
            self._session.add(member)
            self._session.flush()
            self._session.add_all(
                SelectionConditionRecord(
                    universe_member_id=member.id,
                    condition_id=condition.condition_id,
                    status=condition.status,
                    passed=condition.passed,
                )
                for condition in result.conditions
            )
        self._session.flush()
        return snapshot.id
