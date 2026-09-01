from decimal import Decimal

from fip.services.data_service.quality import (
    BlockingScope,
    QualityLevel,
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
    assert verdict.blocked_fund_ids == frozenset({1})
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
    assert verdict.blocked_fund_ids == frozenset()
    assert "adjusted_nav" in verdict.blocked_metrics
    assert any(f.scope is BlockingScope.METRIC for f in verdict.findings)


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
