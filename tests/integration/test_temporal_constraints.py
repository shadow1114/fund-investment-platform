import datetime as dt
import os
import pathlib

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


# --- clause 5：available_at 不得早于它自己声明的来源 -------------------------
# fix round 3 item 1（Critical）：clause 2 是 provider_available_at >=
# published_at，clause 3 是 ingested_at >= COALESCE(...) —— 两条都【没有提到
# available_at】。于是 fix round 2 为区间表删掉 clause 4 之后，区间表上的
# available_at 不再被任何 CHECK 触及；而版本化表上这个洞更老 —— clause 4 只
# 把 available_at 钉在 effective_at 之后，从未把它与三个来源关联过，所以
# 「公告 18:00、却声称 10:00 就可用」这种纯前视偏差一直可以写进库。
#
# 补上的第五条子句与 anchor 无关，两类表都成立：
#     available_at >= COALESCE(provider_available_at, published_at)
#   · EXACT    ：available_at == provider_available_at，取等号通过；
#   · DERIVED  ：provider_available_at 为 NULL，COALESCE 落到 published_at，
#                available_at == published_at，取等号通过；
#   · INFERRED ：两者皆 NULL，COALESCE 为 NULL，比较为 NULL → 真空满足。
#                这正是 declared_lag_availability（净值灌数）走的路径，
#                下面两条守卫测试专门钉住它没有被误伤。
# 【不】加 available_at <= ingested_at：INFERRED 下 available_at =
# effective_at + 时滞 可以晚于 ingested_at（当天灌当天的数据就会触发），
# 那会拒掉合法行。


def test_available_at_cannot_precede_its_own_declared_source(db_session):
    """版本化表：公告在 18:00，却声称 10:00 就可用 —— 纯粹的前视偏差。

    这一行满足原有全部四条 clause（published_at >= effective_at、
    provider_available_at >= published_at、ingested_at 最后、available_at >=
    effective_at），仅仅是 available_at 早于它自己的来源。修复前【被接受】。
    """
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(
            quality="EXACT", available_at=T0,
            published_at=T1, provider_available_at=T1, ingested_at=T2))
        db_session.flush()


def test_interval_available_at_cannot_precede_its_own_declared_source(db_session):
    """区间表：同一个洞。放宽 clause 4 是对的，但没有任何东西补上它的位置。

    available_at = 2025-12-25 早于 published_at = 2026-01-02 10:00，
    等于声称我们在公告前 8 天就知道了。修复前【被接受】。
    """
    early = dt.datetime(2025, 12, 25, 9, 0, tzinfo=dt.UTC)
    with pytest.raises(IntegrityError):
        db_session.execute(INTERVAL_INSERT, _interval_row(
            quality="EXACT", available_at=early,
            published_at=T0, provider_available_at=T1, ingested_at=T2))
        db_session.flush()


def test_inferred_available_at_stays_free_of_the_source_floor(db_session):
    """守卫：INFERRED 下两个来源皆 NULL，COALESCE 为 NULL，新子句必须真空满足。

    净值灌数（declared_lag_availability）走的就是这条路径：available_at =
    effective_at + 声明时滞，没有任何来源可比。新子句若误伤这里，全平台的
    净值一行都写不进去。
    """
    db_session.execute(INSERT, _row(
        quality="INFERRED", available_at=T2, published_at=None,
        provider_available_at=None, ingested_at=T1))
    db_session.flush()


def test_interval_inferred_available_at_stays_free_of_the_source_floor(db_session):
    """守卫：区间表上同一条真空满足路径 —— 早于 valid_from 也照样接受。"""
    early = dt.datetime(2025, 12, 25, 9, 0, tzinfo=dt.UTC)
    db_session.execute(INTERVAL_INSERT, _interval_row(
        quality="INFERRED", available_at=early, published_at=None,
        provider_available_at=None, ingested_at=early))
    db_session.flush()


def test_derived_available_at_equal_to_published_at_is_accepted(db_session):
    """守卫：DERIVED 取等号必须通过 —— 新子句是 >= 而非严格 >。"""
    db_session.execute(INSERT, _row(
        quality="DERIVED", available_at=T0, published_at=T0,
        provider_available_at=None, ingested_at=T2))
    db_session.flush()


def test_interval_exact_available_at_equal_to_provider_time_is_accepted(db_session):
    """守卫：EXACT 取等号必须通过（区间表上同理）。"""
    db_session.execute(INTERVAL_INSERT, _interval_row(
        quality="EXACT", available_at=T1,
        published_at=T0, provider_available_at=T1, ingested_at=T2))
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


# --------------------------------------------------------------------------
# CHECK 约束的黄金快照
# --------------------------------------------------------------------------

