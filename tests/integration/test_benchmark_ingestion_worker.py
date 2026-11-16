"""基准行情抓取端到端：接口提交 / 幂等 / SKIPPED、worker 写库与版本规则、失败隔离。"""

import datetime as dt
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from fip.api.app import create_app
from fip.platform.source.port import SourceRecord
from fip.services.data_service.models.benchmark import BenchmarkIndex, BenchmarkIndexValue

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def clean_committed_benchmark_ingestion_fixtures(db_engine):
    """The API test commits benchmark jobs and indexes through an independent session."""
    yield
    with db_engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM governance.calculation_job "
                "WHERE job_type = 'benchmark_index_ingest'"
            )
        )
        connection.execute(
            text(
                "DELETE FROM market.benchmark_index "
                "WHERE provider_code IN ('ZZTEST1', 'ZZTEST2')"
            )
        )

HEADERS = {"X-Roles": "operations", "X-User-ID": "alice"}


class _FakeCsiAdapter:
    provider_code = "CSIINDEX"
    adapter_version = "test"

    def __init__(self, closes: dict[str, float | None]) -> None:
        self.closes = closes

    def fetch(self, dataset: str, **params: str) -> SourceRecord:
        frame = pd.DataFrame(
            {"tradeDate": list(self.closes), "close": list(self.closes.values())}
        )
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        return SourceRecord(
            dataset=dataset,
            payload=buffer.getvalue(),
            row_count=len(frame),
            ingested_at=dt.datetime.now(dt.UTC),
            request_params=params,
        )


def test_submit_list_items_and_skipped_sources(db_engine):
    with Session(db_engine) as session:
        supported = BenchmarkIndex(
            provider_code="ZZTEST1", display_name="集成测试指数甲", source="csindex"
        )
        unsupported = BenchmarkIndex(
            provider_code="ZZTEST2", display_name="集成测试指数乙", source="wind"
        )
        session.add_all([supported, unsupported])
        session.commit()
        ids = [str(supported.id), str(unsupported.id)]
    app = create_app(persistent_operations=True, strict_contracts=True)
    app.state.api_engine = db_engine
    with TestClient(app) as client:
        listing = client.get("/api/v1/benchmark-indexes?q=集成测试指数", headers=HEADERS)
        assert listing.status_code == 200, listing.text
        page = listing.json()["data"]
        assert page["total"] == 2
        assert page["source_counts"] == {"csindex": 1, "chinabond": 0, "akshare": 0}
        filtered = client.get(
            "/api/v1/benchmark-indexes?q=zztest&source=csindex", headers=HEADERS
        ).json()["data"]
        assert [item["provider_code"] for item in filtered["items"]] == ["ZZTEST1"]
        assert filtered["source_counts"]["csindex"] == 1

        key = {**HEADERS, "Idempotency-Key": "bench-submit-1"}
        body = {"benchmark_index_ids": ids, "start_date": "2026-01-01", "end_date": "2026-01-31"}
        submit = client.post("/api/v1/benchmark-ingestion-jobs", headers=key, json=body)
        assert submit.status_code == 202, submit.text
        data = submit.json()["data"]
        assert (data["dataset"], data["fund_id"]) == ("BENCHMARK", "SCOPED")
        replay = client.post("/api/v1/benchmark-ingestion-jobs", headers=key, json=body)
        assert replay.json()["data"]["operation_id"] == data["operation_id"]
        conflict = client.post(
            "/api/v1/benchmark-ingestion-jobs",
            headers=key,
            json={**body, "benchmark_index_ids": ids[:1]},
        )
        assert conflict.status_code == 409

        operation_id = data["operation_id"]
        task = client.get(f"/api/v1/ingestions/{operation_id}", headers=HEADERS).json()["data"]
        assert (task["start_date"], task["end_date"]) == ("2026-01-01", "2026-01-31")
        items = client.get(f"/api/v1/ingestions/{operation_id}/items", headers=HEADERS)
        assert items.status_code == 200, items.text
        rows = items.json()["data"]["items"]
        assert [(row["subject_type"], row["status"]) for row in rows] == [
            ("BENCHMARK", "PENDING"),
            ("BENCHMARK", "SKIPPED"),
        ]
        assert rows[0]["subject_name"] == "集成测试指数甲"
        assert rows[1]["benchmark_index_id"] == ids[1]
        assert "fund_id" not in rows[0]
        history = client.get(
            "/api/v1/fund-ingestions?dataset=BENCHMARK", headers=HEADERS
        ).json()["data"]
        assert operation_id in [item["operation_id"] for item in history["items"]]
        assert client.post(
            f"/api/v1/ingestions/{operation_id}/cancel", headers=HEADERS
        ).status_code == 202


