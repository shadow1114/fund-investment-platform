"""中债通道的请求参数、序列键选择、时间戳换算与响应契约测试，无需联网。"""

import datetime as dt
import io

import httpx
import pandas as pd
import pytest

from fip.platform.source.port import SourceAdapter
from fip.services.data_service.adapters.chinabond import ChinaBondSourceAdapter
from fip.services.data_service.adapters.chinabond.client import ChinaBondContractError

FIXED_NOW = dt.datetime(2026, 11, 13, 8, tzinfo=dt.UTC)
CODE = "2c90818811afed8d0111c0c672b31578"
# 取自样例响应：北京时间 2006-11-20、2006-11-21 及 2026-11-12 零点。
BODY = {
    "QJZS_00": {"1163952000000": 99.8291, "1164038400000": 99.7602, "1794412800000": 87.5218},
    "name": "",
    "XQJSL_00": {"1163952000000": None, "1164038400000": 93.1053, "1794412800000": 15.33},
    "dqcName": {"00": "总值"},
    "dqcList": ["00"],
}


def _client(requests, body=None, status=200, text=None):
    def handler(request):
        requests.append(request)
        if text is not None:
            return httpx.Response(status, text=text)
        return httpx.Response(status, json=BODY if body is None else body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _fetch(body=None, **params):
    requests = []
    with _client(requests, body) as client:
        adapter = ChinaBondSourceAdapter(clock=lambda: FIXED_NOW, client=client)
        record = adapter.fetch(
            "index_daily",
            **{"code": CODE, "index_type": "QJZS", "period_type": "00", **params},
        )
    return adapter, record, requests


def _frame(record):
    return pd.read_parquet(io.BytesIO(record.payload))


def test_request_uses_external_params_and_fixed_sample_params():
    adapter, record, requests = _fetch()
    assert isinstance(adapter, SourceAdapter)
    assert adapter.provider_code == "CHINABOND"
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/cbweb-mn/indices/singleIndexQueryResult"
    assert dict(requests[0].url.params) == {
        "indexid": CODE, "qxlxt": "00", "zslxt": "QJZS",
        "ltcslx": "", "zslxt1": "", "lx": "1", "locale": "zh_CN",
    }
    assert record.request_params == {"code": CODE, "index_type": "QJZS", "period_type": "00"}
    assert record.published_at is None
    assert record.provider_available_at is None
    assert record.ingested_at == FIXED_NOW


def test_selects_index_type_period_key_and_converts_beijing_dates():
    _, record, _ = _fetch()
    frame = _frame(record)
    assert list(frame.columns) == ["date", "value"]
    assert list(frame["date"]) == [
        dt.date(2006, 11, 20), dt.date(2006, 11, 21), dt.date(2026, 11, 12),
    ]
    assert list(frame["value"]) == [99.8291, 99.7602, 87.5218]
    assert record.row_count == 3


def test_other_key_is_selected_and_null_values_are_kept():
    _, record, requests = _fetch(index_type="XQJSL")
    frame = _frame(record)
    assert dict(requests[0].url.params)["zslxt"] == "XQJSL"
    assert pd.isna(frame["value"].iloc[0])
    assert list(frame["value"].iloc[1:]) == [93.1053, 15.33]


def test_rows_are_sorted_by_date():
    body = {"QJZS_00": {"1164038400000": 2.0, "1163952000000": 1.0}}
    frame = _frame(_fetch(body)[1])
    assert list(frame["value"]) == [1.0, 2.0]


def test_empty_series_keeps_columns():
    _, record, _ = _fetch({"QJZS_00": {}})
    frame = _frame(record)
    assert list(frame.columns) == ["date", "value"]
    assert record.row_count == 0


@pytest.mark.parametrize("params", [
    {"code": ""}, {"code": "2c90-8188"}, {"index_type": ""}, {"period_type": ""},
    {"period_type": "0/0"}, {"startDate": "20260101"},
])
def test_invalid_params_are_rejected_before_request(params):
    requests = []
    with _client(requests) as client, pytest.raises(ValueError):
        ChinaBondSourceAdapter(client=client).fetch(
            "index_daily",
            **{"code": CODE, "index_type": "QJZS", "period_type": "00", **params},
        )
    assert requests == []


def test_unknown_dataset_is_rejected():
    with pytest.raises(KeyError):
        ChinaBondSourceAdapter().fetch("unknown")


@pytest.mark.parametrize("body", [
    {"CFZS_00": {"1163952000000": 1.0}},
    {"QJZS_00": [1.0]},
    {"QJZS_00": {"1163952000001": 1.0}},
    {"QJZS_00": {"abc": 1.0}},
    {"QJZS_00": {"1163952000000": "99.8"}},
    {"QJZS_00": {"1163952000000": True}},
    [],
])
def test_contract_violations_raise(body):
    with pytest.raises(ChinaBondContractError):
        _fetch(body)


def test_invalid_json_raises_contract_error():
    requests = []
    with _client(requests, text="<html>error</html>") as client, pytest.raises(
        ChinaBondContractError
    ):
        ChinaBondSourceAdapter(client=client).fetch(
            "index_daily", code=CODE, index_type="QJZS", period_type="00"
        )


def test_http_error_is_raised():
    requests = []
    with _client(requests, status=503) as client, pytest.raises(httpx.HTTPStatusError):
        ChinaBondSourceAdapter(client=client).fetch(
            "index_daily", code=CODE, index_type="QJZS", period_type="00"
        )
