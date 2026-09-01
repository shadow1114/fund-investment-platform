import datetime as dt

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, func, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column

availability_quality_enum = ENUM(
    "EXACT", "DERIVED", "INFERRED",
    name="availability_quality_enum",
    create_type=False,
)

QUALITY_SOURCE_SQL = (
    "(availability_quality = 'EXACT' AND provider_available_at IS NOT NULL) OR "
    "(availability_quality = 'DERIVED' AND provider_available_at IS NULL "
    " AND published_at IS NOT NULL) OR "
    "(availability_quality = 'INFERRED' AND provider_available_at IS NULL "
    " AND published_at IS NULL)"
)


# --------------------------------------------------------------------------
# anchor 的 UTC 钉定（fix round 2 item 2，Critical）
#
# anchor（effective_at）是 DATE，其余时序列是 TIMESTAMPTZ。裸写
# `available_at >= effective_at` 会让 PostgreSQL 走 date→timestamptz 的隐式
# 转换，而那个转换是 STABLE 而非 IMMUTABLE 的：它把 DATE 解释为【会话
# TimeZone 下】的当日零点。于是同一行在不同会话时区下结论不同 ——
#   · Asia/Shanghai（UTC+8）：anchor = 前一日 16:00Z，约束偏松，
#     2026-08-30T20:00Z 这样真正早于生效日的行会被【误收】；
#   · America/Los_Angeles（UTC-7）：anchor = 当日 07:00Z，约束偏紧，
#     2026-08-31T03:00Z 这样合法的行会被【误拒】。
# 后果不止于插入：pg_restore 与 ALTER TABLE ... VALIDATE CONSTRAINT 也在
# 各自的会话时区下重新求值，可以拒绝一批早已存在、当初写入时完全合法的行。
#
# 版本化事实表现在只是【侥幸】安全：DISCLOSURE_LAG_DAYS = 1 把 available_at
# 推到了 anchor+24h，盖住了任何现实时区偏移。把时滞调成 0、或引入任何 lag
# 小于时区偏移的数据源，就会立刻重现。
#
# 修法是把转换显式钉在 UTC：`{anchor}::timestamp AT TIME ZONE 'UTC'`
# 先把 DATE 转成无时区的当日零点，再声明「这个零点读作 UTC」，得到一个与
# 会话时区无关的 TIMESTAMPTZ。全平台的时间语义本来就是 UTC
# （available_at / ingested_at 一律以 UTC 写入），这里只是把它写进约束。
def utc_anchor_sql(anchor: str) -> str:
    """把 DATE 列 anchor 转成【与会话时区无关】的 UTC 当日零点 TIMESTAMPTZ。"""
    return f"({anchor}::timestamp AT TIME ZONE 'UTC')"


_ANCHOR = utc_anchor_sql("effective_at")

# --------------------------------------------------------------------------
# 四条 clause 的单独定义。两类表【共享】clause 2 / clause 3，
# 只有 clause 1 / clause 4 是版本化事实表专有的 —— 见下面两个生成器的
# docstring。
_CLAUSE_1_PUBLISHED_AFTER_ANCHOR = f"(published_at IS NULL OR published_at >= {_ANCHOR})"
_CLAUSE_2_PROVIDER_AFTER_PUBLISHED = (
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at)"
)
_CLAUSE_3_INGESTED_LAST = (
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at))"
)
_CLAUSE_4_AVAILABLE_AFTER_ANCHOR = f"(available_at >= {_ANCHOR})"

# 版本化事实表（VersionedMixin，anchor = effective_at）的四子句时序约束。
TIME_ORDER_SQL = " AND ".join((
    _CLAUSE_1_PUBLISHED_AFTER_ANCHOR,
    _CLAUSE_2_PROVIDER_AFTER_PUBLISHED,
    _CLAUSE_3_INGESTED_LAST,
    _CLAUSE_4_AVAILABLE_AFTER_ANCHOR,
))

# 区间型状态表（IntervalMixin，区间起点 = valid_from）的两子句时序约束。
INTERVAL_TIME_ORDER_SQL = " AND ".join((
    _CLAUSE_2_PROVIDER_AFTER_PUBLISHED,
    _CLAUSE_3_INGESTED_LAST,
))

INTERVAL_SQL = "valid_to IS NULL OR valid_from < valid_to"


@declarative_mixin
class TimeSourceMixin:
    """available_at 的三个来源依据。

    available_at 是【解析产物】，三个来源是它的依据（03-data/01 §11）。
    published_at 与 provider_available_at 允许为空 —— Provider 能力有差异，
    拿不到就是拿不到，绝不允许用 ingested_at 回填（Constraint C-12）。
    """

    available_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    availability_quality: Mapped[str] = mapped_column(
        availability_quality_enum, nullable=False
    )
    published_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_available_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@declarative_mixin
