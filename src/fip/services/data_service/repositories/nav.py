import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.db.types import NavNumeric
from fip.platform.decision_data.pit import NavPoint
from fip.platform.source.availability import weakest_quality
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
           effective_at, dividend_per_unit, split_ratio, availability_quality
    FROM market.fund_distribution
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND effective_at <= :date_to
    ORDER BY effective_at, version DESC
""")


# 出口量化的标度直接取自 NavNumeric（= NUMERIC(18, 8)），不写死 8 ——
# 标度若哪天改了，读路径与物化列必须一起改，不能靠人记得同步两处。
_NAV_SCALE = int(NavNumeric.scale or 0)
_NAV_QUANTUM = Decimal(1).scaleb(-_NAV_SCALE)


def _quantize_nav(value: Decimal) -> Decimal:
    """把现算的复权净值量化到 NavNumeric 的标度。

    为什么必须在【出口】量化（fix round 4）：

    compute_adjusted_nav 内部用 60 位有效数字 + 60 位保护位滚动累乘，产出的
    是 60 位有效数字的值；而 market.fund_nav.adjusted_nav 是 NUMERIC(18, 8)，
    由 PostgreSQL 舍入到 8 位。两条路径于是有两个不同精度的口径：
      · 实测（fip_dev，share_class 4，5997 行 / 25 次分红）：5893 行不相等，
        max|diff| = 5.0e-9，恰是 8 位小数的半个 ulp；
      · NavPoint.adjusted_nav 没有精度契约，60 位里有 52 位是计算保护位的
        噪声，会直接流进 Plan-2 的因子计算；
      · spec §9.3 的可复现性容差是 1e-10，「回读列 vs 现算」的相对误差约
        5e-9，超标一个半数量级。

    舍入方式取 ROUND_HALF_UP（半个 ulp 向远离零的方向），与 PostgreSQL 的
    numeric 舍入一致 —— 若这里用 Python Decimal 默认的 ROUND_HALF_EVEN，
    恰好落在半个 ulp 上的值会与列里的值差 1 个 ulp，一致性对照又会分叉。

    【只在出口量化】：compute_adjusted_nav 这个纯函数不动，累乘链路仍然全程
    高精度 —— 先降精度再累乘会让舍入误差随链路长度累积，那是另一个 bug。
    """
    return value.quantize(_NAV_QUANTUM, rounding=ROUND_HALF_UP)


class SqlNavPitRepository:
    """PIT NAV 访问的 SQL 实现。

    可见性上界在【构造期】注入，方法签名中不出现时点参数 —— 调用方
    无法省略它，也无法绕过它取到未来数据（PIT-A2 / PIT-A3）。

    版本解析：对每个 effective_at，在 available_at ≤ decision_at 的行中
    取 version 最大者。净值表与事件表都适用这一条规则。这实现了上游原则二
    的「取 available_at ≤ decision_at 中的最新版本」。
    """

    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        """visible_until 由 PitDataContext.visible_until 注入。

        本类【不再】自己把 decision_at 翻译成时间戳上界：那条规则的唯一
        归属是 fip.platform.decision_data.pit.resolve_visible_until（H-1）。
        构造期注入上界与注入 decision_at 在 PIT-A2 上是等价的 —— 时点仍然
        不出现在任何方法签名里，调用方仍然无法省略它、无法绕过它取未来数据。
        """
        self._session = session
        self._visible_until = visible_until

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

        精度契约：返回的 adjusted_nav 一律量化到 NavNumeric 的标度
        （NUMERIC(18, 8)），与物化列同一口径 —— 见 _quantize_nav。
        """
        params = {
            "share_class_id": share_class_id,
            "visible_until": self._visible_until,
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
        adjusted = {p.effective_at: _quantize_nav(p.adjusted_nav) for p in points}
        # unit_nav / version / availability_quality 仍取自净值行本身；
        # 只有 adjusted_nav 来自现算结果。切片放在最后一步。
        qualities_by_date: dict[dt.date, list[str]] = {}
        for row in (*nav_rows, *event_rows):
            qualities_by_date.setdefault(row["effective_at"], []).append(
                row["availability_quality"]
            )
        chain_quality_by_date: dict[dt.date, str] = {}
        weakest_so_far: str | None = None
        for effective_at in sorted(qualities_by_date):
            qualities = qualities_by_date[effective_at]
            if weakest_so_far is not None:
                qualities = [weakest_so_far, *qualities]
            weakest_so_far = weakest_quality(qualities).value
            chain_quality_by_date[effective_at] = weakest_so_far

        return [
            NavPoint(
                effective_at=row["effective_at"],
                adjusted_nav=adjusted[row["effective_at"]],
                unit_nav=row["unit_nav"],
                version=row["version"],
                availability_quality=row["availability_quality"],
                chain_availability_quality=chain_quality_by_date[row["effective_at"]],
            )
            for row in nav_rows
            if date_from <= row["effective_at"] <= date_to
        ]