_SNAPSHOT = pathlib.Path(__file__).with_name("check_constraints.snapshot")

_ALL_CHECKS = text("""
    SELECT n.nspname||'.'||t.relname||'.'||c.conname AS k,
           pg_get_constraintdef(c.oid) AS d
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE c.contype = 'c'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY 1
""")


def test_check_constraints_match_the_committed_snapshot(db_session):
    """库里【实际】的 CHECK 定义必须与提交在仓库里的快照逐字相同。

    为什么需要这条测试：本仓库一直把「alembic revision --autogenerate 报告
    零操作」当作硬闸门，它确实抓出过三次误删。但 autogenerate【根本不比较
    CHECK 表达式】—— 实测把 market.fund_nav 的整条时序 CHECK 换成恒真的
    `CHECK (1=1)`（即把全平台 PIT 强制彻底废掉），autogenerate 依然报告
    零操作。也就是说那道闸门对 CHECK 漂移完全失明，而本平台的载重时序
    不变式恰恰全部住在 CHECK 里。

    本测试的对象是【迁移的产出】而非 ORM 声明：测试库由 conftest 跑真实
    alembic upgrade head 建起（见 tests/conftest.py），所以快照比对验的是
    迁移真正在数据库里建出了什么。

    快照【故意】做成逐字比对：任何对 mixins.py 或迁移的改动都会让它失败，
    强制改动者重新生成快照并在 diff 里正面看到 DDL 到底变了什么 —— 这正是
    autogenerate 给不了的那一眼。合法改动后这样重新生成（fix round 4 item 5：
    此处原先指向 tests/integration/_snapshot_query.sql，而【该文件不存在】，
    照着做只会得到一个 FileNotFoundError）：

        FIP_WRITE_CHECK_SNAPSHOT=1 .venv/bin/pytest \
            tests/integration/test_temporal_constraints.py -k snapshot

    它按当前测试库（conftest 跑真实 alembic upgrade head 建起）重写快照文件，
    然后【故意以失败结束】—— 重新生成永远不能顺带变绿，改动者必须去看
    git diff 再不带该环境变量重跑一次。
    """
    rows = db_session.execute(_ALL_CHECKS).all()
    actual = "\n".join(f"{k}\n    {d}" for k, d in rows) + "\n"

    if os.environ.get("FIP_WRITE_CHECK_SNAPSHOT") == "1":
        _SNAPSHOT.write_text(actual, encoding="utf-8")
        pytest.fail(
            f"已按当前数据库重新生成 {_SNAPSHOT.name}。请在 git diff 里逐条确认"
            "这些 DDL 变化确实是你想要的，再不带 FIP_WRITE_CHECK_SNAPSHOT 重跑。"
        )

    expected = _SNAPSHOT.read_text(encoding="utf-8")

    if actual != expected:
        actual_map = {k: d for k, d in rows}
        expected_map = {}
        lines = expected.splitlines()
        for i in range(0, len(lines) - 1, 2):
            expected_map[lines[i]] = lines[i + 1].strip()
        added = sorted(set(actual_map) - set(expected_map))
        removed = sorted(set(expected_map) - set(actual_map))
        changed = sorted(
            k for k in set(actual_map) & set(expected_map)
            if actual_map[k] != expected_map[k]
        )
        pytest.fail(
            "数据库里的 CHECK 定义与快照不符。\n"
            f"新增 {len(added)}：{added}\n"
            f"消失 {len(removed)}：{removed}\n"
            f"变更 {len(changed)}：{changed}\n"
            + "".join(
                f"\n  {k}\n    快照: {expected_map[k]}\n    实际: {actual_map[k]}"
                for k in changed[:5]
            )
        )


# --------------------------------------------------------------------------
# 迁移 0016：三张区间表补齐的数据库不变式（Plan-1 交接项四 / 裁定 P2-3）
# --------------------------------------------------------------------------
# 这三条测的不是 CHECK，而是 EXCLUDE USING gist 与两个部分唯一索引 ——
# 黄金快照只查 contype='c'，看不见它们；autogenerate 闸门只比 ORM 声明与
# 库结构是否一致，不检验语义是否正确。语义只能靠下面这种【行为】测试钉住。

_INV_VALID_FROM = dt.date(2020, 1, 1)
_INV_MID = dt.date(2020, 6, 1)
_INV_END = dt.date(2020, 9, 1)
_INV_AVAILABLE_AT = dt.datetime(2019, 12, 20, 9, 0, tzinfo=dt.UTC)
_INV_INGESTED_AT = dt.datetime(2019, 12, 20, 10, 0, tzinfo=dt.UTC)


