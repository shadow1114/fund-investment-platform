"""基准行情抓取接口：权限、参数校验、幂等判定与 SKIPPED 项的无数据库单元测试。"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fip.api.app import create_app
from fip.api.schemas import BenchmarkIngestionRequest, FundIngestionItemModel
from fip.settings import Settings

MANAGER = {"X-Roles": "operations", "X-User-ID": "alice", "Idempotency-Key": "bench-key-1"}
VIEWER = {"X-Roles": "Researcher", "X-User-ID": "bob", "Idempotency-Key": "bench-key-1"}


@pytest.fixture()
def client():
    app = create_app(settings_override=Settings(database_url="sqlite://"))
    with TestClient(app) as test_client:
        yield test_client


def test_submit_requires_data_ingestion_permission(client):
    response = client.post(
        "/api/v1/benchmark-ingestion-jobs", headers=VIEWER, json={"benchmark_index_ids": ["1"]}
    )
    assert response.status_code == 403


def test_list_requires_data_ingestion_permission(client):
    assert client.get("/api/v1/benchmark-indexes", headers=VIEWER).status_code == 403


@pytest.mark.parametrize(
    "query", ["page_size=201", "page_size=0", "page=0", "source=wind", "q=" + "x" * 129]
)
def test_list_validates_query_parameters(client, query):
    response = client.get(f"/api/v1/benchmark-indexes?{query}", headers=MANAGER)
    assert response.status_code == 422


def test_submit_rejects_reversed_date_range_with_400(client):
    response = client.post(
        "/api/v1/benchmark-ingestion-jobs",
        headers=MANAGER,
        json={"benchmark_index_ids": ["1"], "start_date": "2026-02-01", "end_date": "2026-01-01"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_submit_compares_start_with_default_end_date(client, monkeypatch):
    from fip.api.routers import fund_ingestions

    monkeypatch.setattr(fund_ingestions, "_beijing_today", lambda: dt.date(2026, 1, 1))
    response = client.post(
        "/api/v1/benchmark-ingestion-jobs",
        headers=MANAGER,
        json={"benchmark_index_ids": ["1"], "start_date": "2026-01-02"},
    )
    assert response.status_code == 400


def test_submit_requires_idempotency_key(client):
    headers = {key: value for key, value in MANAGER.items() if key != "Idempotency-Key"}
    response = client.post(
        "/api/v1/benchmark-ingestion-jobs", headers=headers, json={"benchmark_index_ids": ["1"]}
    )
    assert response.status_code == 422


def test_submit_requires_durable_workers(client):
    response = client.post(
        "/api/v1/benchmark-ingestion-jobs", headers=MANAGER, json={"benchmark_index_ids": ["1"]}
    )
    assert response.status_code == 503


@pytest.mark.parametrize(
    "body",
    [
        {"benchmark_index_ids": []},
        {"benchmark_index_ids": [str(i) for i in range(201)]},
        {"benchmark_index_ids": ["abc"]},
        {"benchmark_index_ids": ["１"]},
        {"benchmark_index_ids": ["1"], "unknown": True},
        {"benchmark_index_ids": ["1"], "start_date": "not-a-date"},
    ],
)
def test_request_body_validation(client, body):
    response = client.post("/api/v1/benchmark-ingestion-jobs", headers=MANAGER, json=body)
    assert response.status_code == 422


def test_request_deduplicates_ids_preserving_order():
    request = BenchmarkIngestionRequest.model_validate({"benchmark_index_ids": ["3", "1", "3"]})
    assert request.benchmark_index_ids == ["3", "1"]
    with pytest.raises(ValidationError):
        BenchmarkIngestionRequest.model_validate({"benchmark_index_ids": ["-1"]})


def test_unsupported_source_items_are_skipped_with_reason():
    from fip.api.routers.fund_ingestions import _initial_benchmark_item

    for source in ("csindex", "chinabond", "akshare"):
        assert _initial_benchmark_item(source) == ("PENDING", None)
    assert _initial_benchmark_item(None) == ("SKIPPED", "不支持的基准数据源 source=None")
    assert _initial_benchmark_item("wind") == ("SKIPPED", "不支持的基准数据源 source=wind")


def test_idempotent_replay_matches_ids_and_dates():
    from fip.api.routers.fund_ingestions import _same_benchmark_request

    stored = {
        "dataset": "BENCHMARK",
        "benchmark_index_ids": ["1", "2"],
        "start_date": "2026-01-01",
        "end_date": "2026-11-13",
    }
    start = dt.date(2026, 1, 1)
    assert _same_benchmark_request(stored, ["1", "2"], start, None)
    assert _same_benchmark_request(stored, ["1", "2"], start, dt.date(2026, 11, 13))
    assert not _same_benchmark_request(stored, ["2", "1"], start, None)
    assert not _same_benchmark_request(stored, ["1", "2"], None, None)
    assert not _same_benchmark_request(stored, ["1", "2"], start, dt.date(2026, 11, 12))
    assert not _same_benchmark_request({**stored, "dataset": "NAV"}, ["1", "2"], start, None)


def test_task_model_exposes_benchmark_dataset_and_date_range():
    from fip.api.routers.fund_ingestions import _task_model

    now = dt.datetime(2026, 11, 13, tzinfo=dt.UTC)
    job = SimpleNamespace(
        execution_id="op-1",
        resource_id="SCOPED",
        status="RUNNING",
        error_detail=None,
        created_at=now,
        started_at=None,
        finished_at=None,
        job_payload={
            "dataset": "BENCHMARK",
            "actor": "alice",
            "source": "MULTI",
            "scope_type": "SELECTED",
            "scoped_items": True,
            "start_date": None,
            "end_date": "2026-11-13",
            "benchmark_index_ids": ["1"],
        },
        result_payload={"requested_count": 1, "skipped_count": 0},
    )
    model = _task_model(job)  # type: ignore[arg-type]
    assert (model.dataset, model.source, model.fund_id) == ("BENCHMARK", "MULTI", "SCOPED")
    assert (model.start_date, model.end_date) == (None, dt.date(2026, 11, 13))
    fund_job = SimpleNamespace(**{**job.__dict__, "job_payload": {"dataset": "NAV"}})
    assert _task_model(fund_job).start_date is None  # type: ignore[arg-type]


def test_item_model_defaults_to_fund_subject_and_allows_benchmark_items():
    base = {
        "id": 1, "share_class_id": None, "symbol": None, "status": "PENDING", "attempts": 0,
        "result": None, "error": None, "started_at": None, "finished_at": None,
    }
    fund_item = FundIngestionItemModel(**base, fund_id="000001")
    assert fund_item.subject_type == "FUND" and fund_item.benchmark_index_id is None
    bench = FundIngestionItemModel(
        **base, subject_type="BENCHMARK", subject_name="中证800", benchmark_index_id="5"
    )
    assert bench.fund_id is None


def test_benchmark_job_type_is_covered_by_ingestion_endpoints():
    from fip.api.routers.fund_ingestions import INGESTION_JOB_TYPES

    assert "benchmark_index_ingest" in INGESTION_JOB_TYPES


def test_like_pattern_escapes_wildcards():
    from fip.api.routers.fund_ingestions import _like_pattern

    assert _like_pattern("50%_a\\") == "%50\\%\\_a\\\\%"
