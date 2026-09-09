import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import FeePoint

_CURRENT_SQL = text("""
    SELECT DISTINCT ON (fee_type)
           fee_type, rate, valid_from, availability_quality
    FROM fund.fund_fee
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND valid_from <= :effective_at
      AND (valid_to IS NULL OR valid_to > :effective_at)
    ORDER BY fee_type, valid_from DESC, available_at DESC, id DESC
""")


class SqlFeePitRepository:
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        self._session = session
        self._visible_until = visible_until

    def current(self, share_class_id: int) -> tuple[FeePoint, ...]:
        rows = self._session.execute(
            _CURRENT_SQL,
            {
                "share_class_id": share_class_id,
                "visible_until": self._visible_until,
                "effective_at": self._visible_until.date(),
            },
        ).mappings().all()
        return tuple(
            FeePoint(
                row["fee_type"],
                row["rate"],
                row["valid_from"],
                row["availability_quality"],
            )
            for row in rows
        )
