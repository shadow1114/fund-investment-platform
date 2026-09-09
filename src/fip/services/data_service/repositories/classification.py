import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import ClassificationPoint

CLASSIFICATION_SCHEME = "FIP_INTERNAL_L2"

_CURRENT_SQL = text("""
    SELECT classification_code, valid_from, availability_quality
    FROM fund.fund_classification_history
    WHERE fund_id = :fund_id
      AND classification_scheme = :classification_scheme
      AND available_at <= :visible_until
      AND valid_from <= :effective_at
      AND (valid_to IS NULL OR valid_to > :effective_at)
    ORDER BY valid_from DESC, available_at DESC, id DESC
    LIMIT 1
""")


class SqlClassificationPitRepository:
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        self._session = session
        self._visible_until = visible_until

    def current(self, fund_id: int) -> ClassificationPoint | None:
        row = self._session.execute(
            _CURRENT_SQL,
            {
                "fund_id": fund_id,
                "classification_scheme": CLASSIFICATION_SCHEME,
                "visible_until": self._visible_until,
                "effective_at": self._visible_until.date(),
            },
        ).mappings().first()
        if row is None:
            return None
        return ClassificationPoint(
            row["classification_code"],
            row["valid_from"],
            row["availability_quality"],
        )
