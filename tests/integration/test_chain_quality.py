"""The NAV result carries the weakest quality of its entire calculation chain."""

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

pytestmark = pytest.mark.integration


def _utc(year: int, month: int, day: int, hour: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, tzinfo=dt.UTC)


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(
        fund_code="P-CQ",
        product_name="chain quality",
        grouping_status=GroupingStatus.CONFIRMED.value,
    )
    db_session.add(fund)
    db_session.flush()
    share_class = FundShareClass(
        fund_id=fund.id, share_class_code="A", display_name="chain quality A"
    )
    db_session.add(share_class)
    db_session.flush()
    return share_class


def _add_nav(session, share_class, day: dt.date, value: str, quality: str) -> None:
    if quality == "EXACT":
        available_at = _utc(day.year, day.month, day.day, 12)
        published_at = _utc(day.year, day.month, day.day, 9)
        provider_available_at = available_at
    else:
        available_at = _utc(day.year, day.month, day.day) + dt.timedelta(days=1)
        published_at = None
        provider_available_at = None
    session.add(
        FundNav(
            share_class_id=share_class.id,
            effective_at=day,
            version=1,
            unit_nav=Decimal(value),
            available_at=available_at,
            availability_quality=quality,
            published_at=published_at,
            provider_available_at=provider_available_at,
            ingested_at=_utc(2026, 8, 31),
        )
    )


def _series(db_session, share_class, date_from: dt.date, date_to: dt.date):
    decision_at = dt.date(2026, 8, 31)
    context = DecisionExecutionContext(
        decision_id="D-CQ",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    return PitDataContext(context=context, session=db_session).navs().adjusted_nav_series(
        share_class.id, date_from, date_to
    )


def test_chain_quality_includes_nav_rows_before_requested_window(
    db_session, share_class
):
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "INFERRED")
    _add_nav(db_session, share_class, dt.date(2020, 3, 2), "1.1", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 3, 3), "1.2", "EXACT")
    db_session.flush()

    series = _series(
        db_session, share_class, dt.date(2020, 3, 1), dt.date(2020, 3, 31)
    )

    assert {point.availability_quality for point in series} == {"EXACT"}
    assert {point.chain_availability_quality for point in series} == {"INFERRED"}


def test_chain_quality_includes_distribution_rows(db_session, share_class):
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.1", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.0", "EXACT")
    db_session.add(
        FundDistribution(
            share_class_id=share_class.id,
            effective_at=dt.date(2020, 1, 3),
            version=1,
            dividend_per_unit=Decimal("0.1"),
            split_ratio=Decimal("1"),
            available_at=_utc(2020, 1, 4),
            availability_quality="INFERRED",
            published_at=None,
            provider_available_at=None,
            ingested_at=_utc(2026, 8, 31),
        )
    )
    db_session.flush()

    series = _series(
        db_session, share_class, dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )

    assert [point.chain_availability_quality for point in series] == ["EXACT", "INFERRED"]


def test_empty_window_has_no_chain_quality(db_session, share_class):
    _add_nav(db_session, share_class, dt.date(2019, 1, 2), "1.0", "INFERRED")
    db_session.flush()

    series = _series(
        db_session, share_class, dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )

    assert series == []


def test_rows_after_date_to_do_not_weaken_chain_quality(db_session, share_class):
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "EXACT")
    _add_nav(db_session, share_class, dt.date(2021, 6, 1), "1.5", "INFERRED")
    db_session.flush()

    series = _series(
        db_session, share_class, dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )

    assert series[-1].chain_availability_quality == "EXACT"
