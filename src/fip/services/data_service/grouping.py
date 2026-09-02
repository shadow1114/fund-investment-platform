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
    本规则只处理最明确的一种情形：结尾单个大写字母 → CONFIRMED。

    其余一切形状都是 UNCONFIRMED：份额类别各自单独成一个 fund（行为与
    CONFIRMED 的单类别产品相同），但如实标记「规则判不了，待人工确认」。

    ── 为什么「没识别出后缀」必须是 UNCONFIRMED（fix round 4）──

    此前 fallback 分支返回 CONFIRMED，等于把「我没识别出后缀」读成「我确认
    它没有后缀，是个单类别产品」。这两件事完全不同，而 grouping_status 存在
    的唯一意义就是区分它们。实测代价（fip_dev 的真实交付数据，15 fund /
    20 share_class）：

        华夏成长混合            DEFAULT  CONFIRMED
        华夏成长混合(后端)       DEFAULT  CONFIRMED  ← 000021，是 000001 的后端份额
        华夏大盘精选混合  A              CONFIRMED
        华夏大盘精选混合A(后端)  DEFAULT  CONFIRMED  ← 名字里直接嵌着 A

    同一只基金被拆成两个 Fund，A/C 费率差异无处安放，Peer Group 里同一个
    组合被计两次 —— 而 15/15 全是 CONFIRMED，逃生口的信息量为零。

    【不猜】的边界：本函数【不】去猜「(后端)」「A(后端)」该并到哪只基金，
    也不去剥括号 —— 那是猜，猜错的后果是两只不相干的基金共用 Peer Group
    与评分口径。它只如实报告不确定性（spec §4.5 / R-4）。

    ── 对 spec §4.5 的收窄（如实登记，本轮不实现）──

    spec §4.5 的归组键是「名称主干 + 管理人」。本实现只用了名称主干：
    fund.fund_management_company 建了表，但灌数链路从不写入，AKShare 的基金
    列表接口也不提供管理人字段。因此两家公司若各有一只同名产品，本规则会把
    它们并成一个 product_name 而不自知。补上管理人维度属 Plan-2 的范围
    （需要一个能提供管理人的数据源，不是这里多写一个 split）。
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

    # 走到这里的两类名字（结尾是多个大写字母的 ETF/LOF/QDII，以及一切
    # 不以大写字母结尾的名字）在【结果上】完全一致：单独成一个 fund，
    # 标记 UNCONFIRMED。因此不再分两个分支写。
    #
    # 特别地，「华夏成长混合(后端)」「华夏大盘精选混合A(后端)」这类带括号
    # 或内嵌类别标记的名字落在这里：正则识别不出后缀，我们就说识别不出，
    # 而不是宣布它没有后缀。
    return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)
