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

# 假设：披露不早于生效（即不存在「先公告、后生效」的预披露事实）。
# clause 1 已经隐含这个假设（published_at >= effective_at）；clause 4 把它
# 显式地施加到 available_at 本身 —— 无论 available_at 最终解析自哪个来源，
# 都不能早于 effective_at，这才是「不能在事实发生前看到它」这条不变式的
# 直接表达。若 published_at 或两个来源均为 NULL，clause 2 / clause 3 会
# 退化为真空满足（vacuous truth），必须靠 clause 4 兜底，否则 EXACT 分支的
# provider_available_at、INFERRED 分支的 ingested_at 可以早于 effective_at
# 而不被拦下 —— 对 EXACT/INFERRED 而言 available_at 分别取自这两列，等价于
# 平台在事实生效前就“看到”了它，即前视偏差。
# M1 覆盖的数据类型（净值、分红、无风险利率）均为「先生效、后披露」，此假设
# 成立；未来若引入预披露事实（先公告、后生效），须重新审视这条约束。
TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= effective_at) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= effective_at)"
)

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
    """时序约束（03-data/01 §11.6）。

    effective_at 是 DATE、其余是 TIMESTAMPTZ，比较时 effective_at 隐式转为
    当日 00:00，因此「公告发生在生效日当天」仍满足约束。
    """
    return CheckConstraint(TIME_ORDER_SQL, name=f"ck_{table}_time_order")


def interval_check(table: str) -> CheckConstraint:
    return CheckConstraint(INTERVAL_SQL, name=f"ck_{table}_interval")


def temporal_check_constraints(table: str) -> tuple[CheckConstraint, CheckConstraint]:
    """版本化表的两组标准约束。区间型表另需 interval_check。"""
    return (quality_source_check(table), time_order_check(table))
