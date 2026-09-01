import datetime as dt

import pytest

from fip.platform.source.availability import (
    AvailabilityQuality,
    declared_lag_availability,
    resolve_availability,
)

PUB = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.UTC)
PROV = dt.datetime(2026, 1, 2, 10, 3, tzinfo=dt.UTC)
ING = dt.datetime(2026, 1, 2, 18, 0, tzinfo=dt.UTC)


def test_provider_push_time_wins_and_is_exact():
    assert resolve_availability(PUB, PROV, ING) == (PROV, AvailabilityQuality.EXACT)


def test_published_at_is_used_when_provider_time_missing():
    """公告发布 ≠ 投资系统已知，因此只能是 DERIVED。"""
    assert resolve_availability(PUB, None, ING) == (PUB, AvailabilityQuality.DERIVED)


def test_falls_back_to_ingested_at_as_inferred():
    """AKShare 回补数据的常态。"""
    assert resolve_availability(None, None, ING) == (ING, AvailabilityQuality.INFERRED)


def test_exact_is_never_returned_without_provider_time():
    """C-12：绝不允许用 ingested_at 回填 provider_available_at 后标成 EXACT。"""
    for pub in (PUB, None):
        _, quality = resolve_availability(pub, None, ING)
        assert quality is not AvailabilityQuality.EXACT


def test_declared_lag_produces_inferred_quality():
    """净值历史回补：available_at = effective_at + 声明的披露时滞。"""
    at, quality = declared_lag_availability(dt.date(2020, 1, 2), dt.timedelta(days=1))
    assert at == dt.datetime(2020, 1, 3, 0, 0, tzinfo=dt.UTC)
    assert quality is AvailabilityQuality.INFERRED


def test_declared_lag_rejects_negative_lag():
    with pytest.raises(ValueError, match="lag"):
        declared_lag_availability(dt.date(2020, 1, 2), dt.timedelta(days=-1))
