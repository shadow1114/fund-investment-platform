import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import RiskFreeRatePoint

_SERIES_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, tenor, rate, version, availability_quality
    FROM market.risk_free_rate
    WHERE currency = :currency
      AND tenor = :tenor
      AND available_at <= :visible_until
      AND effective_at BETWEEN :date_from AND :date_to
    ORDER BY effective_at, version DESC, available_at DESC, curve_code
""")


class SqlRiskFreeRatePitRepository:
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        self._session = session
        self._visible_until = visible_until

    def series(
        self,
        currency: str,
        tenor: str,
        date_from: dt.date,
        date_to: dt.date,
    ) -> tuple[RiskFreeRatePoint, ...]:
        rows = self._session.execute(
            _SERIES_SQL,
            {
                "currency": currency,
                "tenor": tenor,
                "date_from": date_from,
                "date_to": date_to,
                "visible_until": self._visible_until,
            },
        ).mappings().all()
        return tuple(
            RiskFreeRatePoint(
                row["effective_at"],
                row["tenor"],
                row["rate"],
                row["version"],
                row["availability_quality"],
            )
            for row in rows
        )
