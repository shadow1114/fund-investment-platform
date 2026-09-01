import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.parse import parse_yield_curve_frame


def _payload(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


def test_wide_frame_is_melted_into_tenor_rows():
    """中债曲线是宽表（每个期限一列），需展开为 (日期, 期限, 利率) 行。"""
    payload = _payload(pd.DataFrame({
        "日期": ["2024-01-02", "2024-01-03"],
        "3月": [2.10, 2.12],
        "1年": [2.30, 2.31],
        "10年": [2.60, 2.62],
    }))
    rows = parse_yield_curve_frame(payload)
    assert len(rows) == 6
    one_year = [r for r in rows if r.tenor == "1Y"]
    assert [r.effective_at for r in one_year] == [dt.date(2024, 1, 2), dt.date(2024, 1, 3)]


def test_percentage_is_converted_to_decimal_fraction():
    """全平台百分比一律用小数（10-api §12.1）。2.30% → 0.023。"""
    payload = _payload(pd.DataFrame({"日期": ["2024-01-02"], "1年": [2.30]}))
    row = parse_yield_curve_frame(payload)[0]
    assert row.rate == Decimal("0.02300000")
    assert isinstance(row.rate, Decimal)


@pytest.mark.parametrize(
    ("column", "tenor"),
    [("3月", "3M"), ("6月", "6M"), ("1年", "1Y"), ("3年", "3Y"), ("10年", "10Y")],
)
def test_chinese_tenor_labels_are_normalized(column, tenor):
    payload = _payload(pd.DataFrame({"日期": ["2024-01-02"], column: [2.0]}))
    assert parse_yield_curve_frame(payload)[0].tenor == tenor


def test_unrecognized_tenor_columns_are_skipped():
    """无法识别的列直接跳过，不猜测其含义。"""
    payload = _payload(pd.DataFrame({
        "日期": ["2024-01-02"], "1年": [2.30], "曲线名称": ["中债国债收益率曲线"],
    }))
    rows = parse_yield_curve_frame(payload)
    assert [r.tenor for r in rows] == ["1Y"]


def test_missing_rate_is_dropped_not_filled():
    payload = _payload(pd.DataFrame({"日期": ["2024-01-02"], "1年": [None]}))
    assert parse_yield_curve_frame(payload) == []
