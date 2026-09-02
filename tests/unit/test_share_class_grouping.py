import pytest

from fip.services.data_service.grouping import (
    GroupingStatus,
    split_share_class_name,
)


@pytest.mark.parametrize(
    ("display_name", "product", "cls"),
    [
        ("易方达蓝筹精选混合A", "易方达蓝筹精选混合", "A"),
        ("易方达蓝筹精选混合C", "易方达蓝筹精选混合", "C"),
        ("招商中证白酒指数分级B", "招商中证白酒指数分级", "B"),
        ("兴全合润混合A类", "兴全合润混合", "A"),
    ],
)
def test_trailing_single_letter_is_a_share_class(display_name, product, cls):
    result = split_share_class_name(display_name)
    assert result.status is GroupingStatus.CONFIRMED
    assert result.product_name == product
    assert result.share_class_code == cls


@pytest.mark.parametrize(
    "display_name",
    [
        "华夏成长混合",              # 也许真是单类别产品，也许我们没识别出后缀
        "华夏成长混合(后端)",        # 实测：000021，是 000001 的后端收费份额
        "华夏大盘精选混合A(后端)",   # 实测：类别标记 A 内嵌在括号之前
        "嘉实增强信用定期债券",
    ],
)
def test_name_without_a_recognized_suffix_is_unconfirmed(display_name):
    """规则没识别出后缀 ≠ 确认没有后缀 —— 一律标记待人工确认。

    ⚠️ 本条替换了旧测试 test_name_without_suffix_is_a_single_class_product：
    旧测试断言「华夏成长混合」的 fallback 分支是 CONFIRMED，即把「我没识别
    出后缀」直接读成「我确认它没有后缀、是个单类别产品」。这两件事不是一
    回事，而这条测试把后者当规范锁住了。

    实测代价（fip_dev 的 15 fund / 20 share_class 真实交付数据）：

        fund  4  华夏成长混合             DEFAULT  CONFIRMED
        fund  5  华夏成长混合(后端)        DEFAULT  CONFIRMED  ← 000021，是 000001 的后端份额
        fund 11  华夏大盘精选混合    A             CONFIRMED
        fund 12  华夏大盘精选混合A(后端)   DEFAULT  CONFIRMED  ← 名字里直接嵌着 A

    同一只基金被拆成两个 Fund 产品，A/C 费率差异无处安放，Peer Group 里同
    一个组合被计两次 —— 而 grouping_status 全是 CONFIRMED，这个本该当逃生口
    的字段信息量为零（实测 15/15 CONFIRMED）。

    修复方向【不是】去猜「(后端)」该并到哪只基金（那是猜），而是如实报告
    「规则判不了」：份额类别仍各自单独成一个 fund（行为不变），但打上
    UNCONFIRMED，让人工确认有据可依（spec §4.5 / R-4）。
    """
    result = split_share_class_name(display_name)
    assert result.status is GroupingStatus.UNCONFIRMED
    assert result.product_name == display_name
    assert result.share_class_code == "DEFAULT"


def test_back_end_share_class_is_flagged_rather_than_silently_split():
    """两条真实数据的对照：不确定的那一半必须是可被人工发现的。

    我们【不】断言两者归到同一个 product_name —— 那需要「名称主干 + 管理人」
    的归组键与后缀词表，属 Plan-2。这里断言的是最低限度：不确定的那一条不
    能伪装成确定。
    """
    front = split_share_class_name("华夏成长混合")
    back = split_share_class_name("华夏成长混合(后端)")
    assert front.product_name != back.product_name  # 仍是两个 fund（行为不变）
    assert front.status is GroupingStatus.UNCONFIRMED
    assert back.status is GroupingStatus.UNCONFIRMED


@pytest.mark.parametrize(
    "display_name",
    [
        "广发纳斯达克100ETF",       # 结尾是 ETF，F 前还是大写字母
        "华宝油气LOF",              # 同上
        "易方达中概互联50ETF",
    ],
)
def test_ambiguous_trailing_letters_are_not_guessed(display_name):
    """不猜 —— 归组不确定的份额类别单独成一个 fund 并标记待确认。"""
    result = split_share_class_name(display_name)
    assert result.status is GroupingStatus.UNCONFIRMED
    assert result.product_name == display_name
    assert result.share_class_code == "DEFAULT"


def test_two_classes_of_the_same_product_share_a_product_name():
    """归组正确性的核心断言：同产品的两个类别必须落到同一个 product_name。"""
    a = split_share_class_name("易方达蓝筹精选混合A")
    c = split_share_class_name("易方达蓝筹精选混合C")
    assert a.product_name == c.product_name
    assert a.share_class_code != c.share_class_code


def test_empty_stem_is_unconfirmed():
    result = split_share_class_name("A")
    assert result.status is GroupingStatus.UNCONFIRMED


def test_whitespace_is_stripped():
    assert split_share_class_name("  华夏成长混合  ").product_name == "华夏成长混合"
