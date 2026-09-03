"""复权净值的【运维物化】回填。

本模块产出的是运维物化值，**不是 PIT 真值来源**。

「正确的复权净值」是 (行, decision_at) 的二元函数：同一净值行在不同决策
时点应有不同的复权值，因为它之后可能又披露了迟到的分红/拆分事件。
market.fund_nav.adjusted_nav 是每行一个标量，装不下这个二元函数 —— 无论
选哪个时刻盖章都会错一边（见下面 backfill_adjusted_nav 的 docstring）。

因此自 Task 15 fix round 3 起，决策链路读到的复权净值由
SqlNavPitRepository.adjusted_nav_series 按 decision_at 【现算】，不再读本
模块写进列里的值。本列保留的用途是排查与快速目视核对：它让人不必跑一遍
计算就能看到某一行大致的复权水平。任何决策链路都不得读它。
"""

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import resolve_visible_until
from fip.services.data_service.normalization.adjusted_nav import (
    AdjustedNavUnavailable,
    DistributionEvent,
    NavObservation,
    compute_adjusted_nav,
)

# 与 Step 3 的 PIT 查询不同：这里取【全部】在 decision_at 可见的版本
# （不做 DISTINCT ON 版本折叠），因为回填需要为每个版本分别计算它
# 【首次成为当前版本】那一刻应有的复权净值——只回填 decision_at 那一刻
# 折叠出的单一版本，会让被取代的旧版本的 adjusted_nav 永远停留在
# NULL（见 Task 15 fix round 1）。
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

    adjusted_nav 在 market.fund_nav 里是【每行一个标量】，而「正确的复权
    净值」其实是 (行, decision_at) 的二元函数：同一行在不同决策时点应有
    不同的值，因为它之后可能又披露了迟到的分红/拆分事件。一个标量列装不下
    这个二元函数，必须选定一个盖章时刻。

    本函数选择【首个 checkpoint 盖章】：每个 (effective_at, version) 只在
    它第一次成为当前版本的那个 checkpoint 被赋值，之后任何 checkpoint 都
    不得覆盖它。

    为什么是「首个」而不是「reign 内最后一个」（fix round 2）：全平台唯一的
    可见性规则是 available_at <= decision_at，所以任何能解析到某行的
    decision_at 都 >= 该行的 available_at；而该行首次成为当前版本的
    checkpoint 就等于它的 available_at。于是「存的值绝不比行本身更新」是
    构造性成立的 —— 列里的值绝不含该行可见时尚不存在的信息。反之若按 reign
    内最后一个 checkpoint 盖章，一个在 reign 中途才披露的迟到事件会回头改写
    该版本已存的值，含未来信息。

    但「首个」也不是对的（fix round 3）：迟到事件披露之后，早期版本行的
    adjusted_nav 偏「旧」（不含该事件）而晚期行含，同一次查询里就出现口径
    不一致 —— 在披露日附近伪造出一个凭空的收益尖峰，对动量/波动率这类因子
    而言与前视一样是污染。两侧都错，说明标量列根本盖不住这个二元函数。
    结论：本列降级为运维物化值，PIT 真值改由读路径按 decision_at 现算
    （见本模块顶部 docstring 与 SqlNavPitRepository.adjusted_nav_series）。
    这里仍保留「首个盖章」，因为在标量列的两种选择中只有它方向安全 ——
    宁可信息偏少，不可信息偏多（C-12：不回填/伪造时间戳，也不让旧行冒充
    知道后来的事）。

    做法：取 decision_at 可见的全部净值/事件行（不折叠版本），把两者的
    available_at 并集排序为一组 checkpoint；在每个 checkpoint 上重新做
    PIT 版本解析，候选 key 取「该 checkpoint 解析出的当前 key 中尚未盖过章
    的那些」，调用 compute_adjusted_nav 成功则只给候选 key 盖章；无论成功
    失败，最后都把该 checkpoint 的全部当前 key 记为已出现过。

    容错粒度是【单个 checkpoint】：某个 checkpoint 抛 AdjustedNavUnavailable
    只跳过它自己，不再牵连整只份额类别。只有「首次成为当前版本的那个
    checkpoint 恰好失败」的行才保持 NULL，下游据此标记 UNAVAILABLE，不填 0、
    不沿用上期（C-6）。C-6 的「全有或全无」语义保留在【写入】这一侧：所有
    checkpoint 都算完之后才统一执行 UPDATE。
    """
    visible_until = resolve_visible_until(decision_at)
    params = {"share_class_id": share_class_id, "visible_until": visible_until}

    nav_rows = session.execute(_ALL_NAV_SQL, params).mappings().all()
    if not nav_rows:
        return 0
    event_rows = session.execute(_ALL_EVENT_SQL, params).mappings().all()

    checkpoints = sorted(
        {row["available_at"] for row in nav_rows}
        | {row["available_at"] for row in event_rows}
    )

    writes: dict[tuple[dt.date, int], Decimal] = {}
    # 已经作为「当前版本」出现过的 key；出现过即失去盖章资格（首个盖章）。
    stamped: set[tuple[dt.date, int]] = set()
    for checkpoint in checkpoints:
        current_navs = _resolve_current(nav_rows, checkpoint)
        if not current_navs:
            continue
        current_keys = {
            (effective_at, row["version"])
            for effective_at, row in current_navs.items()
        }
        candidates = current_keys - stamped
        # 无论本 checkpoint 算得出算不出，它的当前 key 都算「出现过」：
        # 若写成「只在 writes 里不存在时才写」，下面失败跳过的行会在后续
        # checkpoint 被补上一个更新的值，前视偏差又回来了。
        stamped |= current_keys
        if not candidates:
            continue

        current_events = _resolve_current(event_rows, checkpoint)
        try:
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
        except AdjustedNavUnavailable:
            # 逐 checkpoint 容错：只放弃本 checkpoint 的候选行，其余照常。
            continue

        for point in points:
            key = (point.effective_at, current_navs[point.effective_at]["version"])
            if key in candidates:
                writes[key] = point.adjusted_nav

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
