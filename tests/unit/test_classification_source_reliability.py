"""Public source failures retain bytes and retry only structured transient errors."""

import base64
import json
import subprocess

import pytest
import requests

from fip.services.data_service.adapters.akshare import client
from fip.services.data_service.adapters.akshare.overview_worker import capture_overview


def test_parser_failure_retains_original_http_body_without_retry(monkeypatch):
    response = requests.Response()
    response.status_code = 200
    response._content = b"<html>changed table 429</html>"
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)

    def parse_broken(symbol):
        requests.get("https://example.invalid")
        raise ValueError("table 429 missing")

    result = capture_overview("000001", caller=parse_broken)
    assert result["retryable"] is False
    assert base64.b64decode(result["raw"]) == b"<html>changed table 429</html>"
    assert result["kind"] == "parse"


def test_http_status_is_structured_retryable_before_parsing(monkeypatch):
    response = requests.Response()
    response.status_code = 503
    response._content = b"upstream maintenance"
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)
    result = capture_overview("000001", caller=lambda symbol: requests.get("https://invalid"))
    assert result["retryable"] is True
    assert result["http_status"] == 503
    assert base64.b64decode(result["raw"]) == b"upstream maintenance"


def test_isolated_parser_failure_is_not_retried_and_exposes_raw_record(monkeypatch):
    calls = []

    def run(*args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                {
                    "kind": "parse",
                    "retryable": False,
                    "raw": base64.b64encode(b"broken HTML").decode(),
                    "error": "table 429 missing",
                    "http_status": 200,
                }
            ).encode(),
            b"",
        )

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    with pytest.raises(client.AkShareContractError) as caught:
        client.AkShareSourceAdapter().fetch("fund_overview", symbol="000001")
    assert len(calls) == 1
    assert calls[0]["timeout"] == 25
    assert caught.value.record.payload == b"broken HTML"
    assert caught.value.record.request_params["payload_format"] == "html"


def test_request_interval_throttles_successive_starts(monkeypatch):
    ticks = iter([100.0, 100.1])
    waits = []
    monkeypatch.setattr(client.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(client.time, "sleep", waits.append)
    monkeypatch.setattr(client, "_overview_last_start", 0.0)
    client._throttle_overview()
    client._throttle_overview()
    assert waits == pytest.approx([0.4])


def test_successful_isolated_envelope_can_be_serialized_by_adapter(monkeypatch):
    import io

    import pandas as pd

    buf = io.BytesIO()
    pd.DataFrame([{"基金全称": "测试", "基金类型": "股票型"}]).to_parquet(buf, index=False)
    envelope = {
        "kind": "ok",
        "retryable": False,
        "raw": base64.b64encode(b"html").decode(),
        "parquet": base64.b64encode(buf.getvalue()).decode(),
        "http_status": 200,
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, json.dumps(envelope).encode(), b""),
    )
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    record = client.AkShareSourceAdapter().fetch("fund_overview", symbol="000001")
    assert pd.read_parquet(io.BytesIO(record.payload)).iloc[0]["基金类型"] == "股票型"
