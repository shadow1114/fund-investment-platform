"""Bounded classification-worker tests with faked provider calls."""

import datetime as dt
import io
from dataclasses import replace
from types import SimpleNamespace

import pandas as pd

from fip.platform.jobs.executor import JobContext
from fip.platform.jobs.fund_classification import handle_fund_classification
from fip.platform.jobs.worker import _job_executor
from fip.platform.source.port import SourceRecord

NOW = dt.datetime(2026, 10, 28, tzinfo=dt.UTC)


def index_record(dataset: str, indicator: str) -> SourceRecord:
    frame = pd.DataFrame(
        [
            {
                "基金代码": "000001",
                "跟踪标的": "全部",
                "跟踪方式": indicator,
            }
        ]
    )
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return SourceRecord(
        dataset,
        buffer.getvalue(),
        1,
        NOW,
        {"symbol": "全部", "indicator": indicator},
    )


class FakeAdapter:
    def __init__(self, fail_dataset: str | None = None):
        self.fail_dataset = fail_dataset
        self.calls: list[tuple[str, dict[str, str]]] = []

    def fetch(self, dataset: str, **params: str):
        self.calls.append((dataset, params))
        if dataset == self.fail_dataset:
            raise TimeoutError("fixture timeout")
        indicator = "被动指数型" if dataset.endswith("passive") else "增强指数型"
        return index_record(dataset, indicator)


def run_index_job(monkeypatch, fail_dataset: str | None = None):
    fake = FakeAdapter(fail_dataset)
    import fip.services.data_service.adapters.akshare.client as client
    from fip.services.data_service.ingest import IngestService

    monkeypatch.setattr(client, "AkShareSourceAdapter", lambda: fake)
    monkeypatch.setattr(
        IngestService,
        "_store_raw",
        lambda self, record: SimpleNamespace(id=len(fake.calls) + 100),
    )
    job = SimpleNamespace(
        execution_id="JOB-001",
        job_payload={"action": "refresh_index_sets", "actor": "operator"},
        result_payload=None,
        progress=0,
    )
    context = JobContext(job, object(), "worker-1", NOW)
    outcome = handle_fund_classification(context)
    return fake, job, outcome


def test_index_refresh_collects_each_indicator_once_and_never_claims_unverified_complete(
    monkeypatch,
):
    fake, job, outcome = run_index_job(monkeypatch)
    assert [dataset for dataset, _ in fake.calls] == [
        "fund_index_passive",
        "fund_index_enhanced",
    ]
    assert all(params == {} for _, params in fake.calls)
    assert outcome.status == "COMPLETED"
    assert job.result_payload["task_status"] == "SUCCESS"
    assert [item["state"] for item in job.result_payload["items"]] == [
        "UNVERIFIED",
        "UNVERIFIED",
    ]
    assert all(item["may_withdraw_prior"] is False for item in job.result_payload["items"])


def test_one_index_source_failure_is_reported_without_suppressing_other_source(monkeypatch):
    fake, job, outcome = run_index_job(monkeypatch, "fund_index_enhanced")
    assert len(fake.calls) == 2
    assert outcome.status == "COMPLETED"
    assert job.result_payload["task_status"] == "PARTIAL_SUCCESS"
    passive, enhanced = job.result_payload["items"]
    assert passive["state"] == "UNVERIFIED"
    assert enhanced["state"] == "FAILED"
    assert "TimeoutError" in enhanced["diagnostics"][0]


def test_durable_worker_registers_both_classification_job_types():
    handlers = _job_executor()._handlers
    assert handlers["fund_classification_refresh"] is handle_fund_classification
    assert handlers["fund_classification_index_sets"] is handle_fund_classification
    assert "fund_basic_info_ingest" in handlers
    assert "fund_nav_ingest" in handlers


