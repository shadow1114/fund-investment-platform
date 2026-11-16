"""基准行情数据抓取任务：按项分块推进 benchmark_ingestion_run_item。

服务层依赖一律在函数内导入，保持 platform 层不在模块级依赖 services 层。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from fip.platform.jobs.executor import JobContext, JobOutcome
from fip.platform.jobs.fund_ingestion import _is_transient_result

BENCHMARK_INGESTION_JOB_TYPE = "benchmark_index_ingest"
BENCHMARK_CHUNK_SIZE = 20

# 测试可替换的适配器工厂：source → SourceAdapter。None 表示使用真实适配器。
AdapterFactory = Callable[[str], Any]


def _parse_payload_date(value: object) -> dt.date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"任务载荷中的日期必须是 ISO 字符串：{value!r}")
    return dt.date.fromisoformat(value)


def _is_transient_error(error: BaseException) -> bool:
    """网络超时、连接中断、上游 5xx / 429 视为临时故障，可人工重试。"""
    import httpx
    import requests

    if isinstance(error, TimeoutError | ConnectionError):
        return True
    if isinstance(
        error,
        httpx.TimeoutException
        | httpx.NetworkError
        | httpx.RemoteProtocolError
        | requests.exceptions.Timeout
        | requests.exceptions.ConnectionError,
    ):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        return code == 429 or code >= 500
    return False


def handle_benchmark_ingestion(
    context: JobContext, *, adapter_factory: AdapterFactory | None = None
) -> JobOutcome:
    """处理一块（至多 20 条）PENDING 项；仍有剩余时返回 RUNNING 由 worker 继续领取。"""
    from sqlalchemy import func, select, update

    from fip.services.data_service.benchmark_values import (
        default_adapter_factory,
        ingest_benchmark_index,
    )
    from fip.services.data_service.models.fund_ingestion import BenchmarkIngestionRunItem

    job = context.job
    session = context.session
    payload = job.job_payload or {}
    try:
        start_date = _parse_payload_date(payload.get("start_date"))
        end_date = _parse_payload_date(payload.get("end_date"))
    except ValueError as error:
        return JobOutcome.failed("INVALID_INGESTION_REQUEST", f"基准抓取任务载荷无效：{error}")
    if end_date is None:
        return JobOutcome.failed("INVALID_INGESTION_REQUEST", "基准抓取任务缺少 end_date")
    if start_date is not None and start_date > end_date:
        return JobOutcome.failed("INVALID_INGESTION_REQUEST", "start_date 不能晚于 end_date")
    factory = adapter_factory or default_adapter_factory

    if payload.get("cancel_requested"):
        session.execute(
            update(BenchmarkIngestionRunItem)
            .where(
                BenchmarkIngestionRunItem.operation_id == job.execution_id,
                BenchmarkIngestionRunItem.status == "PENDING",
            )
            .values(status="CANCELLED", finished_at=context.now)
        )
        items: list[BenchmarkIngestionRunItem] = []
    else:
        items = list(
            session.scalars(
                select(BenchmarkIngestionRunItem)
                .where(
                    BenchmarkIngestionRunItem.operation_id == job.execution_id,
                    BenchmarkIngestionRunItem.status == "PENDING",
                )
                .order_by(BenchmarkIngestionRunItem.id)
                .limit(BENCHMARK_CHUNK_SIZE)
            )
        )
    for item in items:
        item.attempts += 1
        item.started_at = context.now
        try:
            # 单项独立执行：ingest_benchmark_index 自带 savepoint，失败只回滚本项写入。
            detail = ingest_benchmark_index(
                session,
                item.benchmark_index_id,
                start_date=start_date,
                end_date=end_date,
                adapter_factory=factory,
            )
        except Exception as error:  # 项级结果必须保留失败明细
            result: dict[str, Any] = {
                "status": "FAILED",
                "error": f"{type(error).__name__}: {error}",
            }
            source = getattr(error, "benchmark_source", None)
            dataset = getattr(error, "benchmark_dataset", None)
            if source is not None:
                result["source"] = source
            if dataset is not None:
                result["dataset"] = dataset
            if _is_transient_error(error) or _is_transient_result(result):
                result["error_code"] = "PROVIDER_TEMPORARY_FAILURE"
                result["retryable"] = True
            item.status = "FAILED"
            item.error = str(result["error"])
            item.result = result
        else:
            item.status = "SUCCESS"
            item.error = None
            item.result = {"status": "SUCCESS", **detail}
        item.finished_at = context.now
    session.flush()

    counts: dict[str, int] = {
        status: count
        for status, count in session.execute(
            select(BenchmarkIngestionRunItem.status, func.count())
            .where(BenchmarkIngestionRunItem.operation_id == job.execution_id)
            .group_by(BenchmarkIngestionRunItem.status)
        ).all()
    }
    successes = counts.get("SUCCESS", 0)
    failures = counts.get("FAILED", 0)
    skipped = counts.get("SKIPPED", 0)
    cancelled = counts.get("CANCELLED", 0)
    job.progress = successes + failures + skipped + cancelled
    job.result_payload = {
        "dataset": payload.get("dataset"),
        "requested_count": sum(counts.values()),
        "success_count": successes,
        "failure_count": failures,
        "skipped_count": skipped,
        "cancelled_count": cancelled,
    }
    if counts.get("PENDING", 0):
        return JobOutcome.running()
    if payload.get("cancel_requested"):
        return JobOutcome("CANCELLED", result_ref=job.result_ref)
    summary = "FAILED" if not successes else "PARTIAL_SUCCESS" if failures or skipped else "SUCCESS"
    job.result_payload = {**job.result_payload, "task_status": summary}
    if summary == "FAILED":
        return JobOutcome.failed("INGESTION_FAILED", "没有任何基准指数抓取成功")
    return JobOutcome.completed(result_ref=job.result_ref)
