import datetime as dt
from decimal import Decimal

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundDistribution, FundNav
from fip.services.data_service.normalization.backfill import backfill_adjusted_nav

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-PIT", product_name="PIT 测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="PIT 测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _utc(year, month, day):
    return dt.datetime(year, month, day, tzinfo=dt.UTC)


def _add_nav(session, sc, day, value, version=1, available_at=None):
    session.add(FundNav(
        share_class_id=sc.id, effective_at=day, version=version,
        unit_nav=Decimal(value),
        available_at=available_at or _utc(day.year, day.month, day.day)
        + dt.timedelta(days=1),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))


def _ctx(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-PIT", decision_at=decision_at, data_as_of=decision_at,
        strategy_version="sv-1", policy_version="pv-1", code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def _series(db_session, sc, decision_at, date_from, date_to):
    ctx = PitDataContext(context=_ctx(decision_at), session=db_session)
    return ctx.navs().adjusted_nav_series(sc.id, date_from, date_to)


def test_backfill_computes_adjusted_nav(db_session, share_class):
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.1")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.0")
    db_session.add(FundDistribution(
        share_class_id=share_class.id, effective_at=dt.date(2020, 1, 3), version=1,
        dividend_per_unit=Decimal("0.1"), split_ratio=Decimal(1),
        available_at=_utc(2020, 1, 4), availability_quality="INFERRED",
        published_at=None, provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))
    db_session.flush()

    updated = backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    assert updated == 2

    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.adjusted_nav for p in points] == [Decimal("1.1"), Decimal("1.1")]


def test_data_not_yet_available_is_invisible(db_session, share_class):
    """PIT 的核心断言：决策时点看不见的数据不得参与。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0",
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.5",
             available_at=_utc(2020, 1, 10))  # 迟到的数据
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    early = _series(db_session, share_class, dt.date(2020, 1, 5),
                    dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in early] == [dt.date(2020, 1, 2)]

    later = _series(db_session, share_class, dt.date(2020, 1, 15),
                    dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in later] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_revision_is_resolved_by_decision_time(db_session, share_class):
    """净值修订：决策时点之前看到的是旧版本，之后才是新版本。"""
    day = dt.date(2020, 1, 2)
    _add_nav(db_session, share_class, day, "1.0", version=1,
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, day, "1.2", version=2,
             available_at=_utc(2020, 2, 1))
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    before = _series(db_session, share_class, dt.date(2020, 1, 10), day, day)
    assert before[0].unit_nav == Decimal("1.0")
    assert before[0].version == 1
    assert before[0].adjusted_nav == Decimal("1.0")

    after = _series(db_session, share_class, dt.date(2020, 3, 1), day, day)
    assert after[0].unit_nav == Decimal("1.2")
    assert after[0].version == 2
    assert after[0].adjusted_nav == Decimal("1.2")


def test_superseded_version_keeps_its_own_adjusted_nav(db_session, share_class):
    """被取代的旧版本不能永远停留在 adjusted_nav = NULL（fix round 1）。

    两个版本都在【同一次】批量回填运行【之前】就已存在——这正是 Task 19
    历史全量回填会遇到的形状：回填只跑一次，但 fund_nav 里已经有多版本。
    """
    day = dt.date(2020, 1, 2)
    _add_nav(db_session, share_class, day, "1.0", version=1,
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, day, "1.2", version=2,
             available_at=_utc(2020, 2, 1))
    db_session.flush()

    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    before = _series(db_session, share_class, dt.date(2020, 1, 10), day, day)
    assert before[0].version == 1
    assert before[0].adjusted_nav == Decimal("1.0")

    after = _series(db_session, share_class, dt.date(2020, 3, 1), day, day)
    assert after[0].version == 2
    assert after[0].adjusted_nav == Decimal("1.2")


def test_series_is_sorted_and_bounded_by_date_range(db_session, share_class):
    for day, value in [(dt.date(2020, 1, 3), "1.1"),
                       (dt.date(2020, 1, 2), "1.0"),
                       (dt.date(2021, 1, 4), "1.3")]:
        _add_nav(db_session, share_class, day, value)
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in points] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_availability_quality_is_returned(db_session, share_class):
    """调用方必须能判断这段序列的 PIT 可信度。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0")
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert points[0].availability_quality == "INFERRED"


def test_empty_range_returns_empty_list(db_session, share_class):
    assert _series(db_session, share_class, dt.date(2026, 8, 31),
                   dt.date(2020, 1, 1), dt.date(2020, 12, 31)) == []
