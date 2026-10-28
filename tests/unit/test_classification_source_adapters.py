"""Offline provider-shaped fixtures: never import AKShare or request external data."""

import datetime as dt
import importlib
import io

import pandas as pd
import pytest

from fip.platform.source.port import SourceRecord
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter

NOW = dt.datetime(2026, 10, 27, tzinfo=dt.UTC)
INDEX_COLUMNS = [
    "基金代码",
    "基金名称",
    "单位净值",
    "日期",
    "日增长率",
    "近1周",
    "近1月",
    "近3月",
    "近6月",
    "近1年",
    "近2年",
    "近3年",
    "今年来",
    "成立来",
    "手续费",
    "起购金额",
    "跟踪标的",
    "跟踪方式",
]


@pytest.fixture(autouse=True)
def block_default_provider_calls(monkeypatch):
    import socket
    import subprocess

    import requests

    from fip.services.data_service.adapters.akshare import client, source_worker

    def forbidden(*args, **kwargs):
        pytest.fail("live default caller is forbidden in offline adapter tests")

    monkeypatch.setattr(client, "_default_caller", forbidden)
    monkeypatch.setattr(source_worker, "_provider_call", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    original_popen = subprocess.Popen

    def guarded_popen(command, *args, **kwargs):
        # Only the reviewed local sleeping-child timeout fixture may start a process.
        if (
            isinstance(command, list)
            and len(command) == 4
            and command[1] == "-c"
            and command[2]
            == ("import pathlib,sys,time; time.sleep(1); pathlib.Path(sys.argv[1]).touch()")
            and not kwargs.get("shell")
        ):
            return original_popen(command, *args, **kwargs)
        pytest.fail("unreviewed child process forbidden in offline adapter tests")

    monkeypatch.setattr(subprocess, "Popen", guarded_popen)


def sources():
    return importlib.import_module(
        "fip.services.data_service.adapters.akshare.classification_sources"
    )


def index_frame(codes=("000001", "012345"), indicator="被动指数型"):
    rows = []
    for code in codes:
        row = dict.fromkeys(INDEX_COLUMNS, "0")
        row.update(
            {
                "基金代码": code,
                "基金名称": "测试基金",
                "日期": "2026-10-26",
                "跟踪标的": "全部",
                "跟踪方式": indicator,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=INDEX_COLUMNS)


def snowball_frame():
    return pd.DataFrame(
        [
            ("基金代码", "000001"),
            ("基金名称", "测试混合A"),
            ("基金全称", "测试基金"),
            ("成立时间", "2020-01-01"),
            ("最新规模", "1亿"),
            ("基金公司", "公司"),
            ("基金经理", "经理"),
            ("托管银行", "银行"),
            ("基金类型", "混合型-偏股"),
            ("评级机构", None),
            ("基金评级", "五星"),
            ("投资策略", "采用主动管理和多因子模型"),
            ("投资目标", "争取长期回报"),
            ("业绩比较基准", "沪深300指数收益率*80%"),
        ],
        columns=["item", "value"],
    )


def record(frame, dataset="fund_index_passive", **params):
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return SourceRecord(dataset, buf.getvalue(), len(frame), NOW, params)


@pytest.mark.parametrize(
    "dataset,indicator",
    [
        ("fund_index_passive", "被动指数型"),
        ("fund_index_enhanced", "增强指数型"),
    ],
)
def test_index_registry_uses_exact_central_query(dataset, indicator):
    def caller(name, **params):
        assert name == "fund_info_index_em"
        assert params == {"symbol": "全部", "indicator": indicator}
        return index_frame(indicator=indicator)

    result = AkShareSourceAdapter(caller=caller).fetch(dataset)
    assert result.row_count == 2
    assert result.request_params == {"symbol": "全部", "indicator": indicator}


def test_snowball_registry_passes_fund_identity_and_bounded_timeout():
    def caller(name, **params):
        assert name == "fund_individual_basic_info_xq"
        assert params == {"symbol": "000001", "timeout": 20}
        return snowball_frame()

    result = AkShareSourceAdapter(caller=caller).fetch("fund_detail_xq", symbol="000001")
    assert result.row_count == 14


def test_index_membership_is_positive_only_with_stable_provider_identity():
    module = sources()
    result = module.parse_index_batch(
        record(index_frame(), symbol="全部", indicator="被动指数型"),
        batch_id="batch-1",
        payload_ref="raw_payload:7",
        verified_total=2,
    )
    assert result.state == "COMPLETE"
    assert result.may_withdraw_prior is True
    assert result.row_count == 2
    assert result.batch_id == "batch-1"
    assert result.indicator == "被动指数型"
    assert result.source_timestamp == NOW
    assert result.published_at is None
    assert result.provider_available_at is None
    assert result.fund_codes == ("000001", "012345")
    assert len(result.evidence) == 2
    evidence = result.evidence[0]
    assert evidence.source == "AGGREGATOR"
    assert evidence.normalized_field == "index_membership"
    assert evidence.raw_field == "基金代码"
    assert evidence.raw_value == "000001"
    assert evidence.payload_ref == "raw_payload:7"
    assert evidence.classified_at == NOW
    identity = module.source_identity(evidence)
    assert identity["provider"] == "EASTMONEY"
    assert identity["adapter"] == "AKSHARE"
    assert identity["dataset"] == "fund_index_passive"
    assert identity["function"] == "fund_info_index_em"
    assert identity["params"] == {"symbol": "全部", "indicator": "被动指数型"}
    assert identity["provider_fund_code"] == "000001"
    assert identity["raw_field"] == "基金代码"
    assert "row" not in identity  # row positions belong to payload location, not stable identity
    assert "row:0" in evidence.locator
    again = module.parse_index_batch(
        record(index_frame(("012345", "000001")), symbol="全部", indicator="被动指数型"),
        batch_id="batch-2",
        payload_ref="raw_payload:8",
        verified_total=2,
    )
    assert module.source_identity(again.evidence[1]) == identity
    enhanced = module.parse_index_batch(
        record(
            index_frame(indicator="增强指数型"),
            "fund_index_enhanced",
            symbol="全部",
            indicator="增强指数型",
        ),
        batch_id="batch-3",
        payload_ref="raw_payload:9",
        verified_total=2,
    )
    assert module.source_identity(enhanced.evidence[0]) != identity


@pytest.mark.parametrize(
    "codes,total,state",
    [
        (("000001",), None, "UNVERIFIED"),
        (("000001",), 2, "UNVERIFIED"),
        ((), 0, "EMPTY"),
        (("000001", "bad"), 2, "MALFORMED"),
        (("000001", "000001"), 2, "MALFORMED"),
        ((1,), 1, "MALFORMED"),
    ],
)
def test_unsafe_batch_retains_prior_membership(codes, total, state):
    result = sources().parse_index_batch(
        record(index_frame(codes), symbol="全部", indicator="被动指数型"),
        batch_id="batch",
        payload_ref="raw:1",
        verified_total=total,
    )
    assert result.state == state
    assert not result.may_withdraw_prior
    assert result.diagnostics


def test_capped_batch_is_not_complete_even_with_matching_count():
    frame = index_frame(tuple(f"{i:06d}" for i in range(10000)))
    result = sources().parse_index_batch(
        record(frame, symbol="全部", indicator="被动指数型"),
        batch_id="cap",
        payload_ref="raw:1",
        verified_total=10000,
    )
    assert result.state == "CAPPED"
    assert not result.may_withdraw_prior


@pytest.mark.parametrize("mutation", ["missing_column", "wrong_context", "wrong_request"])
def test_schema_or_scope_drift_cannot_withdraw(mutation):
    frame = index_frame()
    params = {"symbol": "全部", "indicator": "被动指数型"}
    if mutation == "missing_column":
        frame = frame.drop(columns=["基金代码"])
    elif mutation == "wrong_context":
        frame.loc[0, "跟踪标的"] = "股票指数"
    else:
        params["indicator"] = "增强指数型"
    result = sources().parse_index_batch(
        record(frame, **params),
        batch_id="bad",
        payload_ref="raw:1",
        verified_total=2,
    )
    assert result.state == "MALFORMED"
    assert not result.may_withdraw_prior


def test_snowball_long_form_emits_only_four_field_evidence():
    module = sources()
    result = module.parse_snowball_detail(
        record(snowball_frame(), "fund_detail_xq", symbol="000001", timeout="20"),
        payload_ref="raw_payload:11",
    )
    assert result.state == "VALID"
    assert result.field_states == {
        "基金类型": "PRESENT",
        "投资策略": "PRESENT",
        "投资目标": "PRESENT",
        "业绩比较基准": "PRESENT",
    }
    assert [item.normalized_field for item in result.evidence] == [
        "formal_type",
        "investment_strategy",
        "investment_objective",
        "benchmark",
    ]
    assert all(item.source == "AGGREGATOR" for item in result.evidence)
    assert module.source_identity(result.evidence[0])["provider"] == "SNOWBALL"
    assert module.source_identity(result.evidence[0])["provider_fund_code"] == "000001"
    assert "row:8" in result.evidence[0].locator


def test_snowball_absent_empty_duplicate_are_distinct_and_duplicates_not_chosen():
    frame = snowball_frame()
    frame = frame[~frame["item"].isin(["投资目标"])]
    frame.loc[frame["item"] == "投资策略", "value"] = None
    frame = pd.concat(
        [frame, pd.DataFrame([("基金类型", "股票型")], columns=["item", "value"])],
        ignore_index=True,
    )
    result = sources().parse_snowball_detail(
        record(frame, "fund_detail_xq", symbol="000001"),
        payload_ref="raw:12",
    )
    assert result.field_states == {
        "基金类型": "DUPLICATE",
        "投资策略": "EMPTY",
        "投资目标": "ABSENT",
        "业绩比较基准": "PRESENT",
    }
    assert [e.raw_field for e in result.evidence] == ["投资策略", "业绩比较基准"]
    assert result.evidence[0].raw_value == ""
    assert result.diagnostics


@pytest.mark.parametrize(
    "mutation,state",
    [
        ("mismatch", "IDENTITY_MISMATCH"),
        ("identity_absent", "IDENTITY_MISMATCH"),
        ("identity_duplicate", "IDENTITY_MISMATCH"),
        ("missing_column", "MALFORMED"),
        ("bad_item", "MALFORMED"),
        ("bad_value", "MALFORMED"),
    ],
)
def test_snowball_malformed_or_wrong_fund_is_not_usable(mutation, state):
    frame = snowball_frame()
    if mutation == "mismatch":
        frame.loc[0, "value"] = "000002"
    elif mutation == "identity_absent":
        frame = frame.iloc[1:]
    elif mutation == "identity_duplicate":
        frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    elif mutation == "missing_column":
        frame = frame.rename(columns={"item": "changed"})
    elif mutation == "bad_item":
        frame.loc[1, "item"] = None
    else:
        # Use a scalar number; heterogeneous lists cannot be encoded as parquet strings.
        frame.loc[11, "value"] = "123"
        frame["value"] = frame["value"].map(lambda v: [v] if v is not None else None)
    result = sources().parse_snowball_detail(
        record(frame, "fund_detail_xq", symbol="000001"),
        payload_ref="raw:13",
    )
    assert result.state == state
    assert not result.evidence
    assert result.diagnostics


def test_central_collection_runs_each_indicator_once_and_reports_partial_failure():
    calls = []

    def caller(name, **params):
        calls.append((name, params))
        if params["indicator"] == "增强指数型":
            raise ValueError("upstream missing field")
        return index_frame()

    results = sources().collect_index_batches(
        AkShareSourceAdapter(caller=caller, clock=lambda: NOW),
        batch_id="central",
        payload_refs={"被动指数型": "raw:20", "增强指数型": "raw:21"},
        verified_totals={"被动指数型": 2},
    )
    assert [result.state for result in results] == ["COMPLETE", "FAILED"]
    assert results[1].may_withdraw_prior is False
    assert results[1].diagnostics
    assert calls == [
        ("fund_info_index_em", {"symbol": "全部", "indicator": "被动指数型"}),
        ("fund_info_index_em", {"symbol": "全部", "indicator": "增强指数型"}),
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"symbol": "股票指数"},
        {"indicator": "增强指数型"},
    ],
)
def test_index_dataset_rejects_scope_override_before_fetch(params):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid scope must not reach provider")

    with pytest.raises(ValueError):
        AkShareSourceAdapter(caller=forbidden).fetch("fund_index_passive", **params)


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"symbol": "1"},
        {"symbol": "000001", "timeout": "0"},
        {"symbol": "000001", "timeout": "1000"},
    ],
)
def test_snowball_rejects_invalid_identity_or_unbounded_timeout(params):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid request must not reach provider")

    with pytest.raises(ValueError):
        AkShareSourceAdapter(caller=forbidden).fetch("fund_detail_xq", **params)


