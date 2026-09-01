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


def test_interval_available_at_may_precede_valid_from(db_session):
    """fix round 2 item 1：区间表【必须】接受 available_at 早于 valid_from。

    费率调整、申赎状态变更、基金分类转型、Provider 标识重指派在现实中几乎
    总是提前公告：公告日 8-25、生效日 9-01。此时 available_at < valid_from
    是合法且常见的事实 —— 「知悉时点」与「生效时点」是两件事，把它们绑在
    一起（原 clause 4）会让数据库直接拒收真实数据。

    防前视偏差的不变式由 clause 2 / clause 3 / quality_source 完整表达，
    与 valid_from 无关，下面几条测试逐一锁住它们仍然有效。
    """
    early = dt.datetime(2025, 12, 25, 9, 0, tzinfo=dt.UTC)
    db_session.execute(INTERVAL_INSERT, _interval_row(
        quality="INFERRED", available_at=early, published_at=None,
        provider_available_at=None, ingested_at=early))
    db_session.flush()


def test_interval_published_at_may_precede_valid_from(db_session):
    """同上，clause 1 也必须去掉：预披露公告日就是早于生效日的。"""
    announced = dt.datetime(2025, 12, 25, 9, 0, tzinfo=dt.UTC)
    pushed = dt.datetime(2025, 12, 25, 9, 3, tzinfo=dt.UTC)
    db_session.execute(INTERVAL_INSERT, _interval_row(
        quality="EXACT", available_at=pushed, published_at=announced,
        provider_available_at=pushed, ingested_at=pushed))
    db_session.flush()


def test_interval_still_rejects_provider_available_at_before_published_at(db_session):
    """clause 2 必须原样保留：推送不可能早于公告。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INTERVAL_INSERT, _interval_row(
            published_at=T1, provider_available_at=T0))
        db_session.flush()


def test_interval_still_rejects_ingested_at_before_provider_available_at(db_session):
    """clause 3 必须原样保留：落库不可能早于我们能拿到它的时刻。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INTERVAL_INSERT, _interval_row(
            provider_available_at=T2,
            ingested_at=dt.datetime(2026, 1, 2, 11, 0, tzinfo=dt.UTC)))
        db_session.flush()


def test_interval_still_enforces_quality_source(db_session):
    """quality_source 必须原样保留：EXACT 却没有 provider_available_at
    是伪装成精确值的兜底值 —— 这一条与 valid_from 无关，不受本轮放宽影响。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INTERVAL_INSERT, _interval_row(
            quality="EXACT", provider_available_at=None))
        db_session.flush()


def test_interval_legitimate_row_is_accepted(db_session):
    db_session.execute(INTERVAL_INSERT, _interval_row(
        valid_from=D, valid_to=dt.date(2026, 2, 1)))
    db_session.flush()


# --- CHECK 不得依赖会话时区 -----------------------------------------------
# fix round 2 item 2（Critical）：anchor 是 DATE、其余列是 TIMESTAMPTZ，
# `timestamptz >= date` 走 STABLE 的 date→timestamptz 转换，结果依赖会话
# TimeZone —— 同一行在不同机器上可以一次合法一次非法，pg_restore /
# VALIDATE CONSTRAINT 因此可能拒绝已经存在的行。修复是把 anchor 的转换显式
# 钉在 UTC：`{anchor}::timestamp AT TIME ZONE 'UTC'`。
#
# 既有两个 fixture 的 FIXED_NOW 都是 18:00 UTC，即便在 UTC-8 的 CI 上也照样
# 通过 —— 这正是这个缺陷一直没被抓到的原因。下面这组用例刻意把会话时区切到
# UTC 以西与以东【两侧】，并选取落在时区偏移窗口内的时刻。

TZ_EFFECTIVE_AT = dt.date(2026, 8, 31)
# 03:00Z 落在 America/Los_Angeles（UTC-7 夏令时）的偏移窗口内：
# 未钉 UTC 时 anchor 会被解释成 2026-08-31 00:00 PDT = 07:00Z，本行被误拒。
TZ_EARLY_MORNING_UTC = dt.datetime(2026, 8, 31, 3, 0, tzinfo=dt.UTC)
# 前一日 20:00Z 落在 Asia/Shanghai（UTC+8）的偏移窗口内：
# 未钉 UTC 时 anchor 会被解释成 2026-08-31 00:00 CST = 2026-08-30 16:00Z，
# 本行被误【收】—— 它确实早于生效日的 UTC 零点，应当被拒。
TZ_PREVIOUS_EVENING_UTC = dt.datetime(2026, 8, 30, 20, 0, tzinfo=dt.UTC)


def _tz_row(**overrides):
    base = dict(
        effective_at=TZ_EFFECTIVE_AT, quality="INFERRED",
        published_at=None, provider_available_at=None,
    )
    base.update(overrides)
    return _row(**base)


@pytest.mark.parametrize(
    "session_tz", ["UTC", "Asia/Shanghai", "America/Los_Angeles", "Pacific/Honolulu"]
)
def test_time_order_verdict_does_not_depend_on_session_timezone(db_session, session_tz):
    """同一行在任何会话时区下都必须被接受。

    这是本条 Critical 的直接复现：修复前，在 America/Los_Angeles 下
    effective_at=2026-08-31 且 available_at/ingested_at=2026-08-31T03:00Z
    的行会抛 CheckViolation，而同一组值在 Asia/Shanghai 与 UTC 下都成立。
    """
    db_session.execute(text(f"SET LOCAL TimeZone TO '{session_tz}'"))
    db_session.execute(INSERT, _tz_row(
        available_at=TZ_EARLY_MORNING_UTC, ingested_at=TZ_EARLY_MORNING_UTC))
    db_session.flush()


@pytest.mark.parametrize(
    "session_tz", ["UTC", "Asia/Shanghai", "America/Los_Angeles", "Pacific/Honolulu"]
)
def test_time_order_rejects_pre_utc_midnight_row_in_every_timezone(db_session, session_tz):
    """反方向：早于生效日 UTC 零点的行在任何会话时区下都必须被拒。

    未钉 UTC 时，Asia/Shanghai（UTC+8）会把 anchor 退到前一日 16:00Z，
    于是 2026-08-30T20:00Z 这一行被【误收】—— 时区依赖不只是「误拒」，
    也会让真正的前视偏差从东八区悄悄溜进来。
    """
    db_session.execute(text(f"SET LOCAL TimeZone TO '{session_tz}'"))
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _tz_row(
            available_at=TZ_PREVIOUS_EVENING_UTC,
            ingested_at=TZ_PREVIOUS_EVENING_UTC))
        db_session.flush()
