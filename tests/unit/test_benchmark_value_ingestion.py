"""基准行情抓取：请求解析、帧解析、版本规则与任务 handler 的无数据库单元测试。"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pandas as pd
import pytest
from sqlalchemy.sql.dml import Update

from fip.platform.source.port import SourceRecord
from fip.services.data_service import benchmark_values
from fip.services.data_service.benchmark_values import (
    BENCHMARK_FRAME_COLUMNS,
    BenchmarkConfigError,
    BenchmarkDataError,
    ParsedIndexValue,
    build_fetch_request,
    parse_index_frame,
    resolve_akshare_dataset,
    write_index_values,
)

NOW = dt.datetime(2026, 11, 13, 8, 0, tzinfo=dt.UTC)
END = dt.date(2026, 11, 13)


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _record(frame: pd.DataFrame, dataset: str = "index_daily") -> SourceRecord:
    return SourceRecord(
        dataset=dataset, payload=_parquet(frame), row_count=len(frame), ingested_at=NOW
    )


# ---------- 请求解析 ----------


def test_csindex_uses_provider_code_and_ignores_api_and_param():
    request = build_fetch_request(
        source="csindex",
        provider_code="000906",
        api="ignored",
        param={"index_type": "ignored"},
        start_date=dt.date(2026, 1, 2),
        end_date=END,
    )
    assert (request.dataset, request.params) == (
        "index_daily",
        {"indexCode": "000906", "startDate": "20260102", "endDate": "20261113"},
    )
    without_start = build_fetch_request(
        source="csindex", provider_code="H11001", api=None, param=None,
        start_date=None, end_date=END,
    )
    assert "startDate" not in without_start.params


def test_chinabond_reads_index_type_and_period_type_from_param():
    request = build_fetch_request(
        source="chinabond",
        provider_code="8a8b2c8f5a62e9ca015a645fe3b60001",
        api=None,
        param={"period_type": "00", "index_type": "QJZS"},
        start_date=None,
        end_date=END,
    )
    assert request.params == {
        "code": "8a8b2c8f5a62e9ca015a645fe3b60001",
        "index_type": "QJZS",
        "period_type": "00",
    }


@pytest.mark.parametrize(
    ("param", "message"),
    [
        (None, "缺少 param"),
        ({"period_type": "00"}, "index_type"),
        ({"index_type": "QJZS"}, "period_type"),
        ({"index_type": "", "period_type": "00"}, "index_type"),
        ({"index_type": 1, "period_type": "00"}, "index_type"),
    ],
)
def test_chinabond_missing_param_is_a_config_error(param, message):
    with pytest.raises(BenchmarkConfigError, match=message):
        build_fetch_request(
            source="chinabond", provider_code="abc", api=None, param=param,
            start_date=None, end_date=END,
        )


def test_akshare_api_is_resolved_to_dataset_by_callable_name():
    assert resolve_akshare_dataset("stock_hk_index_daily_em") == "hk_index_daily"
    request = build_fetch_request(
        source="akshare", provider_code="HSTECH", api="stock_hk_index_daily_em",
        param=None, start_date=None, end_date=END,
    )
    assert (request.dataset, request.params) == ("hk_index_daily", {"symbol": "HSTECH"})


@pytest.mark.parametrize("api", [None, "", "fund_open_fund_info_em", "unknown_api"])
def test_akshare_unknown_api_is_rejected_with_clear_error(api):
    # fund_open_fund_info_em 虽是已登记函数，但不在基准列映射表中，同样拒绝。
    with pytest.raises(BenchmarkConfigError, match="AKShare"):
        resolve_akshare_dataset(api)


def test_unsupported_source_is_a_config_error():
    with pytest.raises(BenchmarkConfigError, match="不支持的基准数据源"):
        build_fetch_request(
            source="wind", provider_code="X", api=None, param=None,
            start_date=None, end_date=END,
        )


def test_every_mapped_akshare_dataset_is_declared():
    from fip.services.data_service.adapters.akshare.datasets import DATASETS

    for source, dataset in BENCHMARK_FRAME_COLUMNS:
        if source == "akshare":
            columns = BENCHMARK_FRAME_COLUMNS[(source, dataset)]
            assert {columns.date_column, columns.value_column} <= DATASETS[dataset].required_columns


# ---------- 帧解析 ----------


def test_parse_filters_date_range_and_skips_null_values():
    frame = pd.DataFrame(
        {
            "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2), dt.date(2026, 1, 3),
                     dt.date(2026, 1, 4)],
            "value": [100.0, None, 101.5, 102.0],
        }
    )
    parsed = parse_index_frame(
        _parquet(frame), BENCHMARK_FRAME_COLUMNS[("chinabond", "index_daily")],
        dt.date(2026, 1, 2), dt.date(2026, 1, 3),
    )
    assert parsed.values == [ParsedIndexValue(dt.date(2026, 1, 3), Decimal("101.50000000"))]
    assert (parsed.fetched_row_count, parsed.null_count) == (4, 1)


def test_parse_csindex_basic_dates_and_akshare_iso_dates():
    csi = pd.DataFrame({"tradeDate": ["20260105", "20260106"], "close": [3500.12, 3510.0]})
    parsed = parse_index_frame(
        _parquet(csi), BENCHMARK_FRAME_COLUMNS[("csindex", "index_daily")], None, END
    )
    assert [item.effective_at for item in parsed.values] == [
        dt.date(2026, 1, 5), dt.date(2026, 1, 6)
    ]
    hk = pd.DataFrame({"date": ["2026-01-05"], "open": [1.0], "latest": [20000.5]})
    parsed = parse_index_frame(
        _parquet(hk), BENCHMARK_FRAME_COLUMNS[("akshare", "hk_index_daily")], None, END
    )
    assert parsed.values == [ParsedIndexValue(dt.date(2026, 1, 5), Decimal("20000.50000000"))]


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        (pd.DataFrame({"date": ["2026-01-05"], "value": [0.0]}), "必须为正"),
        (pd.DataFrame({"date": ["2026-01-05"], "value": [-1.0]}), "必须为正"),
        (pd.DataFrame({"date": ["2026-01-05", "2026-01-05"], "value": [1.0, 2.0]}), "重复"),
        (pd.DataFrame({"day": ["2026-01-05"], "value": [1.0]}), "缺少必需列"),
    ],
)
def test_parse_rejects_contract_violations(frame, message):
    with pytest.raises(BenchmarkDataError, match=message):
        parse_index_frame(
            _parquet(frame), BENCHMARK_FRAME_COLUMNS[("chinabond", "index_daily")], None, END
        )


def test_zero_schema_frame_is_an_empty_result():
    parsed = parse_index_frame(
        _parquet(pd.DataFrame()), BENCHMARK_FRAME_COLUMNS[("csindex", "index_daily")], None, END
    )
    assert parsed.values == [] and parsed.fetched_row_count == 0


# ---------- 版本规则 ----------


class _ValueSession:
    """仅支撑 write_index_values 的假会话：scalars 返回既有版本，add 收集新行。"""

    def __init__(self, existing: list[Any]) -> None:
        self.existing = existing
        self.added: list[Any] = []

    def scalars(self, _stmt: object) -> list[Any]:
        return sorted(self.existing, key=lambda row: (row.effective_at, row.version))

    def add(self, row: Any) -> None:
        self.added.append(row)

    def flush(self) -> None:
        return None


def test_unchanged_value_does_not_create_version_and_changed_value_bumps_version():
    existing = [
        SimpleNamespace(effective_at=dt.date(2026, 1, 5), version=1, value=Decimal("100")),
        SimpleNamespace(effective_at=dt.date(2026, 1, 6), version=1, value=Decimal("101")),
        SimpleNamespace(effective_at=dt.date(2026, 1, 6), version=2, value=Decimal("101.5")),
    ]
    session = _ValueSession(existing)
    record = _record(pd.DataFrame({"date": [], "value": []}))
    result = write_index_values(
        session,  # type: ignore[arg-type]
        7,
        [
            ParsedIndexValue(dt.date(2026, 1, 5), Decimal("100.00000000")),
            ParsedIndexValue(dt.date(2026, 1, 6), Decimal("101.60000000")),
            ParsedIndexValue(dt.date(2026, 1, 7), Decimal("102.00000000")),
        ],
        record,
    )
    assert (result.inserted_count, result.unchanged_count) == (2, 1)
    versions = {(row.effective_at, row.version) for row in session.added}
    assert versions == {(dt.date(2026, 1, 6), 3), (dt.date(2026, 1, 7), 1)}
    for row in session.added:
        # 三类数据源都没有发布 / 推送时刻：可得时间取落库时刻，质量 INFERRED。
        assert row.availability_quality == "INFERRED"
        assert row.published_at is None and row.provider_available_at is None
        assert row.available_at == NOW and row.ingested_at == NOW
        assert row.index_id == 7


def test_available_at_is_never_before_effective_date():
    session = _ValueSession([])
    record = _record(pd.DataFrame({"date": [], "value": []}))
    write_index_values(
        session,  # type: ignore[arg-type]
        1,
        [ParsedIndexValue(dt.date(2026, 11, 14), Decimal("1"))],
        record,
    )
    assert session.added[0].available_at == dt.datetime(2026, 11, 14, tzinfo=dt.UTC)


# ---------- 单指数抓取分派 ----------


class _FakeAdapter:
    adapter_version = "test"

    def __init__(self, source: str, frame: pd.DataFrame | None, error: Exception | None = None):
        self.provider_code = source.upper()
        self.frame = frame
        self.error = error
        self.calls: list[tuple[str, dict[str, str]]] = []

    def fetch(self, dataset: str, **params: str) -> SourceRecord:
        self.calls.append((dataset, params))
        if self.error is not None:
            raise self.error
        assert self.frame is not None
        return _record(self.frame, dataset)


class _IngestSession(_ValueSession):
    def __init__(self, index: Any) -> None:
        super().__init__([])
        self.index = index

    def scalar(self, _stmt: object) -> Any:
        return self.index

    def begin_nested(self) -> contextlib.AbstractContextManager[None]:
        return contextlib.nullcontext()


class _FakeIngestService:
    stored: list[SourceRecord] = []

    def __init__(self, *_args: object) -> None:
        return None

    def _store_raw(self, record: SourceRecord) -> SimpleNamespace:
        self.stored.append(record)
        return SimpleNamespace(id=len(self.stored))


@pytest.fixture()
def fake_raw(monkeypatch):
    from fip.services.data_service import ingest

    _FakeIngestService.stored = []
    monkeypatch.setattr(ingest, "IngestService", _FakeIngestService)
    return _FakeIngestService


@pytest.mark.parametrize(
    ("source", "api", "param", "frame", "expected_call"),
    [
        (
            "csindex", None, None,
            pd.DataFrame({"tradeDate": ["20260105"], "close": [3500.0]}),
            ("index_daily", {"indexCode": "000906", "startDate": "20260101",
                             "endDate": "20261113"}),
        ),
        (
            "chinabond", None, {"index_type": "CFZS", "period_type": "03"},
            pd.DataFrame({"date": [dt.date(2026, 1, 5)], "value": [210.0]}),
            ("index_daily", {"code": "000906", "index_type": "CFZS", "period_type": "03"}),
        ),
        (
            "akshare", "stock_hk_index_daily_em", None,
            pd.DataFrame({"date": ["2025-12-31", "2026-01-05"], "latest": [1.0, 20000.0]}),
            ("hk_index_daily", {"symbol": "000906"}),
        ),
    ],
)
def test_ingest_dispatches_each_source_to_its_adapter(
    fake_raw, source, api, param, frame, expected_call
):
    adapters: dict[str, _FakeAdapter] = {}

    def factory(name: str) -> _FakeAdapter:
        adapters[name] = _FakeAdapter(name, frame)
        return adapters[name]

    index = SimpleNamespace(id=3, source=source, provider_code="000906", api=api, param=param)
    session = _IngestSession(index)
    result = benchmark_values.ingest_benchmark_index(
        session,  # type: ignore[arg-type]
        3,
        start_date=dt.date(2026, 1, 1),
        end_date=END,
        adapter_factory=factory,  # type: ignore[arg-type]
    )
    assert list(adapters) == [source]
    assert adapters[source].calls == [expected_call]
    assert result == {
        "source": source,
        "dataset": expected_call[0],
        "row_count": 1,
        "inserted_count": 1,
        "unchanged_count": 0,
        "first_date": "2026-01-05",
        "last_date": "2026-01-05",
        "fetched_row_count": len(frame),
        "null_count": 0,
        "raw_payload_id": 1,
    }
    assert len(fake_raw.stored) == 1


def test_parse_failure_keeps_raw_payload_and_reports_source(fake_raw):
    frame = pd.DataFrame({"date": ["2026-01-05"], "latest": [-5.0]})
    index = SimpleNamespace(
        id=3, source="akshare", provider_code="HSI", api="stock_hk_index_daily_em", param=None
    )
    with pytest.raises(BenchmarkDataError) as caught:
        benchmark_values.ingest_benchmark_index(
            _IngestSession(index),  # type: ignore[arg-type]
            3,
            start_date=None,
            end_date=END,
            adapter_factory=lambda name: _FakeAdapter(name, frame),  # type: ignore[arg-type,return-value]
        )
    assert caught.value.benchmark_source == "akshare"  # type: ignore[attr-defined]
    assert caught.value.benchmark_dataset == "hk_index_daily"  # type: ignore[attr-defined]
    assert fake_raw.stored  # 回滚后仍单独留存原始返回


# ---------- 任务 handler ----------


class _HandlerSession:
    """支撑 handle_benchmark_ingestion 的假会话：按语句类型模拟项表操作。"""

    def __init__(self, items: list[Any]) -> None:
        self.items = items

    def scalars(self, _stmt: object) -> list[Any]:
        return [item for item in self.items if item.status == "PENDING"][:20]

    def execute(self, stmt: object) -> Any:
        if isinstance(stmt, Update):
            for item in self.items:
                if item.status == "PENDING":
                    item.status = "CANCELLED"
            return None
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.status] = counts.get(item.status, 0) + 1
        return SimpleNamespace(all=lambda: list(counts.items()))

    def flush(self) -> None:
        return None


def _item(index_id: int, status: str = "PENDING") -> SimpleNamespace:
    return SimpleNamespace(
        benchmark_index_id=index_id, status=status, attempts=0, result=None, error=None,
        started_at=None, finished_at=None,
    )


def _context(items: list[Any], **payload: Any) -> Any:
    from fip.platform.jobs.executor import JobContext

    job = SimpleNamespace(
        execution_id="bm-op",
        result_ref="/api/v1/ingestions/bm-op",
        progress=0,
        result_payload=None,
        job_payload={
            "dataset": "BENCHMARK",
            "actor": "alice",
            "scoped_items": True,
            "start_date": "2026-01-01",
            "end_date": "2026-11-13",
            **payload,
        },
    )
    return JobContext(job=job, session=_HandlerSession(items), worker_id="w", now=NOW)  # type: ignore[arg-type]


def test_handler_isolates_item_failures_and_marks_timeouts_retryable(monkeypatch):
    from fip.platform.jobs.benchmark_ingestion import handle_benchmark_ingestion

    calls: list[tuple[int, dt.date | None, dt.date]] = []

    def fake_ingest(_session, index_id, *, start_date, end_date, adapter_factory):
        calls.append((index_id, start_date, end_date))
        if index_id == 2:
            raise httpx.ReadTimeout("read timed out")
        if index_id == 3:
            raise BenchmarkConfigError("中债基准指数 param 缺少 index_type")
        return {"source": "csindex", "dataset": "index_daily", "row_count": 2,
                "inserted_count": 2, "unchanged_count": 0,
                "first_date": "2026-01-05", "last_date": "2026-01-06"}

    monkeypatch.setattr(benchmark_values, "ingest_benchmark_index", fake_ingest)
    items = [_item(1), _item(2), _item(3), _item(4, "SKIPPED")]
    context = _context(items)
    outcome = handle_benchmark_ingestion(context)

    assert calls == [(i, dt.date(2026, 1, 1), dt.date(2026, 11, 13)) for i in (1, 2, 3)]
    assert [item.status for item in items] == ["SUCCESS", "FAILED", "FAILED", "SKIPPED"]
    assert items[0].result["inserted_count"] == 2 and items[0].attempts == 1
    assert items[1].result["retryable"] is True
    assert items[1].result["error_code"] == "PROVIDER_TEMPORARY_FAILURE"
    assert "retryable" not in items[2].result
    assert items[2].error == "BenchmarkConfigError: 中债基准指数 param 缺少 index_type"
    assert outcome.status == "COMPLETED"
    assert context.job.result_payload == {
        "dataset": "BENCHMARK",
        "requested_count": 4,
        "success_count": 1,
        "failure_count": 2,
        "skipped_count": 1,
        "cancelled_count": 0,
        "task_status": "PARTIAL_SUCCESS",
    }
    assert context.job.progress == 4


def test_handler_processes_bounded_chunks_until_done(monkeypatch):
    from fip.platform.jobs.benchmark_ingestion import handle_benchmark_ingestion

    monkeypatch.setattr(
        benchmark_values,
        "ingest_benchmark_index",
        lambda *_a, **_k: {"source": "csindex", "dataset": "index_daily"},
    )
    items = [_item(i) for i in range(25)]
    context = _context(items)
    assert handle_benchmark_ingestion(context).status == "RUNNING"
    assert sum(item.status == "SUCCESS" for item in items) == 20
    outcome = handle_benchmark_ingestion(context)
    assert outcome.status == "COMPLETED"
    assert context.job.result_payload["task_status"] == "SUCCESS"


def test_handler_cancels_pending_items(monkeypatch):
    from fip.platform.jobs.benchmark_ingestion import handle_benchmark_ingestion

    def fail(*_a, **_k):
        raise AssertionError("取消后不得再抓取")

    monkeypatch.setattr(benchmark_values, "ingest_benchmark_index", fail)
    items = [_item(1, "SUCCESS"), _item(2), _item(3)]
    context = _context(items, cancel_requested=True)
    outcome = handle_benchmark_ingestion(context)
    assert outcome.status == "CANCELLED"
    assert [item.status for item in items] == ["SUCCESS", "CANCELLED", "CANCELLED"]
    assert context.job.result_payload["cancelled_count"] == 2


def test_handler_fails_when_nothing_succeeds(monkeypatch):
    from fip.platform.jobs.benchmark_ingestion import handle_benchmark_ingestion

    def boom(*_a, **_k):
        raise BenchmarkDataError("指数值必须为正")

    monkeypatch.setattr(benchmark_values, "ingest_benchmark_index", boom)
    context = _context([_item(1)])
    outcome = handle_benchmark_ingestion(context)
    assert outcome.status == "FAILED"
    assert context.job.result_payload["task_status"] == "FAILED"


def test_handler_rejects_invalid_payload_dates():
    from fip.platform.jobs.benchmark_ingestion import handle_benchmark_ingestion

    outcome = handle_benchmark_ingestion(_context([], start_date="2026-12-01"))
    assert outcome.status == "FAILED" and outcome.error_code == "INVALID_INGESTION_REQUEST"
    outcome = handle_benchmark_ingestion(_context([], end_date=None))
    assert outcome.status == "FAILED"


def test_worker_registers_benchmark_handler():
    from fip.platform.jobs.benchmark_ingestion import handle_benchmark_ingestion
    from fip.platform.jobs.worker import _job_executor

    executor = _job_executor()
    assert executor._handlers["benchmark_index_ingest"] is handle_benchmark_ingestion
