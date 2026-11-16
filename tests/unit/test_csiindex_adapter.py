"""中证通道的日期校正、响应契约和时间来源测试，无需联网。"""

import datetime as dt
import io

import httpx
import pandas as pd
import pytest

from fip.platform.source.port import SourceAdapter
from fip.services.data_service.adapters.csiindex import CsiIndexSourceAdapter
from fip.services.data_service.adapters.csiindex.client import CsiIndexContractError

FIXED_NOW = dt.datetime(2026, 11, 11, 8, tzinfo=dt.UTC)
BASIC = {"indexCode": "930901", "basicDate": "2012-12-31", "publishDate": "2016-10-18"}
ROW = {
    "tradeDate": "20261104", "indexCode": "930901",
    "indexNameCnAll": "中证动漫游戏指数", "indexNameCn": "动漫游戏",
    "indexNameEnAll": "CSI Anime Comic & Game Index", "indexNameEn": "ACG Index",
    "open": 1523.51, "high": 1563.68, "low": 1519.51, "close": 1558.12,
    "change": 31.34, "changePct": 2.05, "tradingVol": 1794382825,
    "tradingValue": 187.96, "consNumber": 28, "peg": 17.46,
}


def _body(data):
    return {"code": "200", "msg": "Success", "success": True, "data": data}


def _client(requests, *, basic=None, perf=None, status=200):
    def handler(request):
        requests.append(request)
        if "index-basic-info" in request.url.path:
            return httpx.Response(status, json=_body(BASIC) if basic is None else basic)
        return httpx.Response(status, json=_body([ROW]) if perf is None else perf)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("start", "expected"),
    [(None, "20121231"), ("", "20121231"), ("20120101", "20121231"),
     ("20121231", "20121231"), ("20130104", "20130104")],
)
def test_start_date_is_clamped_to_basic_date(start, expected):
    requests = []
    with _client(requests) as client:
        adapter = CsiIndexSourceAdapter(clock=lambda: FIXED_NOW, client=client)
        params = {"indexCode": "930901", "endDate": "20261110"}
        if start is not None:
            params["startDate"] = start
        record = adapter.fetch("index_daily", **params)
    assert isinstance(adapter, SourceAdapter)
    assert adapter.provider_code == "CSIINDEX"
    assert len(requests) == 2
    assert requests[0].url.path.endswith("index-basic-info/930901")
    assert requests[1].url.path.endswith("perf/index-perf")
    assert dict(requests[1].url.params) == {
        "indexCode": "930901", "startDate": expected, "endDate": "20261110",
    }
    assert record.request_params == dict(requests[1].url.params)
    assert record.dataset == "index_daily"
    assert record.row_count == 1
    assert record.ingested_at == FIXED_NOW
    assert record.published_at is None
    assert record.provider_available_at is None
    pd.testing.assert_frame_equal(pd.read_parquet(io.BytesIO(record.payload)), pd.DataFrame([ROW]))


@pytest.mark.parametrize("params", [
    {"indexCode": "../930901", "endDate": "20261110"},
    {"indexCode": "930901", "endDate": "2026-11-10"},
    {"indexCode": "930901", "endDate": "20260230"},
    {"indexCode": "930901", "endDate": "20261110", "startDate": "20261111"},
    {"indexCode": "930901", "endDate": "20261110", "startCode": "20130104"},
    {"indexCode": "930901"},
])
def test_invalid_params_fail_before_network(params):
    requests = []
    with _client(requests) as client:
        with pytest.raises(ValueError):
            CsiIndexSourceAdapter(client=client).fetch("index_daily", **params)
    assert not requests


def test_unknown_dataset_fails_before_network():
    requests = []
    with _client(requests) as client:
        with pytest.raises(KeyError):
            CsiIndexSourceAdapter(client=client).fetch("unknown")
    assert not requests


@pytest.mark.parametrize("basic", [
    _body({"indexCode": "000300", "basicDate": "2012-12-31"}),
    _body({"indexCode": "930901"}),
    _body({"indexCode": "930901", "basicDate": "2012-02-30"}),
    _body(None),
    {"code": "500", "success": False, "msg": "失败"},
])
def test_invalid_basic_info_prevents_history_request(basic):
    requests = []
    with _client(requests, basic=basic) as client:
        with pytest.raises(CsiIndexContractError):
            CsiIndexSourceAdapter(client=client).fetch(
                "index_daily", indexCode="930901", endDate="20261110",
            )
    assert len(requests) == 1


def test_end_before_basic_date_prevents_history_request():
    requests = []
    with _client(requests) as client:
        with pytest.raises(ValueError, match="basicDate"):
            CsiIndexSourceAdapter(client=client).fetch(
                "index_daily", indexCode="930901", endDate="20120101",
            )
    assert len(requests) == 1


@pytest.mark.parametrize("data", [
    None, {}, [None], [{k: v for k, v in ROW.items() if k != "close"}],
    [{**ROW, "indexCode": "000300"}], [{**ROW, "tradeDate": "20261111"}],
    [{**ROW, "tradeDate": "20260230"}],
])
def test_invalid_history_raises_contract_error(data):
    with _client([], perf=_body(data)) as client:
        with pytest.raises(CsiIndexContractError):
            CsiIndexSourceAdapter(client=client).fetch(
                "index_daily", indexCode="930901", endDate="20261110",
            )


def test_empty_history_is_valid():
    with _client([], perf=_body([])) as client:
        record = CsiIndexSourceAdapter(client=client).fetch(
            "index_daily", indexCode="930901", endDate="20261110",
        )
    assert record.row_count == 0
    assert pd.read_parquet(io.BytesIO(record.payload)).empty


def test_http_error_is_not_treated_as_empty_history():
    with _client([], status=503) as client:
        with pytest.raises(httpx.HTTPStatusError):
            CsiIndexSourceAdapter(client=client).fetch(
                "index_daily", indexCode="930901", endDate="20261110",
            )


def test_invalid_json_raises_contract_error():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="不是 JSON"))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(CsiIndexContractError, match="JSON"):
            CsiIndexSourceAdapter(client=client).fetch(
                "index_daily", indexCode="930901", endDate="20261110",
            )


def test_timeout_is_propagated():
    def handler(request):
        raise httpx.ReadTimeout("请求超时", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ReadTimeout):
            CsiIndexSourceAdapter(client=client).fetch(
                "index_daily", indexCode="930901", endDate="20261110",
            )
