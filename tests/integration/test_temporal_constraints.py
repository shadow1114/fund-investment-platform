import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

INSERT = text("""
    INSERT INTO governance.mixin_probe
        (effective_at, available_at, availability_quality,
         version, published_at, provider_available_at, ingested_at)
    VALUES
        (:effective_at, :available_at, :quality,
         :version, :published_at, :provider_available_at, :ingested_at)
""")

D = dt.date(2026, 1, 2)
T0 = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.UTC)
T1 = dt.datetime(2026, 1, 2, 18, 0, tzinfo=dt.UTC)
T2 = dt.datetime(2026, 1, 3, 9, 0, tzinfo=dt.UTC)


def _row(**overrides):
    base = dict(
        effective_at=D, available_at=T1, quality="EXACT", version=1,
        published_at=T0, provider_available_at=T1, ingested_at=T2,
    )
    base.update(overrides)
    return base


def test_exact_requires_provider_available_at(db_session):
    """EXACT 必须有 provider_available_at —— 否则是伪装成精确值的兜底值。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(quality="EXACT", provider_available_at=None))
        db_session.flush()


def test_inferred_forbids_any_source(db_session):
    """INFERRED 意味着两个来源都拿不到；有来源却标 INFERRED 是映射错误。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(quality="INFERRED", published_at=T0,
                                        provider_available_at=None))
        db_session.flush()


def test_derived_is_accepted_with_published_at_only(db_session):
    db_session.execute(INSERT, _row(quality="DERIVED", published_at=T0,
                                    provider_available_at=None))
    db_session.flush()


def test_inferred_is_accepted_when_both_sources_null(db_session):
    """AKShare 回补数据的常态：两个来源都拿不到。"""
    db_session.execute(INSERT, _row(quality="INFERRED", published_at=None,
                                    provider_available_at=None))
    db_session.flush()


def test_published_at_cannot_precede_effective_at(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(
            published_at=dt.datetime(2025, 12, 31, 9, 0, tzinfo=dt.UTC)))
        db_session.flush()


def test_provider_available_at_cannot_precede_published_at(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(published_at=T1, provider_available_at=T0))
        db_session.flush()


def test_ingested_at_cannot_precede_provider_available_at(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(
            provider_available_at=T2,
            ingested_at=dt.datetime(2026, 1, 2, 11, 0, tzinfo=dt.UTC)))
        db_session.flush()


def test_announcement_on_effective_date_is_accepted(db_session):
    """effective_at 是 DATE，比较时隐式转当日 00:00，公告当天不应被拒。"""
    db_session.execute(INSERT, _row(
        published_at=dt.datetime(2026, 1, 2, 0, 30, tzinfo=dt.UTC),
        provider_available_at=dt.datetime(2026, 1, 2, 0, 40, tzinfo=dt.UTC),
        ingested_at=dt.datetime(2026, 1, 2, 1, 0, tzinfo=dt.UTC)))
    db_session.flush()


def test_exact_provider_time_cannot_precede_effective_at(db_session):
    """真空满足漏洞 1：EXACT 下 published_at 为 NULL 时 clause 2 恒真，
    provider_available_at（EXACT 分支 available_at 的来源）本应仍不能早于
    effective_at —— 否则等于平台在事实生效前就拿到了它。"""
    early = dt.datetime(2025, 12, 31, 9, 0, tzinfo=dt.UTC)
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(
            quality="EXACT", available_at=early, published_at=None,
            provider_available_at=early, ingested_at=T2))
        db_session.flush()


def test_inferred_ingested_at_cannot_precede_effective_at(db_session):
    """真空满足漏洞 2：INFERRED 下两个来源均为 NULL 时 clause 3 退化为
    ingested_at 与自身比较（恒真），ingested_at（INFERRED 分支 available_at
    的来源）本应仍不能早于 effective_at。AKShare 回补数据全部落在
    INFERRED 分支，此漏洞影响面最大。"""
    early = dt.datetime(2025, 12, 31, 9, 0, tzinfo=dt.UTC)
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(
            quality="INFERRED", available_at=early, published_at=None,
            provider_available_at=None, ingested_at=early))
        db_session.flush()


def test_available_at_equal_to_effective_at_is_accepted(db_session):
    """新增的第 4 子句不应过紧：available_at 恰好等于 effective_at（当日零点）
    仍应被接受，而不是必须严格晚于 effective_at。"""
    midnight = dt.datetime(2026, 1, 2, 0, 0, tzinfo=dt.UTC)
    db_session.execute(INSERT, _row(
        quality="INFERRED", available_at=midnight, published_at=None,
        provider_available_at=None, ingested_at=midnight))
    db_session.flush()
