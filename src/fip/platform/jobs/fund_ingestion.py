from __future__ import annotations

from typing import Any

from fip.platform.jobs.executor import JobContext, JobOutcome


class _CapturingAdapter:
    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped
        self.records: list[Any] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def fetch(self, dataset: str, **params: str) -> Any:
        try:
            record = self._wrapped.fetch(dataset, **params)
        except Exception as error:
            record = getattr(error, "record", None)
            if record is not None:
                self.records.append(record)
            raise
        self.records.append(record)
        return record


def handle_fund_ingestion(context: JobContext) -> JobOutcome:
    """Run a persisted basic-info or NAV refresh request.

    Service imports stay inside the handler so the platform layer remains free
    of module-level dependencies on the services layer.
    """
    payload = context.job.job_payload or {}
    if payload.get("scoped_items"):
        return _handle_scoped_ingestion(context)
    dataset = payload.get("dataset")
    actor = payload.get("actor")
    subjects = payload.get("subjects")
    if dataset not in {"BASIC_INFO", "NAV"} or not isinstance(actor, str):
        return JobOutcome.failed("INVALID_INGESTION_REQUEST", "Invalid ingestion request payload")
    if not isinstance(subjects, list) or not subjects:
        return JobOutcome.failed("INVALID_INGESTION_REQUEST", "No mapped share classes to ingest")

    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.ingest import IngestService

    adapter = AkShareSourceAdapter()
    session = context.session
    outcomes: list[dict[str, Any]] = []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        share_class_id = subject.get("share_class_id")
        symbol = subject.get("symbol")
        fund_id = subject.get("fund_id")
        public_fund_id = subject.get("public_fund_id")
        if (
            not isinstance(share_class_id, int)
            or not isinstance(fund_id, int)
            or not isinstance(symbol, str)
        ):
            outcomes.append({"status": "FAILED", "error": "Invalid share class mapping"})
            continue
        try:
            capture = _CapturingAdapter(adapter)
            with session.begin_nested():
                if dataset == "BASIC_INFO":
                    snapshot = IngestService(session, capture, None).ingest_fund_overview(
                        fund_id, symbol, actor=actor
                    )
                    from sqlalchemy import select

                    from fip.services.data_service.models.fund import FundBasicInfoHistory

                    current = session.execute(
                        select(FundBasicInfoHistory)
                        .where(FundBasicInfoHistory.fund_id == fund_id)
                        .order_by(FundBasicInfoHistory.version.desc())
                        .limit(1)
                    ).scalar_one()
                    detail: dict[str, Any] = {
                        "basic_info_version": current.version,
                        "basic_info_raw_payload_id": current.raw_payload_id,
                        "field_count": len(current.normalized_fields),
                        "available_at": current.available_at.isoformat(),
                        "availability_quality": current.availability_quality,
                        "classification": snapshot.to_dict(),
                    }
                else:
                    ingest = IngestService.from_policy(session, capture, rule_version="v1")
                    nav_versions = ingest.ingest_nav(share_class_id, symbol)
                    event_versions = ingest.ingest_distributions(share_class_id, symbol)
                    adjusted_versions = ingest.rebuild_adjusted_nav(
                        share_class_id, context.now.date()
                    )
                    from sqlalchemy import func, select

                    from fip.services.data_service.models.market import FundNav

                    latest_effective_at = session.scalar(
                        select(func.max(FundNav.effective_at)).where(
                            FundNav.share_class_id == share_class_id
                        )
                    )
                    detail = {
                        "nav_versions_created": nav_versions,
                        "corporate_action_versions_created": event_versions,
                        "adjusted_nav_rows_rebuilt": adjusted_versions,
                        "latest_effective_at": (
                            latest_effective_at.isoformat() if latest_effective_at else None
                        ),
                    }
        except Exception as error:  # task result must preserve item-level failure detail
            if capture.records:
                raw_service = IngestService(session, adapter, None)
                for record in capture.records:
                    with session.begin_nested():
                        raw_service._store_raw(record)
            outcomes.append(
                {
                    "fund_id": public_fund_id if isinstance(public_fund_id, str) else fund_id,
                    "share_class_id": share_class_id,
                    "symbol": symbol,
                    "status": "FAILED",
                    "error": f"{type(error).__name__}: {error}",
                }
            )
        else:
            outcomes.append(
                {
                    "fund_id": public_fund_id if isinstance(public_fund_id, str) else fund_id,
                    "share_class_id": share_class_id,
                    "symbol": symbol,
                    "status": "SUCCESS",
                    **detail,
                }
            )

    successes = sum(item.get("status") == "SUCCESS" for item in outcomes)
    failures = len(outcomes) - successes
    task_status = "FAILED" if successes == 0 else "PARTIAL_SUCCESS" if failures else "SUCCESS"
    context.job.result_payload = {
        "dataset": dataset,
        "task_status": task_status,
        "requested_count": len(subjects),
        "success_count": successes,
        "failure_count": failures,
        "items": outcomes,
    }
    context.job.progress = len(outcomes)
    if successes == 0:
        first_error = next(
            (str(item.get("error")) for item in outcomes if item.get("error")),
            "No ingestion items succeeded",
        )
        return JobOutcome.failed("INGESTION_FAILED", first_error)
    return JobOutcome.completed(result_ref=f"/api/v1/ingestions/{context.job.execution_id}")


