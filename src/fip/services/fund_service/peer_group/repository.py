import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.fund_service.models import PeerGroupMember, PeerGroupSnapshot
from fip.services.fund_service.peer_group.models import PeerGroupDraft


class PeerGroupSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        *,
        decision_id: str,
        decision_at: dt.date,
        policy_version_id: int,
        draft: PeerGroupDraft,
    ) -> int:
        row = self._session.execute(
            select(PeerGroupSnapshot).where(
                PeerGroupSnapshot.decision_id == decision_id,
                PeerGroupSnapshot.classification_code == draft.key.classification_code,
                PeerGroupSnapshot.base_currency == draft.key.base_currency,
            )
        ).scalar_one_or_none()
        if row is not None:
            if row.member_count != len(draft.member_ids):
                raise ValueError("peer group snapshot key conflicts with different members")
            return row.id
        row = PeerGroupSnapshot(
            decision_id=decision_id,
            decision_at=decision_at,
            policy_version_id=policy_version_id,
            classification_code=draft.key.classification_code,
            base_currency=draft.key.base_currency,
            status="AVAILABLE",
            member_count=len(draft.member_ids),
        )
        self._session.add(row)
        self._session.flush()
        self._session.add_all(
            PeerGroupMember(snapshot_id=row.id, share_class_id=member_id, status="INCLUDED")
            for member_id in draft.member_ids
        )
        self._session.flush()
        return row.id
