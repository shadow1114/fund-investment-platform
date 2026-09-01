import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import NavPoint

_SERIES_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, unit_nav, adjusted_nav, version, availability_quality
    FROM market.fund_nav
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND effective_at BETWEEN :date_from AND :date_to
    ORDER BY effective_at, version DESC
""")


class SqlNavPitRepository:
    """PIT NAV 访问的 SQL 实现。

    decision_at 在【构造期】注入，方法签名中不出现时点参数 —— 调用方
    无法省略它，也无法绕过它取到未来数据（PIT-A2 / PIT-A3）。

    版本解析：对每个 effective_at，在 available_at ≤ decision_at 的行中
    取 version 最大者。这实现了上游原则二的「取 available_at ≤ decision_at
    中的最新版本」。
    """

    def __init__(self, session: Session, decision_at: dt.date) -> None:
        self._session = session
        self._decision_at = decision_at

    def adjusted_nav_series(
        self,
        share_class_id: int,
        date_from: dt.date,
        date_to: dt.date,
    ) -> list[NavPoint]:
        # decision_at 是业务日期；可见性判定取该日终了时刻。
        visible_until = dt.datetime.combine(
            self._decision_at, dt.time.max, tzinfo=dt.UTC
        )
        rows = self._session.execute(
            _SERIES_SQL,
            {
                "share_class_id": share_class_id,
                "visible_until": visible_until,
                "date_from": date_from,
                "date_to": date_to,
            },
        ).mappings().all()
        return [
            NavPoint(
                effective_at=row["effective_at"],
                adjusted_nav=row["adjusted_nav"],
                unit_nav=row["unit_nav"],
                version=row["version"],
                availability_quality=row["availability_quality"],
            )
            for row in rows
        ]