def test_classification_fetch_uses_isolated_worker_and_hard_timeout(monkeypatch):
    import json
    import subprocess

    from fip.services.data_service.adapters.akshare import client

    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "kind": "parse",
                    "retryable": False,
                    "raw": "YnJva2VuIEpTT04=",
                    "error": "provider changed field",
                }
            ).encode(),
            b"",
        )

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(client, "_throttle_overview", lambda: None)
    with pytest.raises(client.AkShareContractError) as caught:
        client.AkShareSourceAdapter().fetch("fund_index_passive")
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[2] == "fip.services.data_service.adapters.akshare.source_worker"
    assert command[3] == "fund_info_index_em"
    assert json.loads(command[4]) == {"symbol": "全部", "indicator": "被动指数型"}
    assert kwargs["timeout"] == 25
    assert caught.value.record.payload == b"broken JSON"
    assert caught.value.record.request_params["payload_format"] == "http_body"


def test_transient_classification_failure_retries_then_keeps_failure_payload(monkeypatch):
    import json
    import subprocess

    from fip.services.data_service.adapters.akshare import client

    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "kind": "network",
                    "retryable": True,
                    "raw": "bWFpbnRlbmFuY2U=",
                    "error": "503 maintenance",
                    "http_status": 503,
                }
            ).encode(),
            b"",
        )

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(client, "_throttle_overview", lambda: None)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    with pytest.raises(client.AkShareContractError) as caught:
        client.AkShareSourceAdapter().fetch("fund_detail_xq", symbol="000001")
    assert len(calls) == 3
    assert caught.value.record.payload == b"maintenance"