def test_worker_writes_versions_and_isolates_failed_items(db_session):
    from fip.platform.jobs.benchmark_ingestion import handle_benchmark_ingestion
    from fip.platform.jobs.executor import JobContext
    from fip.platform.jobs.models import CalculationJob
    from fip.services.data_service.models.fund_ingestion import BenchmarkIngestionRunItem

    good = BenchmarkIndex(provider_code="000906", display_name="集成测试中证", source="csindex")
    bad = BenchmarkIndex(provider_code="cbx", display_name="集成测试中债", source="chinabond")
    db_session.add_all([good, bad])
    db_session.flush()
    job = CalculationJob(
        execution_id="bench-worker",
        idempotency_key="bench-worker",
        job_type="benchmark_index_ingest",
        status="RUNNING",
        progress=0,
        job_payload={
            "dataset": "BENCHMARK",
            "actor": "alice",
            "scoped_items": True,
            "start_date": "2026-01-05",
            "end_date": "2026-01-07",
        },
    )
    db_session.add(job)
    db_session.flush()
    for index in (good, bad):
        db_session.add(
            BenchmarkIngestionRunItem(
                operation_id=job.execution_id,
                benchmark_index_id=index.id,
                status="PENDING",
                attempts=0,
            )
        )
    db_session.flush()
    closes = {"20260102": 1.0, "20260105": 100.0, "20260106": None, "20260107": 101.0}
    adapter = _FakeCsiAdapter(closes)
    now = dt.datetime.now(dt.UTC)
    outcome = handle_benchmark_ingestion(
        JobContext(job=job, session=db_session, worker_id="w", now=now),
        adapter_factory=lambda _source: adapter,
    )
    assert outcome.status == "COMPLETED"
    items = {
        item.benchmark_index_id: item
        for item in db_session.scalars(
            select(BenchmarkIngestionRunItem).where(
                BenchmarkIngestionRunItem.operation_id == job.execution_id
            )
        )
    }
    assert items[good.id].status == "SUCCESS"
    assert items[good.id].result["inserted_count"] == 2
    assert items[bad.id].status == "FAILED"
    assert "param" in (items[bad.id].error or "")
    values = db_session.scalars(
        select(BenchmarkIndexValue).where(BenchmarkIndexValue.index_id == good.id)
    ).all()
    assert sorted((row.effective_at, row.version) for row in values) == [
        (dt.date(2026, 1, 5), 1),
        (dt.date(2026, 1, 7), 1),
    ]
    assert {row.availability_quality for row in values} == {"INFERRED"}

    # 第二次：1/5 不变、1/7 修订 → 只新增 1/7 的 version 2。
    adapter.closes = {"20260105": 100.0, "20260107": 101.5}
    for item in items.values():
        item.status = "PENDING"
    db_session.flush()
    handle_benchmark_ingestion(
        JobContext(job=job, session=db_session, worker_id="w", now=now),
        adapter_factory=lambda _source: adapter,
    )
    assert items[good.id].result["unchanged_count"] == 1
    assert items[good.id].result["inserted_count"] == 1
    versions = db_session.scalars(
        select(BenchmarkIndexValue.version).where(
            BenchmarkIndexValue.index_id == good.id,
            BenchmarkIndexValue.effective_at == dt.date(2026, 1, 7),
        )
    ).all()
    assert sorted(versions) == [1, 2]
