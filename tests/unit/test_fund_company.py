import datetime as dt
import io

import pandas as pd
import pytest

from fip.platform.source.port import SourceRecord
from fip.services.data_service.company import (
    company_name_from_fields,
    raw_fund_company_from_record,
)


@pytest.mark.parametrize("value", [None, "", "  ", "NaN", "nan", "<NA>"])
def test_company_name_ignores_missing_blank_and_nan_values(value):
    assert company_name_from_fields({}, {"基金公司": value}) is None


def test_company_name_uses_fund_company_and_never_management_person_or_manager():
    assert (
        company_name_from_fields(
            {},
            {
                "基金公司": " 华夏基金 ",
                "基金管理人": "王经理",
                "基金经理": "张经理",
            },
        )
        == "华夏基金"
    )
    assert company_name_from_fields({}, {"基金管理人": "王经理"}) is None
    assert company_name_from_fields({}, {"基金经理": "张经理"}) is None


def test_normalized_company_field_takes_precedence_over_raw_company_value():
    assert (
        company_name_from_fields({"company_name": "规范公司"}, {"基金公司": "旧名称"}) == "规范公司"
    )


def test_company_name_overflow_is_an_explicit_data_error():
    with pytest.raises(ValueError, match="exceeds 128 characters"):
        company_name_from_fields({}, {"基金公司": "公司" * 65})


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


def test_detail_source_rejects_a_company_name_for_another_fund():
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
