import datetime as dt
from dataclasses import dataclass
from enum import StrEnum


class RuntimeMode(StrEnum):
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"


class TriggerType(StrEnum):
    PERIODIC = "PERIODIC"
    DRIFT = "DRIFT"
    ELIGIBILITY_EVENT = "ELIGIBILITY_EVENT"
    CONSTRAINT_BREACH = "CONSTRAINT_BREACH"


class RecomputeScope(StrEnum):
    FULL_PIPELINE = "FULL_PIPELINE"          # Factor → Score → Universe → ⑤ → ⑥ → ⑦
    FROM_UNIVERSE = "FROM_UNIVERSE"          # ④ → ⑤ → ⑥ → ⑦
    FROM_RISK = "FROM_RISK"                  # ⑤ → ⑥ → ⑦
    FROM_CONSTRUCTION = "FROM_CONSTRUCTION"  # ⑥ → ⑦


_TRIGGER_TO_SCOPE: dict[TriggerType, RecomputeScope] = {
    TriggerType.PERIODIC: RecomputeScope.FULL_PIPELINE,
    TriggerType.ELIGIBILITY_EVENT: RecomputeScope.FROM_UNIVERSE,
    TriggerType.DRIFT: RecomputeScope.FROM_RISK,
    TriggerType.CONSTRAINT_BREACH: RecomputeScope.FROM_CONSTRUCTION,
}


@dataclass(frozen=True, slots=True)
class DecisionExecutionContext:
    """一次决策执行的显式上下文，贯穿全部阶段。

    DEC-1 在链路起点创建，不在中途重新生成
    DEC-2 decision_at 由上下文提供，领域服务不自行获取当前时间
    DEC-3 上下文随决策快照落库 —— 它是复现该次决策的入口
    """

    decision_id: str
    decision_at: dt.date
    data_as_of: dt.date
    strategy_version: str
    policy_version: str
    code_version: str
    trigger_type: TriggerType
    recompute_scope: RecomputeScope
    runtime_mode: RuntimeMode

    def __post_init__(self) -> None:
        if self.data_as_of > self.decision_at:
            raise ValueError(
                f"data_as_of={self.data_as_of} 晚于 decision_at={self.decision_at}，"
                "构成未来信息泄漏"
            )
        expected = _TRIGGER_TO_SCOPE[self.trigger_type]
        if self.recompute_scope is not expected:
            raise ValueError(
                f"recompute_scope={self.recompute_scope} 与 "
                f"trigger_type={self.trigger_type} 不匹配，应为 {expected}。"
                "重算深度由触发类型决定，不得在运行时动态调整"
            )

    @classmethod
    def scope_for(cls, trigger: TriggerType) -> RecomputeScope:
        return _TRIGGER_TO_SCOPE[trigger]
