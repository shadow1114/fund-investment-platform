import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundNav

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-NAV", product_name="测试基金",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="测试基金A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _nav(sc, day, value, version=1, available_at=None):
    return FundNav(
        share_class_id=sc.id,
        effective_at=day,
        version=version,
        unit_nav=Decimal(value),
        available_at=available_at
        or dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC) + dt.timedelta(days=1),
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )


def test_rows_land_in_the_year_partition(db_session, share_class):
    db_session.add(_nav(share_class, dt.date(2020, 3, 5), "1.2345"))
    db_session.flush()
    count = db_session.execute(
        text("SELECT count(*) FROM market.fund_nav_2020")
    ).scalar_one()
    assert count == 1


def test_revision_creates_a_new_version_without_overwriting(db_session, share_class):
    """修订产生新版本，旧版本保留（上游原则二）。"""
    day = dt.date(2020, 3, 5)
    db_session.add(_nav(share_class, day, "1.2345", version=1))
    db_session.flush()
    db_session.add(_nav(share_class, day, "1.2000", version=2))
    db_session.flush()
    versions = db_session.query(FundNav).filter_by(
        share_class_id=share_class.id, effective_at=day).count()
    assert versions == 2


def test_duplicate_version_is_rejected(db_session, share_class):
    day = dt.date(2020, 3, 5)
    db_session.add(_nav(share_class, day, "1.2345", version=1))
    db_session.flush()
    db_session.add(_nav(share_class, day, "1.2000", version=1))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_non_positive_nav_is_rejected_by_the_database(db_session, share_class):
    db_session.add(_nav(share_class, dt.date(2020, 3, 5), "0"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_adjusted_nav_may_be_null(db_session, share_class):
    """算不出复权值时留空，绝不填 0（C-6）。"""
    row = _nav(share_class, dt.date(2020, 3, 5), "1.2345")
    db_session.add(row)
    db_session.flush()
    assert row.adjusted_nav is None