def test_payload_persistence_failure_does_not_suppress_other_index_batch(monkeypatch):
    fake = FakeAdapter()
    import fip.services.data_service.adapters.akshare.client as client
    from fip.services.data_service.ingest import IngestService

    monkeypatch.setattr(client, "AkShareSourceAdapter", lambda: fake)

    def store(self, record):
        if record.dataset == "fund_index_passive":
            raise OSError("fixture storage failure")
        return SimpleNamespace(id=101)

    monkeypatch.setattr(IngestService, "_store_raw", store)
    job = SimpleNamespace(
        execution_id="JOB-002",
        job_payload={"action": "refresh_index_sets", "actor": "operator"},
        result_payload=None,
        progress=0,
    )
    outcome = handle_fund_classification(JobContext(job, object(), "worker-1", NOW))
    assert outcome.status == "COMPLETED"
    assert len(fake.calls) == 2
    assert job.result_payload["task_status"] == "PARTIAL_SUCCESS"
    passive, enhanced = job.result_payload["items"]
    assert any("PERSIST_FAILED:OSError" in item for item in passive["diagnostics"])
    assert enhanced["payload_id"] == 101


def test_single_fund_job_includes_preview_unrecognized_reasons(monkeypatch):
    import fip.platform.jobs.fund_classification as classification_job
    import fip.services.data_service.adapters.akshare.client as client
    from fip.services.data_service.classification import workflow
    from fip.services.data_service.classification.service import ClassificationService
    from fip.services.data_service.ingest import IngestService
    from tests.unit.test_classification_revision import MemorySession

    overview_frame = pd.DataFrame([{"基金类型": "混合型-偏股"}])
    detail_frame = pd.DataFrame(
        [("基金代码", "000001"), ("投资策略", "采用主动管理和多因子模型")],
        columns=["item", "value"],
    )
    overview_buffer = io.BytesIO()
    overview_frame.to_parquet(overview_buffer, index=False)
    detail_buffer = io.BytesIO()
    detail_frame.to_parquet(detail_buffer, index=False)

    class FundAdapter:
        def fetch(self, dataset: str, **params: str):
            if dataset == "fund_overview":
                return SourceRecord(
                    dataset, overview_buffer.getvalue(), 1, NOW, {"symbol": "000001"}
                )
            assert dataset == "fund_detail_xq"
            return SourceRecord(
                dataset,
                detail_buffer.getvalue(),
                2,
                NOW,
                {"symbol": "000001", "timeout": "20"},
            )

    adapter = FundAdapter()
    monkeypatch.setattr(client, "AkShareSourceAdapter", lambda: adapter)
    monkeypatch.setattr(classification_job, "_latest_payload", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        classification_job,
        "_existing_index_evidence",
        lambda *_args, **_kwargs: ((), ("INDEX_BATCH_MISSING",), {}),
    )
    payload_ids = iter((101, 102))
    monkeypatch.setattr(
        IngestService,
        "_store_raw",
        lambda self, record: SimpleNamespace(id=next(payload_ids)),
    )
    monkeypatch.setattr(
        ClassificationService,
        "refresh",
        lambda self, *_args, **_kwargs: SimpleNamespace(id=55),
    )
    original_preview = workflow.preview_classification
    monkeypatch.setattr(
        workflow,
        "preview_classification",
        lambda *args, **kwargs: replace(
            original_preview(*args, **kwargs),
            unrecognized_reasons=("asset_class:UNRECOGNIZED",),
        ),
    )
    job = SimpleNamespace(
        execution_id="JOB-REFRESH",
        job_payload={
            "action": "refresh_fund",
            "fund_id": 1,
            "symbol": "000001",
            "actor": "operator",
        },
        result_payload=None,
        progress=0,
    )
    outcome = handle_fund_classification(JobContext(job, MemorySession(), "worker-1", NOW))
    assert outcome.status == "COMPLETED"
    assert job.result_payload["unrecognized_reasons"] == ["asset_class:UNRECOGNIZED"]
    assert job.result_payload["source_freshness"]["fund_detail_xq"]["state"] == "PARTIAL"
    assert (
        job.result_payload["source_freshness"]["fund_detail_xq"]["field_states"]["投资策略"]
        == "PRESENT"
    )
