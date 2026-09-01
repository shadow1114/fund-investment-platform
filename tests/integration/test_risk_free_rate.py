import datetime as dt
from decimal import Decimal

import pytest

from fip.services.data_service.models.market import RiskFreeRate

pytestmark = pytest.mark.integration


def _rate(tenor, day, value, version=1):
    return RiskFreeRate(
        curve_code="CN_TREASURY", currency="CNY", tenor=tenor,
        effective_at=day, version=version, rate=Decimal(value),
        available_at=dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC)
        + dt.timedelta(days=1),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, tzinfo=dt.UTC),
    )


def test_multiple_tenors_coexist_on_one_date(db_session):
    """曲线不是单值 —— 同一天必须能存多个期限。"""
    day = dt.date(2024, 1, 2)
    db_session.add_all([_rate("3M", day, "0.021"), _rate("1Y", day, "0.023"),
                        _rate("10Y", day, "0.026")])
    db_session.flush()
    assert db_session.query(RiskFreeRate).filter_by(effective_at=day).count() == 3


def test_rate_is_stored_as_decimal_fraction(db_session):
    db_session.add(_rate("1Y", dt.date(2024, 1, 2), "0.023"))
    db_session.flush()
    row = db_session.query(RiskFreeRate).one()
    assert row.rate == Decimal("0.02300000")


def test_revision_creates_a_new_version(db_session):
    day = dt.date(2024, 1, 2)
    db_session.add(_rate("1Y", day, "0.023", version=1))
    db_session.flush()
    db_session.add(_rate("1Y", day, "0.0235", version=2))
    db_session.flush()
    assert db_session.query(RiskFreeRate).filter_by(tenor="1Y").count() == 2
