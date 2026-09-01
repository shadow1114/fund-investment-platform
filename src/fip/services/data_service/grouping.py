import re
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_SHARE_CLASS = "DEFAULT"

# 结尾的单个大写字母（可带「类」或「份额」），且该字母前不是另一个大写字母。
# 前置的负向断言把 ETF / LOF / QDII 这类缩写排除在外。
_SUFFIX = re.compile(r"^(?P<stem>.*[^A-Z])(?P<cls>[A-Z])(?:类)?(?:份额)?$")


class GroupingStatus(StrEnum):
    CONFIRMED = "CONFIRMED"      # 规则可判定
    UNCONFIRMED = "UNCONFIRMED"  # 规则无法判定，待人工确认


@dataclass(frozen=True, slots=True)
class GroupingResult:
    product_name: str
    share_class_code: str
    status: GroupingStatus


def split_share_class_name(display_name: str) -> GroupingResult:
    """把 AKShare 的基金简称拆为「产品名 + 份额类别」。

    AKShare 的 6 位代码是份额类别而非产品（03-erd §5.2），需要一条归组规则。
    本规则只处理最明确的一种情形：结尾单个大写字母。

    【不猜】：ETF / LOF / QDII 等以多个大写字母结尾的名称一律标记
    UNCONFIRMED，各自单独成一个 fund，而不是强行合并（spec R-4）。
    强行合并的后果是两只不相干的基金共用 Peer Group 与评分口径。
    """
    name = display_name.strip()
    if not name:
        return GroupingResult("", DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    match = _SUFFIX.match(name)
    if match:
        stem = match.group("stem").strip()
        if stem:
            return GroupingResult(stem, match.group("cls"), GroupingStatus.CONFIRMED)
        # 防御性分支：理论上不可达。_SUFFIX 的 stem 组从 name 的下标 0 开始，
        # 而 name 已经过上面的 display_name.strip()，下标 0 处必是非空白字符，
        # 因此 stem 至少含一个非空白字符，.strip() 后不可能为空。保留该分支
        # 是为了防止未来有人修改上面的正则或去掉顶层 strip() 后，在没有
        # 单元测试兜底的情况下把空 stem 错误地当作 CONFIRMED 产品名返回。
        return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    if name[-1].isupper() and name[-1].isascii():
        # 结尾是大写字母但不匹配上面的模式 —— 说明前面还有大写字母（ETF/LOF）
        return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.CONFIRMED)
