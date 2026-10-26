"""PIT classification adapter for the existing evaluation boundary."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.decision_data.pit import visible_until_for
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.repositories.classification import SqlClassificationPitRepository
from fip.services.fund_service.peer_group.models import PeerGroupCandidate, PeerGroupKey


class SqlClassificationCandidateProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self, context: DecisionExecutionContext) -> tuple[PeerGroupCandidate, ...]:
        return self.at(visible_until_for(context.decision_at))

    def at(self, decision_at: dt.datetime) -> tuple[PeerGroupCandidate, ...]:
        repository = SqlClassificationPitRepository(self._session, decision_at)
        rows = (
            self._session.execute(
                select(Fund, FundShareClass).join(FundShareClass).order_by(FundShareClass.id)
            )
            .tuples()
            .all()
        )
        candidates = []
        for fund, share in rows:
            point = repository.current(fund.id)
            reason = point.exclusion_reason if point else "CLASSIFICATION_MISSING"
            candidates.append(
                PeerGroupCandidate(
                    share.id,
                    PeerGroupKey(point.classification_code, share.base_currency)
                    if point and not reason
                    else None,
                    fund.grouping_status,
                    "UNSUPPORTED_CLASSIFICATION" if reason else None,
                    reason,
                    point.revision_id if point else None,
                    point.mapping_version if point else None,
                )
            )
        return tuple(candidates)
