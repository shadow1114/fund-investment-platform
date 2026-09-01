import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from fip.platform.decision_data.context import DecisionExecutionContext


@dataclass(frozen=True, slots=True)
class NavPoint:
    effective_at: dt.date
    adjusted_nav: Decimal | None
    unit_nav: Decimal
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
    def context(self) -> DecisionExecutionContext:
        return self._context

    def navs(self) -> NavPitRepository:
        # 延迟 import：Task 15 才会创建
        # fip.services.data_service.repositories.nav。这里若改为模块级
        # import 会让 platform 层在模块加载时就依赖 services 层，
        # 反转了架构规定的依赖方向（Task 6 的 fitness test 会对此断言）。
        from fip.services.data_service.repositories.nav import SqlNavPitRepository

        return SqlNavPitRepository(
            session=self._session, decision_at=self.decision_at
        )
