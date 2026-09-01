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
