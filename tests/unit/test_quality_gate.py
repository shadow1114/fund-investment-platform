from decimal import Decimal

from fip.services.data_service.quality import (
    BlockingScope,
    QualityFinding,
    QualityLevel,
    QualityVerdict,
    evaluate_batch_quality,
)

THRESHOLD = Decimal("0.95")


def _verdict(expected, arrived, unavailable=()):
    return evaluate_batch_quality(expected, arrived, unavailable, THRESHOLD)


def test_full_arrival_is_valid():
    verdict = _verdict([1, 2, 3], [1, 2, 3])
    assert verdict.findings == ()
    assert verdict.is_globally_blocked is False


def test_single_missing_fund_blocks_only_that_fund():
    """一只基金缺数据不该阻断整个市场。"""
    verdict = _verdict(list(range(1, 101)), list(range(2, 101)))
    assert verdict.is_globally_blocked is False
    assert verdict.blocked_share_class_ids == frozenset({1})
    assert all(f.scope is BlockingScope.FUND for f in verdict.findings)


def test_coverage_below_threshold_blocks_globally():
    """全市场数据未到位 → 阻断整个决策周期，人工确认后继续。"""
    verdict = _verdict(list(range(1, 101)), list(range(1, 91)))  # 覆盖率 0.90
    assert verdict.is_globally_blocked is True
    assert any(f.scope is BlockingScope.GLOBAL and f.level is QualityLevel.INVALID
               for f in verdict.findings)


def test_coverage_exactly_at_threshold_is_not_blocked():
    verdict = _verdict(list(range(1, 101)), list(range(1, 96)))  # 覆盖率 0.95
    assert verdict.is_globally_blocked is False


def test_unavailable_adjusted_nav_is_metric_level():
    """复权净值算不出 → 只影响依赖它的指标，基金本身仍在池内。"""
    verdict = _verdict([1, 2], [1, 2], unavailable=[2])
    assert verdict.is_globally_blocked is False
    assert verdict.blocked_share_class_ids == frozenset()
    assert "adjusted_nav" in verdict.blocked_metrics
    metric_findings = [f for f in verdict.findings if f.scope is BlockingScope.METRIC]
    assert len(metric_findings) == 1
    assert metric_findings[0].subject == "2"


def test_multiple_unavailable_adjusted_nav_ids_each_get_their_own_finding():
    """指标级判定不能把受影响的份额类别聚合掉 —— 每个 id 都要能在 finding 里找到。"""
    verdict = _verdict([1, 2, 3], [1, 2, 3], unavailable=[2, 3])
    metric_subjects = {f.subject for f in verdict.findings if f.scope is BlockingScope.METRIC}
    assert metric_subjects == {"2", "3"}
    assert "adjusted_nav" in verdict.blocked_metrics


def test_empty_expectation_blocks_globally():
    """预期为空说明上游配置有问题，不能当作『全部到齐』。"""
    verdict = _verdict([], [])
    assert verdict.is_globally_blocked is True


def test_findings_carry_actionable_reasons():
    """只给结论不给原因，运维无法处置。"""
    verdict = _verdict([1, 2], [1])
    assert all(f.reason for f in verdict.findings)
    assert all(f.subject for f in verdict.findings)


def test_no_silent_degradation_missing_funds_are_never_dropped_quietly():
    """缺失必须产生 finding —— 静默丢弃是原则五禁止的降级。"""
    verdict = _verdict([1, 2, 3], [1])
    subjects = {f.subject for f in verdict.findings if f.scope is BlockingScope.FUND}
    assert subjects == {"2", "3"}


def test_warning_level_metric_finding_does_not_block():
    """METRIC 级的 WARNING 不得被当作阻断。

    三个派生属性（is_globally_blocked / blocked_share_class_ids /
    blocked_metrics）必须共享同一条不变式：只有 INVALID 才阻断。
    evaluate_batch_quality 目前只会产出 INVALID 的 METRIC finding，
    所以这条不变式无法经由它触达 —— 必须【直接构造】一个 WARNING 的
    METRIC finding 才能覆盖。没有这个测试，blocked_metrics 里的 level
    过滤被删掉也不会有任何测试报警（Task 18 复评的 PARTIALLY 一条）。
    """
    verdict = QualityVerdict((
        QualityFinding(
            scope=BlockingScope.METRIC,
            level=QualityLevel.WARNING,
            subject="7",
            reason="复权净值口径存疑，但仍可用",
        ),
    ))
    assert verdict.blocked_metrics == frozenset()
    assert verdict.blocked_share_class_ids == frozenset()
    assert verdict.is_globally_blocked is False
