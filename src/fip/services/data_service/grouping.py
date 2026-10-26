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
    """Extract a share-class candidate; names alone never confirm product identity."""
    name = display_name.strip()
    if not name:
        return GroupingResult("", DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    match = _SUFFIX.match(name)
    if match:
        stem = match.group("stem").strip()
        if stem:
            return GroupingResult(stem, match.group("cls"), GroupingStatus.UNCONFIRMED)
        # 防御性分支：理论上不可达。_SUFFIX 的 stem 组从 name 的下标 0 开始，
        # 而 name 已经过上面的 display_name.strip()，下标 0 处必是非空白字符，
        # 因此 stem 至少含一个非空白字符，.strip() 后不可能为空。保留该分支
        # 是为了防止未来有人修改上面的正则或去掉顶层 strip() 后，在没有
        # 单元测试兜底的情况下把空 stem 错误地当作 CONFIRMED 产品名返回。
        return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    # 走到这里的两类名字（结尾是多个大写字母的 ETF/LOF/QDII，以及一切
    # 不以大写字母结尾的名字）在【结果上】完全一致：单独成一个 fund，
    # 标记 UNCONFIRMED。因此不再分两个分支写。
    #
    # 特别地，「华夏成长混合(后端)」「华夏大盘精选混合A(后端)」这类带括号
    # 或内嵌类别标记的名字落在这里：正则识别不出后缀，我们就说识别不出，
    # 而不是宣布它没有后缀。
    return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)
