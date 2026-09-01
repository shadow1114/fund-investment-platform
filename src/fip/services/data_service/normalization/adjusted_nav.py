import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext

# 累乘链路较长（可达数千期），需要高于默认的 28 位精度。
_PRECISION = 60

# 递推逐期滚动 shares，每期一次乘法即引入一次舍入；数千期累积后，若只用
# _PRECISION 位做内部计算，累积舍入误差会在末尾几位偏离「一次性算出的
# 正确舍入结果」（例如 Decimal("1.01") ** 999）。因此内部滚动用更高的
# 「计算精度」，只在对外产出每个点时才舍入到 _PRECISION 位——这样长链条
# 也能精确到 _PRECISION 位有效数字，不因链路长度而漂移。
#
# 60 位保护位是留出的宽裕余量，不是从误差增长公式推导出的紧界——最坏情况
# 下 n 次乘法在计算精度上累积约 O(n) 个末位单位的误差，实测 999 期链路只
# 需 10 位保护位即可让结果与 Decimal("1.01") ** 999 完全一致；60 位是为了
# 覆盖比该测试更长的真实链路（可达数千期）留出充足余量，而非一个已证明的
# 下界。
_GUARD_DIGITS = 60
_COMPUTE_PRECISION = _PRECISION + _GUARD_DIGITS

ONE = Decimal(1)


class AdjustedNavUnavailable(RuntimeError):
    """复权净值无法计算。

    调用方必须把对应记录标记为 UNAVAILABLE，【不得】填 0 或沿用上期（C-6）。
    """


@dataclass(frozen=True, slots=True)
class NavObservation:
    effective_at: dt.date
    unit_nav: Decimal


@dataclass(frozen=True, slots=True)
class DistributionEvent:
    effective_at: dt.date
    dividend_per_unit: Decimal
    split_ratio: Decimal


@dataclass(frozen=True, slots=True)
class AdjustedNavPoint:
    effective_at: dt.date
    unit_nav: Decimal
    cumulative_shares: Decimal
    adjusted_nav: Decimal


def compute_adjusted_nav(
    navs: Sequence[NavObservation],
    events: Sequence[DistributionEvent],
) -> list[AdjustedNavPoint]:
    """由单位净值与除息/拆分事件计算复权净值（分红再投资总收益序列）。

    口径（属 Metric Version，登记于 config/strategy/metric/v1.yaml）：
      · 分红再投资价格 = 除息日当日单位净值（EX_DATE_NAV）
      · 同日事件顺序   = 先除息后拆分（DIVIDEND_THEN_SPLIT）

    递推（持有 1 份起始份额）：
        pre      = unit_nav_t × split_ratio_t     # 除息后、拆分前的净值
        shares_t = shares_{t-1} × (1 + dividend_t / pre) × split_ratio_t
        adj_t    = unit_nav_t × shares_t

    无事件时退化为 shares_t = shares_{t-1}，adj_t = unit_nav_t。

    为什么不能直接用累计净值代替：累计净值不处理拆分，也不做分红再投资的
    乘法复利 —— 它是「累计分配」而非「总收益」。
    """
    if not navs:
        return []

    ordered_navs = sorted(navs, key=lambda n: n.effective_at)
    seen_navs: set[dt.date] = set()
    for observation in ordered_navs:
        if observation.effective_at in seen_navs:
            raise ValueError(f"净值日期重复：{observation.effective_at}")
        seen_navs.add(observation.effective_at)
        if observation.unit_nav <= 0:
            raise AdjustedNavUnavailable(
                f"{observation.effective_at} 的单位净值为 {observation.unit_nav}，"
                "必须为正"
            )

    by_date: dict[dt.date, DistributionEvent] = {}
    for event in events:
        if event.dividend_per_unit < 0:
            raise ValueError(f"{event.effective_at} 的每份分红为负：{event.dividend_per_unit}")
        if event.split_ratio <= 0:
            raise ValueError(f"{event.effective_at} 的拆分比例非正：{event.split_ratio}")
        if event.effective_at in by_date:
            raise ValueError(f"事件日期重复：{event.effective_at}")
        by_date[event.effective_at] = event

    missing = sorted(set(by_date) - seen_navs)
    if missing:
        raise AdjustedNavUnavailable(
            f"事件日 {missing} 缺少净值观测，无法确定再投资价格"
        )

    points: list[AdjustedNavPoint] = []
    with localcontext() as ctx:
        ctx.prec = _COMPUTE_PRECISION
        shares = ONE
        for observation in ordered_navs:
            matched_event = by_date.get(observation.effective_at)
            if matched_event is not None:
                # pre_split_nav 恒为正：unit_nav > 0 与 split_ratio > 0 均已在
                # 上面两个校验循环中强制保证，无需再防御性判断。
                pre_split_nav = observation.unit_nav * matched_event.split_ratio
                reinvest = ONE + matched_event.dividend_per_unit / pre_split_nav
                # shares 以计算精度滚动，不用对外精度舍入，避免逐期舍入误差累积。
                shares = shares * reinvest * matched_event.split_ratio
            with localcontext() as out_ctx:
                out_ctx.prec = _PRECISION
                reported_shares = +shares
                adjusted_nav = observation.unit_nav * reported_shares
            points.append(
                AdjustedNavPoint(
                    effective_at=observation.effective_at,
                    unit_nav=observation.unit_nav,
                    cumulative_shares=reported_shares,
                    adjusted_nav=adjusted_nav,
                )
            )
    return points
