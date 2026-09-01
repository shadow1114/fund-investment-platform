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


def test_name_without_suffix_is_a_single_class_product():
    result = split_share_class_name("华夏成长混合")
    assert result.status is GroupingStatus.CONFIRMED
    assert result.product_name == "华夏成长混合"
    assert result.share_class_code == "DEFAULT"


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
