import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import NavPoint
from fip.services.data_service.normalization.adjusted_nav import (
    DistributionEvent,
    NavObservation,
    compute_adjusted_nav,
)

# 【只设上界，不设下界】——这个不对称是刻意的：
# · 无下界：复权是一条前向累乘链路，起点被截断会让整段序列的绝对水平错掉
#   （截断点之前的全部分红/拆分都会凭空消失）。因此必须从成立日算起。
# · 有上界：date_to 之后的行对区间内的值【毫无贡献】（adj_t 只依赖
#   effective_at ≤ t 的事件），却会扩大抛 AdjustedNavUnavailable 的面 ——
#   一个落在请求区间之后的数据缺口会把一个完全可算的历史窗口整段废掉。
_NAV_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, unit_nav, version, availability_quality
    FROM market.fund_nav
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND effective_at <= :date_to
    ORDER BY effective_at, version DESC
""")

# 事件表用同一条版本解析规则：对每个 effective_at，在 available_at ≤
# decision_at 的行中取 version 最大者。
_EVENT_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, dividend_per_unit, split_ratio
    FROM market.fund_distribution
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND effective_at <= :date_to
    ORDER BY effective_at, version DESC
""")


class SqlNavPitRepository:
    """PIT NAV 访问的 SQL 实现。

    decision_at 在【构造期】注入，方法签名中不出现时点参数 —— 调用方
    无法省略它，也无法绕过它取到未来数据（PIT-A2 / PIT-A3）。

    版本解析：对每个 effective_at，在 available_at ≤ decision_at 的行中
    取 version 最大者。净值表与事件表都适用这一条规则。这实现了上游原则二
    的「取 available_at ≤ decision_at 中的最新版本」。
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
        """按 decision_at 【现算】复权净值序列。

        复权净值不是每行一个标量，而是 (行, decision_at) 的二元函数：同一
        净值行在不同决策时点应有不同的复权值，因为它之后可能又披露了迟到的
        分红/拆分事件。market.fund_nav.adjusted_nav 这个标量列装不下这个
        二元函数，因此它只是运维物化值，【不是】PIT 真值来源；真值在这里
        按 decision_at 现算。

        **这是构造性的 PIT 保证**：函数只可能看到 available_at ≤ decision_at
        的行，前视不可能发生；整条序列算于同一时点，口径不一致也不可能发生。

        计算不出复权净值时 compute_adjusted_nav 抛 AdjustedNavUnavailable，
        本方法【不】捕获它、不回退成读旧列、不填 0、不沿用上期（C-6）。
        """
        # decision_at 是业务日期；可见性判定取该日终了时刻。
        visible_until = dt.datetime.combine(
            self._decision_at, dt.time.max, tzinfo=dt.UTC
        )
        params = {
            "share_class_id": share_class_id,
            "visible_until": visible_until,
            "date_to": date_to,
        }
        nav_rows = self._session.execute(_NAV_SQL, params).mappings().all()
        if not nav_rows:
            return []
        event_rows = self._session.execute(_EVENT_SQL, params).mappings().all()

        points = compute_adjusted_nav(
            [NavObservation(r["effective_at"], r["unit_nav"]) for r in nav_rows],
            [
                DistributionEvent(
                    r["effective_at"], r["dividend_per_unit"], r["split_ratio"]
                )
                for r in event_rows
            ],
        )
        adjusted = {p.effective_at: p.adjusted_nav for p in points}
        # unit_nav / version / availability_quality 仍取自净值行本身；
        # 只有 adjusted_nav 来自现算结果。切片放在最后一步。
        return [
            NavPoint(
                effective_at=row["effective_at"],
                adjusted_nav=adjusted[row["effective_at"]],
                unit_nav=row["unit_nav"],
                version=row["version"],
                availability_quality=row["availability_quality"],
            )
            for row in nav_rows
            if date_from <= row["effective_at"] <= date_to
        ]
