import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from fip.platform.decision_data.context import DecisionExecutionContext


def visible_until_for(decision_at: dt.date) -> dt.datetime:
    """把 decision_at（业务日期）翻译成 `available_at <= ?` 的时间戳上界。

    这是全平台唯一可见性规则 `available_at <= decision_at`（G-1）的**唯一**
    落地形式，本函数是它在代码中的唯一归属。

    ── 为什么必须只有一份（Plan-1 交接项 H-1）──

    Plan-1 结束时同一行 `dt.datetime.combine(decision_at, dt.time.max,
    tzinfo=dt.UTC)` 逐字住在 repositories/nav.py 与 normalization/backfill.py
    两个不同的层，没有共同归属、没有任何测试断言两者相等。Plan-2 要为
    risk_free_rate / fund_classification_history 写第二、第三个 PIT 读取路径，
    第三份拷贝只要写成 `dt.time.min`，两条路径就会对同一个 decision_at 解析出
    不同的可见集合 —— 不报错、不告警，回测和实盘看到不同的数据。

    ── 取日终而不是日初 ──

    decision_at 是【业务日期】，available_at 是【时间戳】。「当日可见」意味着
    当日任意时刻的披露都算数，因此上界取该日终了时刻。取日初会让整整一天的
    披露对当日决策不可见（信息偏少的方向也是错的：它会让因子在披露日当天
    静默变成 UNAVAILABLE）。

    ── 已知边界（Plan-1 交接项二.4，如实登记，本任务不修）──

    日终钉在 UTC。若披露时刻按 UTC+8 记，本规则相当于允许 decision_at 当天
    看到最多 8 小时【之后】的披露。这是 Plan-1 的既有约定，不是现算改造引入的；
    真正的修法是给 available_at 引入交易日历与市场时区，属后续项。
    """
    return dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)


def resolve_visible_until(decision_at: dt.date) -> dt.datetime:
    """兼容 Plan-1 调用方；唯一的时点翻译规则在 visible_until_for。"""
    return visible_until_for(decision_at)


@dataclass(frozen=True, slots=True)
class NavPoint:
    effective_at: dt.date
    adjusted_nav: Decimal
    unit_nav: Decimal
    version: int
    availability_quality: str
    chain_availability_quality: str


@dataclass(frozen=True, slots=True)
class ClassificationPoint:
    classification_code: str
    valid_from: dt.date
    availability_quality: str


@dataclass(frozen=True, slots=True)
class FeePoint:
    fee_type: str
    rate: Decimal
    valid_from: dt.date
    availability_quality: str


@dataclass(frozen=True, slots=True)
class RiskFreeRatePoint:
    effective_at: dt.date
    tenor: str
    rate: Decimal
    version: int
    availability_quality: str


@runtime_checkable
class NavPitRepository(Protocol):
    """时点感知的净值访问。

    注意方法签名中【没有】任何时点参数 —— decision_at 由 PitDataContext
    在构造期绑定并注入实现。这使调用方无法省略时点条件（PIT-A2）。
    本 Protocol 同样不提供任何『取最新一条』的方法（PIT-A3）。
    """

    def adjusted_nav_series(
        self,
        share_class_id: int,
        date_from: dt.date,
        date_to: dt.date,
    ) -> list[NavPoint]: ...


@runtime_checkable
class ClassificationPitRepository(Protocol):
    def current(self, fund_id: int) -> ClassificationPoint | None: ...


@runtime_checkable
class FeePitRepository(Protocol):
    def current(self, share_class_id: int) -> tuple[FeePoint, ...]: ...


@runtime_checkable
class RiskFreeRatePitRepository(Protocol):
    def series(
        self,
        currency: str,
        tenor: str,
        date_from: dt.date,
        date_to: dt.date,
    ) -> tuple[RiskFreeRatePoint, ...]: ...


class PitDataContext:
    """决策上下文的数据视图。

    领域逻辑只通过注入的本对象访问数据，不自行建立连接（SEI-1）。
    Live 与 Backtest 的差异全部体现在注入的 decision_at 与 session 上，
    领域逻辑本身不感知 runtime_mode（SEI-2）。
    """

    def __init__(self, context: DecisionExecutionContext, session: Any) -> None:
        self._context = context
        self._session = session

    @property
    def decision_at(self) -> dt.date:
        return self._context.decision_at

    @property
    def visible_until(self) -> dt.datetime:
        """本次决策的可见性上界：`available_at <= visible_until`。

        PitDataContext 是 decision_at 的唯一构造入口，因此这条翻译规则的
        唯一对外出口就在这里。任何 PIT 读取实现都应当接收本属性的值，
        而不是自己再翻译一次 decision_at（H-1）。
        """
        return visible_until_for(self.decision_at)

    @property
    def context(self) -> DecisionExecutionContext:
        return self._context

    def navs(self) -> NavPitRepository:
        # 延迟 import：Task 15 才会创建
        # fip.services.data_service.repositories.nav。这里若改为模块级
        # import 会让 platform 层在模块加载时就依赖 services 层，
        # 反转了架构规定的依赖方向（Task 6 的 fitness test 会对此断言）。
        from fip.services.data_service.repositories.nav import SqlNavPitRepository

        return SqlNavPitRepository(
            session=self._session, visible_until=self.visible_until
        )

    def classifications(self) -> ClassificationPitRepository:
        from fip.services.data_service.repositories.classification import (
            SqlClassificationPitRepository,
        )

        return SqlClassificationPitRepository(self._session, self.visible_until)

    def fees(self) -> FeePitRepository:
        from fip.services.data_service.repositories.fee import SqlFeePitRepository

        return SqlFeePitRepository(self._session, self.visible_until)

    def risk_free_rates(self) -> RiskFreeRatePitRepository:
        from fip.services.data_service.repositories.risk_free_rate import (
            SqlRiskFreeRatePitRepository,
        )

        return SqlRiskFreeRatePitRepository(self._session, self.visible_until)