def test_timed_out_classification_call_is_bounded_and_not_empty_success(monkeypatch):
    import subprocess

    from fip.services.data_service.adapters.akshare import client

    calls = []

    def run(command, **kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(client, "_throttle_overview", lambda: None)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    with pytest.raises(client.AkShareContractError, match="TimeoutExpired") as caught:
        client.AkShareSourceAdapter().fetch("fund_index_passive")
    assert len(calls) == 3
    assert caught.value.record.request_params["indicator"] == "被动指数型"


def test_source_worker_preserves_http_error_body_without_retrying_parser(monkeypatch):
    import requests

    module = importlib.import_module("fip.services.data_service.adapters.akshare.source_worker")
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"data":"changed upstream"}'
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)

    def broken(**params):
        assert params == {"symbol": "000001", "timeout": 20}
        requests.get("https://offline.invalid")
        raise KeyError("invest_orientation")

    result = module.capture_source(
        "fund_individual_basic_info_xq",
        {"symbol": "000001", "timeout": 20},
        caller=broken,
    )
    import base64

    assert result["kind"] == "parse"
    assert not result["retryable"]
    assert base64.b64decode(result["raw"]) == b'{"data":"changed upstream"}'


def test_real_child_timeout_terminates_child_without_main_worker_hang(tmp_path):
    import subprocess
    import sys
    import time

    from fip.services.data_service.adapters.akshare import client

    # A local sleeping child substitutes for AKShare; no network or AKShare import.
    marker = tmp_path / "child-survived"
    command = [
        sys.executable,
        "-c",
        "import pathlib,sys,time; time.sleep(1); pathlib.Path(sys.argv[1]).touch()",
        str(marker),
    ]
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        client._run_isolated(command, timeout=0.1)
    assert time.monotonic() - start < 2
    time.sleep(1.1)
    assert not marker.exists()


