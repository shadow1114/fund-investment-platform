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
    LIMITED = "LIMITED"                # 有限额（限购）—— M1 的 derive_eligibility
                                        # 无法产生本值：subscription_open 是布尔，
                                        # 表达不了"限购但未关闭申购"这一档。它出现
                                        # 在外部 API 契约（10-api/02-fund-api.md）
                                        # 中，故保留取值而不删除；要产出它，需要在
                                        # 现有 open/closed 布尔之外新增一个配额/限购
                                        # 标志作为函数输入。
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

    已知缺口：本函数永远不会返回 EligibilityStatus.LIMITED（限购）。
    当前两个布尔输入只能表达"开放/关闭"，无法表达"限购但未关闭申购"
    这一档；要支持它，需要新增一个配额/限购标志作为第三个输入维度。
    该枚举值保留是因为它出现在外部 API 契约（10-api/02-fund-api.md）中，
    删除会与契约脱节 —— 这是一个已记录的已知空缺，不是被忽略的分支。
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
