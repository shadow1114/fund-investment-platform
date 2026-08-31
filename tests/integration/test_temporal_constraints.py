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
    """effective_at 是 DATE，比较时隐式转当日 00:00，公告当天不应被拒。

    刻意使用 00:00:00 整（而非 00:30 之类严格晚于零点的时刻），才能真正
    钉住这条边界——00:30 在 > 和 >= 语义下都会通过，测不出隐式转换后
    effective_at 是否被当作 >= 的可取边界，而非只能严格晚于它。
    """
    midnight = dt.datetime(2026, 1, 2, 0, 0, 0, tzinfo=dt.UTC)
    db_session.execute(INSERT, _row(
        available_at=midnight,
        published_at=midnight,
        provider_available_at=midnight,
        ingested_at=midnight))
    db_session.flush()


def test_derived_forbids_provider_available_at(db_session):
    """DERIVED 意味着只拿到了公告时刻；同时又有 provider_available_at 说明
    应该标 EXACT 才对，是映射错误。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(quality="DERIVED", published_at=T0,
                                        provider_available_at=T1))
        db_session.flush()


def test_derived_requires_published_at(db_session):
    """DERIVED 必须有 published_at —— 没有任何来源时应该标 INFERRED，
    而不是 DERIVED。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(quality="DERIVED", published_at=None,
                                        provider_available_at=None))
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


# --- governance.interval_probe：IntervalMixin（anchor="valid_from"）覆盖 ---
# fix round 2 item 2：此前 IntervalMixin / interval_check / INTERVAL_SQL
# 完全没有测试覆盖，也正因如此 item 1 的 Critical（TIME_ORDER_SQL 硬编码
# effective_at，无法套用到 IntervalMixin 表）才一直未被发现。

INTERVAL_INSERT = text("""
    INSERT INTO governance.interval_probe
        (valid_from, valid_to, available_at, availability_quality,
         published_at, provider_available_at, ingested_at)
    VALUES
        (:valid_from, :valid_to, :available_at, :quality,
         :published_at, :provider_available_at, :ingested_at)
""")


def _interval_row(**overrides):
    base = dict(
        valid_from=D, valid_to=None, available_at=T1, quality="EXACT",
        published_at=T0, provider_available_at=T1, ingested_at=T2,
    )
    base.update(overrides)
    return base


def test_interval_valid_to_null_is_accepted(db_session):
    """valid_to 为 NULL 表示区间仍在生效中，应被接受。"""
    db_session.execute(INTERVAL_INSERT, _interval_row(valid_to=None))
    db_session.flush()


def test_interval_valid_from_equal_valid_to_is_rejected(db_session):
    """区间约束用的是严格 < ，valid_from == valid_to 不构成一个有效区间。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INTERVAL_INSERT, _interval_row(valid_to=D))
        db_session.flush()


def test_interval_valid_to_before_valid_from_is_rejected(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(INTERVAL_INSERT, _interval_row(
            valid_to=dt.date(2026, 1, 1)))
        db_session.flush()


def test_interval_available_at_cannot_precede_valid_from(db_session):
    """Critical 的回归测试：time_order 的 anchor 必须是 valid_from（而非
    硬编码的 effective_at）。若 anchor 没有正确传递，能拿到两个来源均为
    NULL 的 INFERRED 行、available_at 早于 valid_from 却仍被接受——即
    平台在区间生效前就“看到”了它。"""
    early = dt.datetime(2025, 12, 31, 9, 0, tzinfo=dt.UTC)
    with pytest.raises(IntegrityError):
        db_session.execute(INTERVAL_INSERT, _interval_row(
            quality="INFERRED", available_at=early, published_at=None,
            provider_available_at=None, ingested_at=early))
        db_session.flush()


def test_interval_legitimate_row_is_accepted(db_session):
    db_session.execute(INTERVAL_INSERT, _interval_row(
        valid_from=D, valid_to=dt.date(2026, 2, 1)))
    db_session.flush()
