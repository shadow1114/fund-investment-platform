"""D-22：`derive_eligibility` 的两个分支与上游语义互换（Plan-1 代码 bug）。

上游三处文档【完全一致】（05-fund-selection.md:217-223 =
02-business-requirements.md §18.2 = 03-data/02-data-domain-model.md:400-406）：

    HOLD_ONLY      暂停申购          可持有 ✓  可加仓 ✗  可减仓 ✓
    NOT_TRADABLE   已清盘 / 暂停赎回  —        ✗        ✗
    EXIT_ONLY      即将清盘 / 转型    ✓        ✗        ✓

而 Plan-1 的实现把两个分支反了，连同 EligibilityStatus 的两行行内注释也反了。
Plan-1 里它没有消费方，错了不显形；Task 16 一旦按 §9.3 消费它：暂停申购
（常见、良性、期满即恢复）被判 EXIT_ONLY → 不入池；暂停赎回（真正不可交易）
被判 HOLD_ONLY → 入池并标注约束。该排除的进了池、不该排除的被赶了出去，
而全部条件结果照常落库，没有一条测试会红。
"""

from fip.services.data_service.eligibility import (
    EligibilityStatus,
    LifecycleStatus,
    derive_eligibility,
)


def test_suspended_redemption_is_not_tradable():
    """暂停赎回 = 钱出不来 = 不可交易。上游三处文档一致。"""
    assert derive_eligibility(LifecycleStatus.NORMAL, True, False) \
        is EligibilityStatus.NOT_TRADABLE


def test_suspended_subscription_is_hold_only():
    """暂停申购 = 不可加仓，但可持有、可减仓。这是常见且良性的状态。"""
    assert derive_eligibility(LifecycleStatus.NORMAL, False, True) \
        is EligibilityStatus.HOLD_ONLY


def test_exit_only_is_never_derived_from_the_two_booleans():
    """EXIT_ONLY 是【生命周期】条件（即将清盘/转型），不是申赎标志的函数。

    穷举 lifecycle × subscription_open × redemption_open 的全部组合，
    断言 EXIT_ONLY 一次都不出现 —— 与既有的 LIMITED 缺口同类，
    把「本函数永不产出它」钉成机器可判定的事实而不是 docstring 里的一句话。
    """
    for lc in LifecycleStatus:
        for sub in (True, False):
            for red in (True, False):
                assert derive_eligibility(lc, sub, red) is not EligibilityStatus.EXIT_ONLY


def test_the_exhaustive_scan_actually_covers_every_combination():
    """守卫：LifecycleStatus 若哪天变成空枚举，上面那条循环会一次都不执行。

    「遍历全部组合」类断言的经典恒真形状 —— 先钉住组合数确实非零。
    """
    combos = [
        (lc, sub, red)
        for lc in LifecycleStatus
        for sub in (True, False)
        for red in (True, False)
    ]
    assert len(combos) == len(LifecycleStatus) * 4
    assert len(combos) >= 20


def test_limited_is_also_never_derived():
    """已登记缺口一：LIMITED 同样永不产出（两个布尔表达不了「限购」这一档）。"""
    for lc in LifecycleStatus:
        for sub in (True, False):
            for red in (True, False):
                assert derive_eligibility(lc, sub, red) is not EligibilityStatus.LIMITED
