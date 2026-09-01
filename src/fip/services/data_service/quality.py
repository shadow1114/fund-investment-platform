from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


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
    def blocked_fund_ids(self) -> frozenset[int]:
        return frozenset(
            int(f.subject)
            for f in self.findings
            if f.scope is BlockingScope.FUND and f.level is QualityLevel.INVALID
        )

    @property
    def blocked_metrics(self) -> frozenset[str]:
        return frozenset(
            f.subject for f in self.findings if f.scope is BlockingScope.METRIC
        )


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

    if unavailable_adjusted_nav_ids:
        findings.append(QualityFinding(
            BlockingScope.METRIC, QualityLevel.INVALID, "adjusted_nav",
            f"{len(set(unavailable_adjusted_nav_ids))} 个份额类别的复权净值"
            "无法计算，依赖它的指标标记 UNAVAILABLE（不得填 0）",
        ))

    return QualityVerdict(tuple(findings))
