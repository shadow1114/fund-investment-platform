import datetime as dt
from decimal import Decimal, localcontext

import pytest

from fip.services.data_service.normalization.adjusted_nav import (
    AdjustedNavUnavailable,
    DistributionEvent,
    NavObservation,
    compute_adjusted_nav,
)


def D(value: str) -> Decimal:
    return Decimal(value)


def nav(day: int, value: str) -> NavObservation:
    return NavObservation(dt.date(2020, 1, day), D(value))


def dividend(day: int, amount: str) -> DistributionEvent:
    return DistributionEvent(dt.date(2020, 1, day), D(amount), D("1"))


def split(day: int, ratio: str) -> DistributionEvent:
    return DistributionEvent(dt.date(2020, 1, day), D("0"), D(ratio))


def both(day: int, amount: str, ratio: str) -> DistributionEvent:
    return DistributionEvent(dt.date(2020, 1, day), D(amount), D(ratio))


def _returns(points):
    return [
        points[i].adjusted_nav / points[i - 1].adjusted_nav - 1
        for i in range(1, len(points))
    ]


def test_without_events_adjusted_equals_unit():
    points = compute_adjusted_nav([nav(2, "1.0"), nav(3, "1.1")], [])
    assert [p.adjusted_nav for p in points] == [D("1.0"), D("1.1")]


def test_pure_dividend_produces_zero_return():
    """除息不是亏损。复权后跨除息日的收益必须为 0。"""
    points = compute_adjusted_nav(
        [nav(2, "1.1"), nav(3, "1.0")],
        [dividend(3, "0.1")],
    )
    assert points[1].cumulative_shares == D("1.1")
    assert points[1].adjusted_nav == D("1.1")
    assert _returns(points) == [D("0")]


def test_pure_split_produces_zero_return():
    """拆分不是亏损。"""
    points = compute_adjusted_nav(
        [nav(2, "2.0"), nav(3, "1.0")],
        [split(3, "2")],
    )
    assert points[1].cumulative_shares == D("2")
    assert points[1].adjusted_nav == D("2.0")
    assert _returns(points) == [D("0")]


def test_same_day_dividend_and_split_produces_zero_return():
    """同日先除息后拆分。

    nav 2.2 → 除息 0.2 后为 2.0 → 拆分 2:1 后为 1.0。
    份额：1 × (1 + 0.2/2.0) × 2 = 2.2；复权净值 1.0 × 2.2 = 2.2，收益为 0。
    """
    points = compute_adjusted_nav(
        [nav(2, "2.2"), nav(3, "1.0")],
        [both(3, "0.2", "2")],
    )
    assert points[1].cumulative_shares == D("2.2")
    assert points[1].adjusted_nav == D("2.2")
    assert _returns(points) == [D("0")]


def test_events_accumulate_multiplicatively():
    """1.0 →（分红 0.1）→ 涨到 2.0 →（拆分 2:1）：总收益 120%。"""
    points = compute_adjusted_nav(
        [nav(2, "1.0"), nav(3, "1.0"), nav(4, "2.0"), nav(5, "1.0")],
        [dividend(3, "0.1"), split(5, "2")],
    )
    assert [p.adjusted_nav for p in points] == [D("1.0"), D("1.1"), D("2.2"), D("2.2")]
    assert points[-1].adjusted_nav / points[0].adjusted_nav - 1 == D("1.2")


def test_result_values_are_decimal():
    """C：金融数值禁止浮点。float 在累乘中会引入不可控误差。"""
    points = compute_adjusted_nav([nav(2, "1.0")], [])
    assert isinstance(points[0].adjusted_nav, Decimal)
    assert isinstance(points[0].cumulative_shares, Decimal)


def test_unordered_input_is_sorted():
    points = compute_adjusted_nav([nav(3, "1.1"), nav(2, "1.0")], [])
    assert [p.effective_at.day for p in points] == [2, 3]


def test_empty_input_returns_empty():
    assert compute_adjusted_nav([], []) == []


def test_event_without_matching_nav_is_an_error():
    """事件日没有净值观测就无法计算再投资价格 —— 显式失败，不跳过。"""
    with pytest.raises(AdjustedNavUnavailable, match="缺少净值"):
        compute_adjusted_nav([nav(2, "1.0")], [dividend(3, "0.1")])


def test_non_positive_nav_is_an_error():
    with pytest.raises(AdjustedNavUnavailable, match="净值"):
        compute_adjusted_nav([NavObservation(dt.date(2020, 1, 2), D("0"))], [])


def test_negative_dividend_is_rejected():
    with pytest.raises(ValueError, match="分红"):
        compute_adjusted_nav([nav(2, "1.0")], [dividend(2, "-0.1")])


def test_non_positive_split_ratio_is_rejected():
    with pytest.raises(ValueError, match="拆分"):
        compute_adjusted_nav([nav(2, "1.0")], [split(2, "0")])


def test_duplicate_nav_dates_are_rejected():
    with pytest.raises(ValueError, match="重复"):
        compute_adjusted_nav([nav(2, "1.0"), nav(2, "1.1")], [])


def test_duplicate_event_dates_are_rejected():
    with pytest.raises(ValueError, match="重复"):
        compute_adjusted_nav([nav(2, "1.0")], [dividend(2, "0.1"), split(2, "2")])


def test_long_series_stays_exact():
    """1000 期连续分红，验证 Decimal 精度不退化为浮点漂移。

    ⚠️ 期望值必须在【与实现相同的精度上下文】内计算。compute_adjusted_nav
    内部用 localcontext(prec=60)，而模块外默认是 prec=28 —— 若在默认上下文
    里算 D("1.01") ** 999，两者必然不等，这条测试会恒失败。
    """
    navs = [NavObservation(dt.date(2020, 1, 1) + dt.timedelta(days=i), D("1.0"))
            for i in range(1000)]
    events = [DistributionEvent(navs[i].effective_at, D("0.01"), D("1"))
              for i in range(1, 1000)]
    points = compute_adjusted_nav(navs, events)
    with localcontext() as ctx:
        ctx.prec = 60
        expected = D("1.01") ** 999
    assert points[-1].cumulative_shares == expected