def test_source_worker_honors_shorter_snowball_http_timeout(monkeypatch):
    import requests

    module = importlib.import_module("fip.services.data_service.adapters.akshare.source_worker")
    seen = []
    response = requests.Response()
    response.status_code = 200
    response._content = b"{}"

    def get(*args, **kwargs):
        seen.append(kwargs["timeout"])
        return response

    monkeypatch.setattr(requests, "get", get)

    def caller(**params):
        requests.get("https://offline.invalid", timeout=params["timeout"])
        return snowball_frame()

    result = module.capture_source(
        "fund_individual_basic_info_xq",
        {"symbol": "000001", "timeout": 3},
        caller=caller,
    )
    assert result["kind"] == "ok"
    assert seen == [3]


def test_contract_failure_retains_source_timestamp_and_payload_in_failed_batch():
    result = sources().collect_index_batches(
        AkShareSourceAdapter(
            caller=lambda *a, **kw: pd.DataFrame({"changed": ["x"]}), clock=lambda: NOW
        ),
        batch_id="bad",
        payload_refs={"被动指数型": "raw:30", "增强指数型": "raw:31"},
    )
    assert [batch.state for batch in result] == ["FAILED", "FAILED"]
    assert all(batch.source_timestamp == NOW for batch in result)
    assert all(batch.record.payload for batch in result)
    assert all(not batch.may_withdraw_prior for batch in result)