class VersionedMixin(TimeSourceMixin):
    """事实型表：三时点 + version。修订产生新版本，旧版本保留、不覆盖。"""

    effective_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )


@declarative_mixin
class IntervalMixin(TimeSourceMixin):
    """状态型表：valid_from / valid_to。同样需要 available_at（03-erd §15.2）。

    只有 valid_from 没有 available_at 会形成前视偏差 —— 经理任职的生效日
    早于公告日是常态。
    """

    valid_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)


def quality_source_check(table: str) -> CheckConstraint:
    """把 available_at 的三级优先级写进数据库（04-database-design §4.4.1）。"""
    return CheckConstraint(QUALITY_SOURCE_SQL, name=f"ck_{table}_quality_source")


def time_order_check(table: str) -> CheckConstraint:
    """版本化事实表的四子句时序约束（03-data/01 §11.6）。"""
    return CheckConstraint(TIME_ORDER_SQL, name=f"ck_{table}_time_order")


def interval_time_order_check(table: str) -> CheckConstraint:
    """区间型状态表的两子句时序约束（不含 clause 1 / clause 4）。"""
    return CheckConstraint(INTERVAL_TIME_ORDER_SQL, name=f"ck_{table}_time_order")


def interval_check(table: str) -> CheckConstraint:
    return CheckConstraint(INTERVAL_SQL, name=f"ck_{table}_interval")


def temporal_check_constraints(table: str) -> tuple[CheckConstraint, CheckConstraint]:
    """【版本化事实表】（VersionedMixin）的标准约束组：quality_source + 四子句时序。

    ── 为什么版本化表与区间型表的时序不变式不同（本仓库最容易被改错的地方）──

    版本化事实表的 anchor 是 effective_at，语义是「这个【事实】在哪一天成立」：
    2026-08-31 的单位净值、当日的分红金额、当日的无风险利率。净值不可能在它
    自己的日期之前就被知道 —— 那不是「提前公告」，那是前视偏差。所以这类表
    保留全部四条 clause：

      clause 1  published_at >= effective_at   公告不早于事实成立日
      clause 2  provider_available_at >= published_at   推送不早于公告
      clause 3  ingested_at >= COALESCE(...)             落库最后发生
      clause 4  available_at >= effective_at   兜底：无论 available_at 解析自
                哪个来源，都不得早于事实成立日。clause 2 / clause 3 在来源为
                NULL 时会退化为真空满足（vacuous truth），必须靠 clause 4 堵住
                EXACT 分支的 provider_available_at 与 INFERRED 分支的
                ingested_at（见迁移 0003）。

    区间型状态表【不适用】clause 1 与 clause 4，务必改用
    interval_temporal_check_constraints()，理由见该函数的 docstring。
    误用本函数会让数据库拒收合法的预披露数据。
    """
    return (quality_source_check(table), time_order_check(table))


def interval_temporal_check_constraints(
    table: str,
) -> tuple[CheckConstraint, CheckConstraint]:
    """【区间型状态表】（IntervalMixin）的标准约束组：quality_source + 两子句时序。

    ── 为什么这里【必须】去掉 clause 1 与 clause 4 ──

    区间型表的区间起点是 valid_from，语义是「这个【状态】从哪天开始生效」，
    而不是「这个事实在哪天成立」。费率调整、申赎状态变更、基金分类转型、
    Provider 标识重指派在现实中几乎总是【提前公告】：公告日 8-25、生效日
    9-01。此时

        published_at  < valid_from   （clause 1 会拒收）
        available_at  < valid_from   （clause 4 会拒收）

    是合法且常见的事实。把它们当成违规，等于要求数据库相信「我们不可能在
    一项变更生效之前就知道它」—— 这不是防前视偏差，这是把「知悉时点」和
    「生效时点」混为一谈，结果是直接拒收真实数据。

    真正防前视偏差的不变式，是 available_at 与它的三个来源
    （published_at / provider_available_at / ingested_at）之间的先后关系 ——
    也就是保留下来的 clause 2、clause 3，加上 quality_source 对
    「available_at 取自哪个来源」的锁定。这三条与 valid_from 无关，
    在区间型表上原样成立、原样有效。

    区间是否可见由全平台唯一的可见性规则 `available_at <= decision_at`
    在【查询】时判定（PIT 解析），不由 CHECK 约束在【写入】时判定 ——
    这也是为什么放宽 clause 4 不会放进任何前视偏差：一条 8-25 就已知、
    9-01 才生效的费率，在 8-26 的决策里照样是可见的（我们确实知道它），
    在 8-24 的决策里照样不可见（available_at > decision_at）。

    区间型表额外还需单独调用 interval_check(table)（valid_from < valid_to）。
    """
    return (quality_source_check(table), interval_time_order_check(table))
