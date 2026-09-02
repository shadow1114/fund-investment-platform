import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundDistribution

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-DIST", product_name="分红测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="分红测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _event(sc, day, dividend="0", ratio="1"):
    return FundDistribution(
        share_class_id=sc.id, effective_at=day, version=1,
        dividend_per_unit=Decimal(dividend), split_ratio=Decimal(ratio),
        available_at=dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )


def test_same_day_dividend_and_split_fit_in_one_row(db_session, share_class):
    """同日除息 + 拆分是真实场景，必须能在一行内表达先后语义。"""
    db_session.add(_event(share_class, dt.date(2021, 3, 15), "0.2", "2"))
    db_session.flush()
    row = db_session.query(FundDistribution).one()
    assert row.dividend_per_unit == Decimal("0.2")
    assert row.split_ratio == Decimal(2)


def test_negative_dividend_is_rejected_by_the_database(db_session, share_class):
    db_session.add(_event(share_class, dt.date(2021, 3, 15), "-0.1"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_zero_split_ratio_is_rejected_by_the_database(db_session, share_class):
    db_session.add(_event(share_class, dt.date(2021, 3, 15), "0", "0"))
    with pytest.raises(IntegrityError):
        db_session.flush()
