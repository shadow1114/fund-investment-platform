import pytest

from fip.services.data_service.eligibility import (
    EligibilityStatus,
    LifecycleStatus,
    derive_eligibility,
)


def test_normal_and_open_is_fully_eligible():
    assert derive_eligibility(LifecycleStatus.NORMAL, True, True) \
        is EligibilityStatus.FULLY_ELIGIBLE


def test_suspended_subscription_can_still_be_held_and_sold():
    """『暂停申购』意味着不可加仓但仍可持有与减仓。

    用单一生命周期状态无法表达这一点 —— 这正是 Investment Eligibility
    必须与 Fund Lifecycle Status 分离的原因（上游术语表）。
    """
    assert derive_eligibility(LifecycleStatus.SUSPENDED_SUBSCRIPTION, False, True) \
        is EligibilityStatus.EXIT_ONLY


def test_open_subscription_with_closed_redemption_is_hold_only():
    assert derive_eligibility(LifecycleStatus.NORMAL, True, False) \
        is EligibilityStatus.HOLD_ONLY


def test_both_closed_is_not_tradable():
    assert derive_eligibility(LifecycleStatus.NORMAL, False, False) \
        is EligibilityStatus.NOT_TRADABLE


@pytest.mark.parametrize(
    "lifecycle",
    [LifecycleStatus.LIQUIDATED, LifecycleStatus.MERGED],
)
def test_terminated_funds_are_never_tradable(lifecycle):
    """清盘或合并的基金，无论申赎标志如何都不可交易。"""
    assert derive_eligibility(lifecycle, True, True) is EligibilityStatus.NOT_TRADABLE


def test_transformed_fund_follows_its_subscription_flags():
    """转型不等于终止 —— 转型后基金仍可交易，分类会变。"""
    assert derive_eligibility(LifecycleStatus.TRANSFORMED, True, True) \
        is EligibilityStatus.FULLY_ELIGIBLE