def _run_scoped_chunk(context: JobContext, subjects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    job = context.job
    original_payload, original_result, original_progress = (
        job.job_payload,
        job.result_payload,
        job.progress,
    )
    try:
        job.job_payload = {**(original_payload or {}), "scoped_items": False, "subjects": subjects}
        handle_fund_ingestion(context)
        result = job.result_payload or {}
        raw_items = result.get("items", [])
        return (
            [item for item in raw_items if isinstance(item, dict)]
            if isinstance(raw_items, list)
            else []
        )
    finally:
        job.job_payload, job.result_payload, job.progress = (
            original_payload,
            original_result,
            original_progress,
        )


def _handle_scoped_ingestion(context: JobContext) -> JobOutcome:
    from sqlalchemy import func, select, update

    from fip.services.data_service.models.fund_ingestion import FundIngestionRunItem

    job = context.job
    session = context.session
    items = list(
        session.scalars(
            select(FundIngestionRunItem)
            .where(
                FundIngestionRunItem.operation_id == job.execution_id,
                FundIngestionRunItem.status == "PENDING",
            )
            .order_by(FundIngestionRunItem.id)
            .limit(50)
        )
    )
    if (job.job_payload or {}).get("cancel_requested"):
        session.execute(
            update(FundIngestionRunItem)
            .where(
                FundIngestionRunItem.operation_id == job.execution_id,
                FundIngestionRunItem.status == "PENDING",
            )
            .values(status="CANCELLED", finished_at=context.now)
        )
        items = []
    if items:
        subjects = [
            {
                "fund_id": item.fund_id,
                "public_fund_id": item.public_fund_id,
                "share_class_id": item.share_class_id,
                "symbol": item.symbol,
            }
            for item in items
        ]
        results = _run_scoped_chunk(context, subjects)
        if len(results) != len(items):
            raise RuntimeError("Ingestion chunk returned an unexpected number of results")
        for item, result in zip(items, results, strict=True):
            item.attempts += 1
            item.started_at = context.now
            item.finished_at = context.now
            item.status = str(result.get("status", "FAILED"))
            if _is_transient_result(result):
                result["error_code"] = "PROVIDER_TEMPORARY_FAILURE"
                result["retryable"] = True
            item.result = result
            item.error = str(result["error"]) if result.get("error") else None
    session.flush()
    counts: dict[str, int] = {
        status: count
        for status, count in session.execute(
            select(FundIngestionRunItem.status, func.count())
            .where(FundIngestionRunItem.operation_id == job.execution_id)
            .group_by(FundIngestionRunItem.status)
        ).all()
    }
    successes = counts.get("SUCCESS", 0)
    failures = counts.get("FAILED", 0)
    skipped = counts.get("SKIPPED", 0)
    cancelled = counts.get("CANCELLED", 0)
    job.progress = successes + failures + skipped + cancelled
    job.result_payload = {
        "dataset": (job.job_payload or {}).get("dataset"),
        "requested_count": sum(counts.values()),
        "success_count": successes,
        "failure_count": failures,
        "skipped_count": skipped,
        "cancelled_count": cancelled,
    }
    if counts.get("PENDING", 0):
        return JobOutcome.running()
    if (job.job_payload or {}).get("cancel_requested"):
        return JobOutcome("CANCELLED", result_ref=job.result_ref)
    summary = "FAILED" if not successes else "PARTIAL_SUCCESS" if failures or skipped else "SUCCESS"
    job.result_payload = {**job.result_payload, "task_status": summary}
    if summary == "FAILED":
        return JobOutcome.failed("INGESTION_FAILED", "No ingestion items succeeded")
    return JobOutcome.completed(result_ref=job.result_ref)


def _is_transient_result(result: dict[str, Any]) -> bool:
    error = result.get("error")
    return (
        result.get("status") == "FAILED"
        and isinstance(error, str)
        and error.startswith(
            (
                "TimeoutExpired:",
                "TimeoutError:",
                "Timeout:",
                "ReadTimeout:",
                "ConnectTimeout:",
                "ConnectionError:",
            )
        )
    )
