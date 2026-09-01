import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.services.data_service.normalization.adjusted_nav import (
    AdjustedNavUnavailable,
    DistributionEvent,
    NavObservation,
    compute_adjusted_nav,
)

_NAV_SQL = text("""
    SELECT DISTINCT ON (effective_at) effective_at, unit_nav, version
    FROM market.fund_nav
    WHERE share_class_id = :share_class_id AND available_at <= :visible_until
    ORDER BY effective_at, version DESC
""")

_EVENT_SQL = text("""
    SELECT DISTINCT ON (effective_at) effective_at, dividend_per_unit, split_ratio
    FROM market.fund_distribution
    WHERE share_class_id = :share_class_id AND available_at <= :visible_until
    ORDER BY effective_at, version DESC
""")

_UPDATE_SQL = text("""
    UPDATE market.fund_nav
    SET adjusted_nav = :adjusted_nav
    WHERE share_class_id = :share_class_id
      AND effective_at = :effective_at
      AND version = :version
""")


def backfill_adjusted_nav(
    session: Session, share_class_id: int, decision_at: dt.date
) -> int:
    """按 decision_at 可见的净值与事件计算复权净值并回填。

    事件日缺净值时抛 AdjustedNavUnavailable —— 该份额类别的 adjusted_nav
    保持为 NULL，下游据此标记 UNAVAILABLE，【不填 0、不沿用上期】（C-6）。
    """
    visible_until = dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)
    params = {"share_class_id": share_class_id, "visible_until": visible_until}

    nav_rows = session.execute(_NAV_SQL, params).mappings().all()
    if not nav_rows:
        return 0
    event_rows = session.execute(_EVENT_SQL, params).mappings().all()

    points = compute_adjusted_nav(
        [NavObservation(r["effective_at"], r["unit_nav"]) for r in nav_rows],
        [
            DistributionEvent(r["effective_at"], r["dividend_per_unit"], r["split_ratio"])
            for r in event_rows
        ],
    )

    version_by_date = {r["effective_at"]: r["version"] for r in nav_rows}
    for point in points:
        session.execute(_UPDATE_SQL, {
            "adjusted_nav": point.adjusted_nav,
            "share_class_id": share_class_id,
            "effective_at": point.effective_at,
            "version": version_by_date[point.effective_at],
        })
    session.flush()
    return len(points)


__all__ = ["AdjustedNavUnavailable", "backfill_adjusted_nav"]
