import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from fip.services.data_service.normalization.adjusted_nav import (
    AdjustedNavUnavailable,
    DistributionEvent,
    NavObservation,
    compute_adjusted_nav,
)

# 与 Step 3 的 PIT 查询不同：这里取【全部】在 decision_at 可见的版本
# （不做 DISTINCT ON 版本折叠），因为回填需要为每个版本分别计算它在
# 「自己成为当前版本」到「被下一版本取代」这段时间里应有的复权净值——
# 只回填 decision_at 那一刻折叠出的单一版本，会让被取代的旧版本的
# adjusted_nav 永远停留在 NULL（见 Task 15 fix round 1）。
_ALL_NAV_SQL = text("""
    SELECT effective_at, unit_nav, version, available_at
    FROM market.fund_nav
    WHERE share_class_id = :share_class_id AND available_at <= :visible_until
    ORDER BY effective_at, version
""")

_ALL_EVENT_SQL = text("""
    SELECT effective_at, dividend_per_unit, split_ratio, version, available_at
    FROM market.fund_distribution
    WHERE share_class_id = :share_class_id AND available_at <= :visible_until
    ORDER BY effective_at, version
""")

_UPDATE_SQL = text("""
    UPDATE market.fund_nav
    SET adjusted_nav = :adjusted_nav
    WHERE share_class_id = :share_class_id
      AND effective_at = :effective_at
      AND version = :version
""")


def _resolve_current(
    rows: Sequence[RowMapping], visible_until: dt.datetime
) -> dict[dt.date, RowMapping]:
    """PIT 版本解析：对每个 effective_at，在 available_at <= visible_until
    的行中取 version 最大者。与 SqlNavPitRepository 使用的是同一条规则，
    只是这里在 Python 侧对一份已取回的行集合重复应用它——因为本函数需要
    在多个 checkpoint（而非仅 decision_at 一个时点）上分别解析当前版本。
    """
    current: dict[dt.date, RowMapping] = {}
    for row in rows:
        if row["available_at"] > visible_until:
            continue
        existing = current.get(row["effective_at"])
        if existing is None or row["version"] > existing["version"]:
            current[row["effective_at"]] = row
    return current


def backfill_adjusted_nav(
    session: Session, share_class_id: int, decision_at: dt.date
) -> int:
    """按 decision_at 可见的净值与事件计算复权净值并回填。

    每个 (effective_at, version) 行都会被回填，值取「该版本成为当前
    版本、直到被下一版本取代」这段时期内、随着更多净值/事件披露而演进
    出的最终已知值——即以该版本的 reign 内所见过的最新 checkpoint 为准。
    这样任何决策时点解析到的行都带有正确的复权净值，而不只是
    decision_at 折叠出的那一个版本。

    做法：取 decision_at 可见的全部净值/事件行（不折叠版本），把两者的
    available_at 并集排序为一组 checkpoint；在每个 checkpoint 上重新做
    PIT 版本解析并调用 compute_adjusted_nav，把结果写给该 checkpoint 下
    解析出的「当前」(effective_at, version)。checkpoint 按时间升序处理，
    同一行被更晚的 checkpoint 覆盖是有意为之——它代表该版本在被取代前
    最后已知的正确值。

    先在内存里算完全部 checkpoint 再统一执行 UPDATE：只要某个 checkpoint
    的计算抛出 AdjustedNavUnavailable，整次回填就不会有任何写入
    （与回填单一 decision_at 时点的原有语义一致，见 C-6）——该份额类别
    的 adjusted_nav 保持为 NULL，下游据此标记 UNAVAILABLE，不填 0、
    不沿用上期。
    """
    visible_until = dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)
    params = {"share_class_id": share_class_id, "visible_until": visible_until}

    nav_rows = session.execute(_ALL_NAV_SQL, params).mappings().all()
    if not nav_rows:
        return 0
    event_rows = session.execute(_ALL_EVENT_SQL, params).mappings().all()

    checkpoints = sorted(
        {row["available_at"] for row in nav_rows}
        | {row["available_at"] for row in event_rows}
    )

    writes: dict[tuple[dt.date, int], Decimal | None] = {}
    for checkpoint in checkpoints:
        current_navs = _resolve_current(nav_rows, checkpoint)
        if not current_navs:
            continue
        current_events = _resolve_current(event_rows, checkpoint)

        points = compute_adjusted_nav(
            [
                NavObservation(effective_at, row["unit_nav"])
                for effective_at, row in current_navs.items()
            ],
            [
                DistributionEvent(
                    effective_at, row["dividend_per_unit"], row["split_ratio"]
                )
                for effective_at, row in current_events.items()
            ],
        )

        for point in points:
            version = current_navs[point.effective_at]["version"]
            writes[(point.effective_at, version)] = point.adjusted_nav

    for (effective_at, version), adjusted_nav in writes.items():
        session.execute(
            _UPDATE_SQL,
            {
                "adjusted_nav": adjusted_nav,
                "share_class_id": share_class_id,
                "effective_at": effective_at,
                "version": version,
            },
        )
    session.flush()
    return len(writes)


__all__ = ["AdjustedNavUnavailable", "backfill_adjusted_nav"]
