import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.parse import parse_nav_frame


def _payload(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


def test_parses_dates_and_decimals():
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-02", "2020-01-03"],
        "单位净值": ["1.0000", "1.0123"],
    }))
    rows = parse_nav_frame(payload)
    assert rows[0].effective_at == dt.date(2020, 1, 2)
    assert rows[0].unit_nav == Decimal("1.0000")
    assert rows[1].unit_nav == Decimal("1.0123")


def test_values_are_decimal_not_float():
    """金融数值禁止浮点 —— float 会在累乘复权时引入不可控误差。"""
    payload = _payload(pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0001"]}))
    assert isinstance(parse_nav_frame(payload)[0].unit_nav, Decimal)


def test_rows_are_sorted_ascending():
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-03", "2020-01-02"],
        "单位净值": ["1.0123", "1.0000"],
    }))
    rows = parse_nav_frame(payload)
    assert [r.effective_at for r in rows] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_missing_nav_is_dropped_not_filled():
    """C-6：缺失不得转 0、不得前向填充。缺失就是缺失。"""
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-02", "2020-01-03"],
        "单位净值": ["1.0000", None],
    }))
    rows = parse_nav_frame(payload)
    assert len(rows) == 1
    assert rows[0].effective_at == dt.date(2020, 1, 2)


def test_duplicate_dates_are_rejected():
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-02", "2020-01-02"],
        "单位净值": ["1.0000", "1.0100"],
    }))
    with pytest.raises(ValueError, match="重复"):
        parse_nav_frame(payload)


def test_non_positive_nav_is_rejected():
    payload = _payload(pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["0"]}))
    with pytest.raises(ValueError, match="净值"):
        parse_nav_frame(payload)