def _interval_times() -> dict:
    """INFERRED 路径：两个来源皆 NULL，clause 5 真空满足（C-12：不伪造时间戳）。"""
    return dict(
        available_at=_INV_AVAILABLE_AT,
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=_INV_INGESTED_AT,
    )


def _make_fund_and_share_class(session, code: str):
    from fip.services.data_service.models.fund import Fund, FundShareClass

    fund = Fund(fund_code=code, product_name=f"P-{code}", grouping_status="CONFIRMED")
    session.add(fund)
    session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name=f"{code}A")
    session.add(sc)
    session.flush()
    return fund, sc


def test_same_manager_cannot_hold_overlapping_assignments(db_session):
    """共管允许（不同 manager 同期同基金），同一经理区间重叠不允许。

    排他键必须【同时含 manager_id】：退化成「仅 fund_id + daterange」会直接
    拒绝合法的共管数据。边界写成 '[)' 才能让首尾相接的任职交接通过 ——
    写成默认的 '[]' 时下面第 3 步会红。
    """
    from fip.services.data_service.models.fund import FundManager, FundManagerAssignment

    fund, _ = _make_fund_and_share_class(db_session, "P-FMA")
    m1 = FundManager(manager_code="M-1", manager_name="张三")
    m2 = FundManager(manager_code="M-2", manager_name="李四")
    db_session.add_all([m1, m2])
    db_session.flush()

    # 1) 同一基金、同一区间、两位不同经理 —— 共管，必须成功
    db_session.add(FundManagerAssignment(
        fund_id=fund.id, manager_id=m1.id,
        valid_from=_INV_VALID_FROM, valid_to=_INV_MID, **_interval_times()))
    db_session.add(FundManagerAssignment(
        fund_id=fund.id, manager_id=m2.id,
        valid_from=_INV_VALID_FROM, valid_to=_INV_MID, **_interval_times()))
    db_session.flush()

    # 2) 同一经理、首尾相接（前段 valid_to == 后段 valid_from）—— 必须成功
    db_session.add(FundManagerAssignment(
        fund_id=fund.id, manager_id=m1.id,
        valid_from=_INV_MID, valid_to=_INV_END, **_interval_times()))
    db_session.flush()

    # 3) 同一经理、同一基金、区间真重叠 —— 必须被数据库拒收
    db_session.add(FundManagerAssignment(
        fund_id=fund.id, manager_id=m1.id,
        valid_from=dt.date(2020, 3, 1), valid_to=dt.date(2020, 4, 1),
        **_interval_times()))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_fund_fee_allows_one_open_interval_per_fee_type(db_session):
    """每种 fee_type 各一条开放区间是合法的；同一 fee_type 两条则不合法。

    唯一性键必须是 (share_class_id, fee_type)：只用 share_class_id 会把
    「管理费 + 托管费同时开放」判成违规，那是正常数据。
    """
    from decimal import Decimal

    from fip.services.data_service.models.fund import FundFee

    _, sc = _make_fund_and_share_class(db_session, "P-FEE")

    db_session.add(FundFee(
        share_class_id=sc.id, fee_type="MANAGEMENT", rate=Decimal("0.015"),
        valid_from=_INV_VALID_FROM, valid_to=None, **_interval_times()))
    db_session.add(FundFee(
        share_class_id=sc.id, fee_type="CUSTODY", rate=Decimal("0.0025"),
        valid_from=_INV_VALID_FROM, valid_to=None, **_interval_times()))
    db_session.flush()

    db_session.add(FundFee(
        share_class_id=sc.id, fee_type="MANAGEMENT", rate=Decimal("0.012"),
        valid_from=_INV_MID, valid_to=None, **_interval_times()))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_fund_status_history_allows_only_one_open_interval(db_session):
    """同一份额类别至多一条 valid_to IS NULL —— 「当前状态」只能有一个。"""
    from fip.services.data_service.models.fund import FundStatusHistory

    _, sc = _make_fund_and_share_class(db_session, "P-FSH")

    db_session.add(FundStatusHistory(
        share_class_id=sc.id, lifecycle_status="NORMAL",
        subscription_open=True, redemption_open=True,
        valid_from=_INV_VALID_FROM, valid_to=_INV_MID, **_interval_times()))
    db_session.add(FundStatusHistory(
        share_class_id=sc.id, lifecycle_status="SUSPENDED_SUBSCRIPTION",
        subscription_open=False, redemption_open=True,
        valid_from=_INV_MID, valid_to=None, **_interval_times()))
    db_session.flush()

    db_session.add(FundStatusHistory(
        share_class_id=sc.id, lifecycle_status="NORMAL",
        subscription_open=True, redemption_open=True,
        valid_from=_INV_END, valid_to=None, **_interval_times()))
    with pytest.raises(IntegrityError):
        db_session.flush()
