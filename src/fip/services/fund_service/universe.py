from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.services.fund_service.models import (
    FundUniverseMember,
    FundUniverseSnapshot,
    SelectionConditionRecord,
)
from fip.services.fund_service.tier import TierStageResult
from fip.strategy_library.universe import (
    SelectionCondition,
    SelectionConditionResult,
    evaluate_candidate,
)


class TierUniverseCandidateProvider:
    def __init__(self, eligible_tiers: Sequence[str]) -> None:
        self._eligible_tiers = frozenset(eligible_tiers)

    def load(
        self, _context: DecisionExecutionContext, tiers: TierStageResult
    ) -> Sequence[tuple[int, SelectionConditionResult]]:
        return tuple(
            (
                item.share_class_id,
                evaluate_candidate(
                    (
                        SelectionCondition(
                            "tier_eligible",
                            item.status,
                            item.tier in self._eligible_tiers if item.tier is not None else None,
                        ),
                    )
                ),
            )
            for item in tiers.tiers
        )


class UniverseSnapshotConflict(ValueError):
    pass


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
        snapshot = self._session.execute(
            select(FundUniverseSnapshot).where(
                FundUniverseSnapshot.decision_id == decision_id,
                FundUniverseSnapshot.evaluation_id == evaluation_id,
            )
        ).scalar_one_or_none()
        if snapshot is not None:
            if snapshot.policy_version_id != policy_version_id:
                raise UniverseSnapshotConflict(
                    "universe snapshot key conflicts with different policy"
                )
            expected = {share_class_id: result for share_class_id, result in members}
            stored_members = self._session.execute(
                select(FundUniverseMember).where(
                    FundUniverseMember.snapshot_id == snapshot.id
                )
            ).scalars()
            stored = {member.share_class_id: member for member in stored_members}
            if set(stored) != set(expected):
                raise UniverseSnapshotConflict("universe snapshot members differ")
            for share_class_id, result in expected.items():
                member = stored[share_class_id]
                conditions = self._session.execute(
                    select(SelectionConditionRecord)
                    .where(SelectionConditionRecord.universe_member_id == member.id)
                    .order_by(SelectionConditionRecord.condition_id)
                ).scalars()
                actual_conditions = tuple(
                    (item.condition_id, item.status, item.passed) for item in conditions
                )
                expected_conditions = tuple(
                    (item.condition_id, item.status, item.passed) for item in result.conditions
                )
                if member.status != result.status or actual_conditions != expected_conditions:
                    raise UniverseSnapshotConflict("universe snapshot content differs")
            return snapshot.id
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
