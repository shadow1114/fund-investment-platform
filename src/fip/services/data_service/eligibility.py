from enum import StrEnum


class LifecycleStatus(StrEnum):
    """基金处于什么状态 —— 描述性事实。"""

    NORMAL = "NORMAL"
    SUSPENDED_SUBSCRIPTION = "SUSPENDED_SUBSCRIPTION"
    LIQUIDATED = "LIQUIDATED"
    MERGED = "MERGED"
    TRANSFORMED = "TRANSFORMED"


class EligibilityStatus(StrEnum):
    """在 decision_at 时点该基金能否被建仓 / 加仓 / 减仓。"""

    FULLY_ELIGIBLE = "FULLY_ELIGIBLE"  # 可建仓、可加仓、可减仓
    HOLD_ONLY = "HOLD_ONLY"            # 可持有、可加仓，不可减仓
    LIMITED = "LIMITED"                # 有限额
    EXIT_ONLY = "EXIT_ONLY"            # 仅可减仓
    NOT_TRADABLE = "NOT_TRADABLE"      # 不可交易


_TERMINATED = {LifecycleStatus.LIQUIDATED, LifecycleStatus.MERGED}


def derive_eligibility(
    lifecycle: LifecycleStatus,
    subscription_open: bool,
    redemption_open: bool,
) -> EligibilityStatus:
    """由生命周期状态与申赎标志派生可投资性。

    Investment Eligibility 是【客观事实】，不含任何策略判断，因此归
    data-service。它是 Eligibility Rules（策略规则，归 fund-service）
    的输入之一，不是它的同义词（01-system-architecture §6.5）。

    它必须与 Fund Lifecycle Status 分离：『暂停申购』意味着不可加仓但
    仍可持有与减仓，用单一生命周期状态无法表达。回测判断某基金当时能否
    买入，依据的是本函数的产出，不是 Lifecycle Status。
    """
    if lifecycle in _TERMINATED:
        return EligibilityStatus.NOT_TRADABLE
    if subscription_open and redemption_open:
        return EligibilityStatus.FULLY_ELIGIBLE
    if subscription_open and not redemption_open:
        return EligibilityStatus.HOLD_ONLY
    if not subscription_open and redemption_open:
        return EligibilityStatus.EXIT_ONLY
    return EligibilityStatus.NOT_TRADABLE
