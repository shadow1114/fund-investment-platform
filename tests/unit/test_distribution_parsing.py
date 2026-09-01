import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.parse import (
    parse_distribution_frame,
    parse_split_frame,
)


def _payload(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


def test_dividend_uses_ex_date_not_record_date():
    """复权按【除息日】计算 —— 权益登记日不是净值下跌的那一天。"""
    payload = _payload(pd.DataFrame({
        "年份": ["2020"],
        "权益登记日": ["2020-06-10"],
        "除息日": ["2020-06-11"],
        "每10份分红": ["每10份派现金1.0000元"],
    }))
    rows = parse_distribution_frame(payload)
    assert rows[0].effective_at == dt.date(2020, 6, 11)
    assert rows[0].dividend_per_unit == Decimal("0.1")   # 1.0000 / 10
    assert rows[0].split_ratio == Decimal(1)


def test_dividend_is_divided_by_the_stated_base():
    """⚠️ 最关键的一条：列名里的基数必须被除掉。

    漏掉除以 10，每笔分红放大 10 倍，复权净值系统性高估且不报错。
    """
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "权益登记日": ["2021-12-31"], "除息日": ["2021-12-31"],
        "每10份分红": ["每10份派现金0.4500元"],
    }))
    assert parse_distribution_frame(payload)[0].dividend_per_unit == Decimal("0.045")


def test_unparseable_dividend_text_is_dropped_not_guessed():
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "权益登记日": ["2021-12-31"], "除息日": ["2021-12-31"],
        "每10份分红": ["暂无数据"],
    }))
    assert parse_distribution_frame(payload) == []


def test_dividend_amount_is_decimal():
    payload = _payload(pd.DataFrame({
        "年份": ["2020"], "权益登记日": ["2020-06-10"],
        "除息日": ["2020-06-11"], "每10份分红": ["每10份派现金1.0000元"],
    }))
    assert isinstance(parse_distribution_frame(payload)[0].dividend_per_unit, Decimal)


def test_negative_dividend_is_rejected():
    payload = _payload(pd.DataFrame({
        "年份": ["2020"], "权益登记日": ["2020-06-10"],
        "除息日": ["2020-06-11"], "每10份分红": ["每10份派现金-0.1元"],
    }))
    with pytest.raises(ValueError, match="分红"):
        parse_distribution_frame(payload)


def test_rows_without_ex_date_are_dropped():
    payload = _payload(pd.DataFrame({
        "年份": ["2020"], "权益登记日": ["2020-06-10"],
        "除息日": [None], "每10份分红": ["每10份派现金1.0000元"],
    }))
    assert parse_distribution_frame(payload) == []


def test_split_ratio_is_parsed():
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "拆分折算日": ["2021-03-15"], "拆分折算比例": ["2.0000"],
    }))
    rows = parse_split_frame(payload)
    assert rows[0].effective_at == dt.date(2021, 3, 15)
    assert rows[0].split_ratio == Decimal("2.0000")
    assert rows[0].dividend_per_unit == Decimal(0)


def test_split_ratio_expressed_as_colon_pair_is_parsed():
    """AKShare 的拆分比例有时是 '1:2' 形式。"""
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "拆分折算日": ["2021-03-15"], "拆分折算比例": ["1:2"],
    }))
    assert parse_split_frame(payload)[0].split_ratio == Decimal(2)


def test_non_positive_split_ratio_is_rejected():
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "拆分折算日": ["2021-03-15"], "拆分折算比例": ["0"],
    }))
    with pytest.raises(ValueError, match="拆分"):
        parse_split_frame(payload)


def test_dividend_amount_is_anchored_to_cash_not_to_the_first_digit_after_base():
    """⚠️ fix round 1：分红金额必须锚定到「现金」，不能是「份」后第一个数。

    『每10份转增2股派现金0.30元』同时携带转增股数与现金分红。若分隔符
    不受限地匹配任意非数字字符，`amount` 组会先撞上「转增2股」里的 2，
    把 0.30 元误解析成 2（放大约 6.7 倍），且不报错——与漏除以 10 是
    同一类静默灾难，只是错在锚点而不是除法。
    """
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "权益登记日": ["2021-06-01"], "除息日": ["2021-06-02"],
        "每10份分红": ["每10份转增2股派现金0.30元"],
    }))
    assert parse_distribution_frame(payload)[0].dividend_per_unit == Decimal("0.03")


def test_dividend_plain_cash_only_form_still_parses_after_anchoring():
    """锚定改动不能破坏最常见的纯现金分红形状（Task 10 探查实测的唯一形状）。"""
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "权益登记日": ["2021-12-31"], "除息日": ["2021-12-31"],
        "每10份分红": ["每10份派现金0.4500元"],
    }))
    assert parse_distribution_frame(payload)[0].dividend_per_unit == Decimal("0.045")


def test_dividend_text_without_a_stated_base_is_dropped_not_guessed():
    """『每份派现金0.5元』没有基数数字——按丢弃而非猜测的既定策略处理。"""
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "权益登记日": ["2021-06-01"], "除息日": ["2021-06-02"],
        "每10份分红": ["每份派现金0.5元"],
    }))
    assert parse_distribution_frame(payload) == []


def test_split_ratio_with_zero_base_colon_pair_is_rejected():
    """'0:2' 的分母为 0：这是脏数据，不是缺失记录，必须报错而不是被静默丢弃。"""
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "拆分折算日": ["2021-03-15"], "拆分折算比例": ["0:2"],
    }))
    with pytest.raises(ValueError, match="拆分"):
        parse_split_frame(payload)
