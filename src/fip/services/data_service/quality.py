from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

# 当前唯一会产生 METRIC 级判定的指标。finding 的 subject 承载的是受影响的
# 份额类别 id（与 FUND 级同构，避免把『哪些份额类别』聚合掉），因此
# `blocked_metrics` 无法从 subject 反查指标名，只能借助这个已知常量表达
# 『哪个指标』。若未来出现第二种 METRIC 判定来源，需要扩展这里的映射逻辑
# （例如让判定来源自带指标名），而不是继续在这个常量上打补丁。
ADJUSTED_NAV_METRIC = "adjusted_nav"


class QualityLevel(StrEnum):
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


class BlockingScope(StrEnum):
    FUND = "FUND"      # 只影响该基金
    METRIC = "METRIC"  # 只影响依赖该指标的结果
    GLOBAL = "GLOBAL"  # 阻断整个决策周期


@dataclass(frozen=True, slots=True)
class QualityFinding:
    scope: BlockingScope
    level: QualityLevel
    subject: str
    reason: str


@dataclass(frozen=True, slots=True)
class QualityVerdict:
    findings: tuple[QualityFinding, ...]

    @property
    def is_globally_blocked(self) -> bool:
        return any(
            f.scope is BlockingScope.GLOBAL and f.level is QualityLevel.INVALID
            for f in self.findings
        )

    @property
    def blocked_share_class_ids(self) -> frozenset[int]:
        """本批次被 FUND 级阻断的份额类别 id 集合。

        故意不叫 `blocked_fund_ids`：`Fund` 与 `FundShareClass` 是两张
        独立的表、各自拥有互不相关的主键序列，本平台的计算最小单位是
        份额类别，下游多数表也按份额类别 id 建键。若把这里的 id 当作
        `Fund.id` 去过滤（例如 `Fund.id.in_(...)`），过滤的会是错误的
        实体 —— 且这些 id 往往仍能在 `fund` 表里命中真实的行，不会
        报错，是一种静默的错误结果，恰好落在这个代码库本该分得最清楚
        的地方。
        """
        return frozenset(
            int(f.subject)
            for f in self.findings
            if f.scope is BlockingScope.FUND and f.level is QualityLevel.INVALID
        )

    @property
    def blocked_metrics(self) -> frozenset[str]:
        """受阻断影响的指标名称集合（与 `blocked_share_class_ids` 是两个维度）。

        必须同 `is_globally_blocked` / `blocked_share_class_ids` 一样只
        看 `INVALID`：METRIC 级 finding 也可能是 WARNING（不阻断，仅
        提示），若不过滤 level，第一个非阻断的指标告警就会被这个属性
        误当作『阻断』。
        """
        if any(
            f.scope is BlockingScope.METRIC and f.level is QualityLevel.INVALID
            for f in self.findings
        ):
            return frozenset({ADJUSTED_NAV_METRIC})
        return frozenset()


def evaluate_batch_quality(
    expected_share_class_ids: Collection[int],
    arrived_share_class_ids: Collection[int],
    unavailable_adjusted_nav_ids: Collection[int],
    coverage_threshold: Decimal,
) -> QualityVerdict:
    """评估一个灌数批次的质量，产出带粒度的阻断判定。

    严禁静默降级（上游原则五）：任何缺失都必须产生 finding。
    但阻断有粒度 —— 一只基金缺数据不该阻断整个市场。
    """
    expected = set(expected_share_class_ids)
    arrived = set(arrived_share_class_ids)
    findings: list[QualityFinding] = []

    if not expected:
        return QualityVerdict((
            QualityFinding(
                BlockingScope.GLOBAL, QualityLevel.INVALID, "batch",
                "预期份额类别集合为空 —— 上游配置异常，不得视为全部到齐",
            ),
        ))

    coverage = Decimal(len(arrived & expected)) / Decimal(len(expected))
    if coverage < coverage_threshold:
        findings.append(QualityFinding(
            BlockingScope.GLOBAL, QualityLevel.INVALID, "batch",
            f"到达覆盖率 {coverage} 低于阈值 {coverage_threshold}，"
            "疑似全市场数据未到位，阻断本决策周期",
        ))

    for missing in sorted(expected - arrived):
        findings.append(QualityFinding(
            BlockingScope.FUND, QualityLevel.INVALID, str(missing),
            "本批次未收到该份额类别的数据",
        ))

    # 逐个份额类别单独产生 finding，而不是聚合成一条『N 个份额类别』
    # 的汇总 —— 否则具体是哪几个份额类别就从判定结果里丢失了，是本
    # 模块本该杜绝的静默降级的一种轻量变体。
    for unavailable in sorted(set(unavailable_adjusted_nav_ids)):
        findings.append(QualityFinding(
            BlockingScope.METRIC, QualityLevel.INVALID, str(unavailable),
            f"该份额类别的复权净值（{ADJUSTED_NAV_METRIC}）无法计算，"
            "依赖它的指标标记 UNAVAILABLE（不得填 0）",
        ))

    return QualityVerdict(tuple(findings))
