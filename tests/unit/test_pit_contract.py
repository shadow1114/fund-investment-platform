"""PIT 数据契约的形状本身（Plan-1 交接项二.1 / 二.2）。

这些断言不需要数据库：它们锁的是 dataclass 与 Protocol 的**类型契约**，
而类型契约一旦松掉，下游会长出永远不会被执行的 None 分支，或把逐行 quality
误当成链路 quality 使用。
"""

import datetime as dt
import typing
from decimal import Decimal

import pytest

from fip.platform.decision_data.pit import NavPitRepository, NavPoint, NavSeries
from fip.platform.source.availability import AvailabilityQuality, weakest_quality


def test_adjusted_nav_is_not_optional():
    """现算路径要么全有值、要么抛 AdjustedNavUnavailable，绝无 None。

    留着 `Decimal | None` 的后果不是「多一点保险」：它让下游每个消费方都
    必须写一个永远不会被执行的 `is None` 分支，而那个分支里最自然的写法
    恰恰是填 0 或沿用上期 —— 正是 C-6 / G-3 禁止的两件事。
    """
    hints = typing.get_type_hints(NavPoint)
    assert hints["adjusted_nav"] is Decimal


def test_nav_point_keeps_its_own_row_quality():
    """逐行 quality 保留：它是那一行自己的事实，不是链路的结论。"""
    hints = typing.get_type_hints(NavPoint)
    assert hints["availability_quality"] is str


def test_repository_returns_a_series_not_a_bare_list():
    """链路 quality 无处安放是 Plan-1 的结构性缺口，返回类型必须能装下它。"""
    hints = typing.get_type_hints(NavPitRepository.adjusted_nav_series)
    assert hints["return"] is NavSeries


def _point(day: int, quality: str) -> NavPoint:
    return NavPoint(
        effective_at=dt.date(2020, 1, day),
        adjusted_nav=Decimal("1.00000000"),
        unit_nav=Decimal("1.00000000"),
        version=1,
        availability_quality=quality,
    )


def test_empty_series_has_no_chain_quality():
    """没有任何行就没有链路 —— 不得凭空造一个 quality 值出来（G-3）。"""
    series = NavSeries(points=(), chain_quality=None)
    assert series.chain_quality is None


def test_non_empty_series_must_carry_a_chain_quality():
    """反向不变式：有点却没有链路结论，是把 quality 悄悄丢掉。"""
    with pytest.raises(ValueError, match="chain_quality"):
        NavSeries(points=(_point(2, "EXACT"),), chain_quality=None)


def test_empty_series_must_not_carry_a_chain_quality():
    with pytest.raises(ValueError, match="chain_quality"):
        NavSeries(points=(), chain_quality="EXACT")


@pytest.mark.parametrize(
    ("qualities", "expected"),
    [
        (["EXACT"], AvailabilityQuality.EXACT),
        (["EXACT", "EXACT"], AvailabilityQuality.EXACT),
        (["EXACT", "DERIVED"], AvailabilityQuality.DERIVED),
        (["DERIVED", "EXACT"], AvailabilityQuality.DERIVED),
        (["EXACT", "DERIVED", "INFERRED"], AvailabilityQuality.INFERRED),
        (["INFERRED", "EXACT"], AvailabilityQuality.INFERRED),
        (["DERIVED", "DERIVED"], AvailabilityQuality.DERIVED),
        ([AvailabilityQuality.EXACT, "INFERRED"], AvailabilityQuality.INFERRED),
    ],
)
def test_weakest_quality_is_min_over_chain(qualities, expected):
    """EXACT > DERIVED > INFERRED，取最弱者（min-over-chain）。

    方向必须是「取最弱」而不是「取多数」或「取最后一行」：复权值是整条
    累乘链路的函数，链路上任何一行不可靠，产出的值就不可靠。
    """
    assert weakest_quality(qualities) is expected


def test_weakest_quality_rejects_an_empty_chain():
    """空链路没有结论 —— 返回一个默认值就是凭空发明可靠性。"""
    with pytest.raises(ValueError):
        weakest_quality([])


def test_weakest_quality_rejects_unknown_labels():
    with pytest.raises(ValueError):
        weakest_quality(["VERIFIED"])