def test_snowball_ignores_nontext_metadata_without_discarding_classification_fields():
    # Homogeneous parquet payload models an irrelevant numeric metadata value.
    frame = snowball_frame()
    frame = pd.concat(
        [frame, pd.DataFrame([("其他元数据", ["1", "2"])], columns=["item", "value"])],
        ignore_index=True,
    )
    # Construct a provider-shaped frame through the decoder boundary; parquet cannot
    # encode mixed string/list object columns, which itself is an upstream contract error.
    module = sources()
    original = record(snowball_frame(), "fund_detail_xq", symbol="000001")
    from dataclasses import replace
    from unittest.mock import patch

    with patch.object(module.pd, "read_parquet", return_value=frame):
        result = module.parse_snowball_detail(
            replace(original, row_count=len(frame)), payload_ref="raw:40"
        )
    assert result.state == "VALID"
    assert len(result.evidence) == 4


def test_snowball_classification_value_contract_failure_retains_raw_response(monkeypatch):
    import base64

    import requests

    module = importlib.import_module("fip.services.data_service.adapters.akshare.source_worker")
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"data":{"fd_code":"000001","totshare":123.4}}'
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)

    def caller(**params):
        requests.get("https://offline.invalid")
        frame = snowball_frame()
        frame.loc[frame["item"] == "最新规模", "value"] = 123.4
        frame.loc[frame["item"] == "投资策略", "value"] = 123.4
        return frame

    result = module.capture_source(
        "fund_individual_basic_info_xq",
        {"symbol": "000001", "timeout": 20},
        caller=caller,
    )
    assert result["kind"] == "parse"
    assert not result["retryable"]
    assert "Arrow" in result["error"]
    assert base64.b64decode(result["raw"]) == response.content


