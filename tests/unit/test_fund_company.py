import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.platform.source.port import SourceRecord
from fip.services.data_service.company import (
    fund_company_from_fields,
    fund_detail_from_record,
    parse_fund_aum,
    parse_fund_fee_rate,
    raw_fund_company_from_record,
)
from fip.services.data_service.ingest import _asset_type


@pytest.mark.parametrize("value", [None, "", "  ", "NaN", "nan", "<NA>"])
def test_fund_company_ignores_missing_blank_and_nan_values(value):
    assert fund_company_from_fields({}, {"基金公司": value}) is None


def test_fund_company_uses_fund_company_and_never_management_person_or_manager():
    assert (
        fund_company_from_fields(
            {},
            {
                "基金公司": " 华夏基金 ",
                "基金管理人": "王经理",
                "基金经理": "张经理",
            },
        )
        == "华夏基金"
    )
    assert fund_company_from_fields({}, {"基金管理人": "王经理"}) is None
    assert fund_company_from_fields({}, {"基金经理": "张经理"}) is None


def test_normalized_company_field_takes_precedence_over_raw_company_value():
    assert (
        fund_company_from_fields({"fund_company": "规范公司"}, {"基金公司": "旧名称"}) == "规范公司"
    )


def test_fund_company_overflow_is_an_explicit_data_error():
    with pytest.raises(ValueError, match="exceeds 128 characters"):
        fund_company_from_fields({}, {"基金公司": "公司" * 65})


def _detail_record(rows, *, symbol="000001", dataset="fund_detail_xq"):
    buffer = io.BytesIO()
    pd.DataFrame(rows, columns=["item", "value"]).to_parquet(buffer, index=False)
    return SourceRecord(
        dataset=dataset,
        payload=buffer.getvalue(),
        row_count=len(rows),
        ingested_at=dt.datetime(2026, 11, 4, tzinfo=dt.UTC),
        request_params={"symbol": symbol},
    )


def test_detail_source_extracts_only_company_and_keeps_its_raw_value():
    record = _detail_record(
        [
            ("基金代码", "000001"),
            ("基金公司", " 华夏基金 "),
            ("基金经理", "经理姓名"),
        ]
    )
    assert raw_fund_company_from_record(record, symbol="000001") == " 华夏基金 "


def test_detail_source_rejects_a_fund_company_for_another_fund():
    record = _detail_record([("基金代码", "000002"), ("基金公司", "易方达基金")])
    with pytest.raises(ValueError, match="fund code does not match"):
        raw_fund_company_from_record(record, symbol="000001")


def test_detail_source_rejects_duplicate_company_fields():
    record = _detail_record(
        [
            ("基金代码", "000001"),
            ("基金公司", "华夏基金"),
            ("基金公司", "易方达基金"),
        ]
    )
    with pytest.raises(ValueError, match="duplicate company"):
        raw_fund_company_from_record(record, symbol="000001")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("29.19亿", Decimal("2919000000.00")),
        ("29.19亿元（截止至：2026年09月30日）", Decimal("2919000000.00")),
        ("2177.53万", Decimal("21775300.00")),
        ("1,234.5", Decimal("1234.50")),
        ("1234.5元", Decimal("1234.50")),
        ("--", None),
        ("", None),
        (None, None),
        ("未知", None),
    ],
)
def test_parse_fund_aum_returns_plain_yuan(value, expected):
    assert parse_fund_aum(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.20%（每年）", Decimal("0.01200000")),
        ("0.20%", Decimal("0.00200000")),
        ("0.00%（每年）", Decimal("0.00000000")),
        ("---（每年）", None),
        ("1.20（每年）", None),
        (None, None),
    ],
)
def test_parse_fund_fee_rate_returns_decimal_ratio(value, expected):
    assert parse_fund_fee_rate(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("混合型-灵活", "混合型"),
        ("债券型-混合二级", "债券型"),
        ("QDII", "QDII"),
        ("", None),
        (None, None),
    ],
)
def test_asset_type_keeps_part_before_dash(value, expected):
    assert _asset_type(value) == expected


def test_fund_detail_extracts_company_manager_and_aum():
    frame = pd.DataFrame(
        {
            "item": ["基金代码", "最新规模", "基金公司", "基金经理"],
            "value": ["000001", "29.19亿", "华夏基金管理有限公司", "刘睿聪 郑晓辉"],
        }
    )
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    record = SourceRecord(
        dataset="fund_detail_xq",
        payload=buffer.getvalue(),
        row_count=len(frame),
        ingested_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        request_params={"symbol": "000001"},
    )
    detail = fund_detail_from_record(record, symbol="000001")
    assert detail.fund_company == "华夏基金管理有限公司"
    assert detail.fund_manager == "刘睿聪 郑晓辉"
    assert detail.fund_aum == Decimal("2919000000.00")