@pytest.mark.parametrize("transport", ["isolated", "injected"])
def test_mixed_snowball_metadata_reaches_adapter_parser_without_changing_evidence(
    monkeypatch,
    transport,
):
    import json
    import subprocess

    import requests

    from fip.services.data_service.adapters.akshare import client, source_worker

    raw = b'{"data":{"fd_code":"000001","totshare":123.4}}'
    response = requests.Response()
    response.status_code = 200
    response._content = raw
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    frame = snowball_frame()
    frame.loc[frame["item"] == "最新规模", "value"] = 123.4
    frame.loc[frame["item"] == "投资目标", "value"] = None

    def provider(**params):
        assert params == {"symbol": "000001", "timeout": 20.0}
        requests.get("https://offline.invalid")
        return frame.copy()

    def run(command, **kwargs):
        assert command[2] == "fip.services.data_service.adapters.akshare.source_worker"
        envelope = source_worker.capture_source(
            command[3],
            json.loads(command[4]),
            caller=provider,
        )
        return subprocess.CompletedProcess(command, 0, json.dumps(envelope).encode(), b"")

    monkeypatch.setattr(client, "_throttle_overview", lambda: None)
    monkeypatch.setattr(subprocess, "run", run)
    adapter = AkShareSourceAdapter(clock=lambda: NOW)
    if transport == "injected":
        adapter = AkShareSourceAdapter(
            clock=lambda: NOW, caller=lambda name, **params: provider(**params)
        )
    payload = adapter.fetch("fund_detail_xq", symbol="000001")
    result = sources().parse_snowball_detail(payload, payload_ref="raw:50")
    assert result.state == "VALID"
    assert result.field_states["投资目标"] == "EMPTY"
    assert [(e.raw_field, e.raw_value) for e in result.evidence] == [
        ("基金类型", "混合型-偏股"),
        ("投资策略", "采用主动管理和多因子模型"),
        ("投资目标", ""),
        ("业绩比较基准", "沪深300指数收益率*80%"),
    ]
    restored = pd.read_parquet(io.BytesIO(payload.payload))
    assert restored.loc[restored["item"] == "最新规模", "value"].iloc[0] == "123.4"
    assert frame.loc[frame["item"] == "最新规模", "value"].iloc[0] == 123.4


def test_nullable_index_context_reports_malformed_and_collects_other_indicator():
    def caller(name, **params):
        frame = index_frame(indicator=params["indicator"])
        if params["indicator"] == "被动指数型":
            # Nullable pandas string dtype preserves pd.NA through parquet roundtrip.
            frame["跟踪标的"] = pd.Series([pd.NA, "全部"], dtype="string")
        return frame

    results = sources().collect_index_batches(
        AkShareSourceAdapter(caller=caller, clock=lambda: NOW),
        batch_id="nullable",
        payload_refs={"被动指数型": "raw:60", "增强指数型": "raw:61"},
        verified_totals={"被动指数型": 2, "增强指数型": 2},
    )
    assert [batch.state for batch in results] == ["MALFORMED", "COMPLETE"]
    assert results[0].diagnostics
    assert not results[0].may_withdraw_prior
    assert results[1].fund_codes == ("000001", "012345")


def test_parse_exception_does_not_skip_independent_enhanced_batch(monkeypatch):
    module = sources()
    parse = module.parse_index_batch

    def parse_with_nullable_failure(record, **kwargs):
        if record.dataset == "fund_index_passive":
            raise TypeError("boolean value of NA is ambiguous")
        return parse(record, **kwargs)

    monkeypatch.setattr(module, "parse_index_batch", parse_with_nullable_failure)
    results = module.collect_index_batches(
        AkShareSourceAdapter(
            caller=lambda name, **params: index_frame(indicator=params["indicator"]),
            clock=lambda: NOW,
        ),
        batch_id="parse-error",
        payload_refs={"被动指数型": "raw:62", "增强指数型": "raw:63"},
        verified_totals={"增强指数型": 2},
    )
    assert [batch.state for batch in results] == ["MALFORMED", "COMPLETE"]
    assert "TypeError" in results[0].diagnostics[0]
    assert results[0].record.payload
    assert not results[0].may_withdraw_prior


def test_offline_guard_blocks_source_provider_child_before_process_creation():
    import sys

    from fip.services.data_service.adapters.akshare import client

    with pytest.raises(pytest.fail.Exception, match="unreviewed child process"):
        client._run_isolated(
            [
                sys.executable,
                "-m",
                "fip.services.data_service.adapters.akshare.source_worker",
                "fund_info_index_em",
                "{}",
            ]
        )
