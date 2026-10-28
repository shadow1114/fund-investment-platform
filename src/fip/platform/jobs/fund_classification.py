"""Bounded classification source jobs; HTTP handlers only enqueue these jobs."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from fip.platform.jobs.executor import JobContext, JobOutcome

if TYPE_CHECKING:
    from fip.services.data_service.classification.models import Evidence


def _latest_payload(session: Any, dataset_code: str, *, symbol: str | None = None) -> Any:
    from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
    from fip.services.data_service.models.raw import RawPayload

    rows = session.scalars(
        select(RawPayload)
        .join(DataProviderDataset, DataProviderDataset.id == RawPayload.dataset_id)
        .join(DataProvider, DataProvider.id == DataProviderDataset.provider_id)
        .where(
            DataProvider.provider_code == "AKSHARE",
            DataProviderDataset.dataset_code == dataset_code,
        )
        .order_by(RawPayload.ingested_at.desc(), RawPayload.id.desc())
    )
    for row in rows:
        if symbol is None or row.request_params.get("symbol") == symbol:
            return row
    return None


def _store_record(session: Any, adapter: Any, record: Any) -> Any:
    from fip.services.data_service.ingest import IngestService

    return IngestService(session, adapter, None)._store_raw(record)


def _refresh_index_sets(context: JobContext, actor: str) -> JobOutcome:
    from fip.services.data_service.adapters.akshare.classification_sources import (
        INDEX_DATASETS,
        collect_index_batches,
    )
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter

    adapter = AkShareSourceAdapter()
    refs = {indicator: f"pending:{indicator}" for indicator in INDEX_DATASETS.values()}
    batches = collect_index_batches(adapter, batch_id=context.job.execution_id, payload_refs=refs)
    items = []
    successful = 0
    for batch in batches:
        raw_id = None
        batch_error = None
        if batch.record is not None:
            try:
                raw_id = _store_record(context.session, adapter, batch.record).id
                successful += batch.state not in {"FAILED", "MALFORMED"}
            except Exception as error:
                batch_error = f"PERSIST_FAILED:{type(error).__name__}:{error}"
            else:
                batch_error = None
        else:
            batch_error = None
        items.append(
            {
                "dataset": next(
                    (
                        name
                        for name, indicator in INDEX_DATASETS.items()
                        if indicator == batch.indicator
                    ),
                    None,
                ),
                "indicator": batch.indicator,
                "state": batch.state,
                "row_count": batch.row_count,
                "payload_id": raw_id,
                "may_withdraw_prior": batch.may_withdraw_prior,
                "diagnostics": [*batch.diagnostics, *([batch_error] if batch_error else [])],
                "published_at": batch.published_at.isoformat() if batch.published_at else None,
                "provider_available_at": (
                    batch.provider_available_at.isoformat() if batch.provider_available_at else None
                ),
                "ingested_at": batch.source_timestamp.isoformat()
                if batch.source_timestamp
                else None,
            }
        )
    context.job.result_payload = {
        "action": "refresh_index_sets",
        "actor": actor,
        "task_status": "SUCCESS" if successful == len(batches) else "PARTIAL_SUCCESS",
        "items": items,
    }
    context.job.progress = len(batches)
    # A partial source refresh is a completed bounded operation; detailed source
    # status stays in result_payload and is not retried as a whole batch.
    return JobOutcome.completed(
        result_ref=f"classification-index-batches:{context.job.execution_id}"
    )


def _existing_index_evidence(
    session: Any, symbol: str
) -> tuple[tuple[Evidence, ...], tuple[str, ...], dict[str, Any]]:
    from fip.services.data_service.adapters.akshare.classification_sources import (
        parse_index_batch,
        source_record_from_payload,
    )

    evidence: list[Evidence] = []
    diagnostics: list[str] = []
    freshness: dict[str, Any] = {}
    for dataset in ("fund_index_passive", "fund_index_enhanced"):
        payload = _latest_payload(session, dataset)
        if payload is None:
            diagnostics.append(f"INDEX_BATCH_MISSING:{dataset}")
            freshness[dataset] = {"state": "MISSING"}
            continue
        batch = parse_index_batch(
            source_record_from_payload(payload, dataset=dataset),
            batch_id=f"saved:{payload.id}",
            payload_ref=f"raw_payload:{payload.id}",
        )
        evidence.extend(item for item in batch.evidence if item.raw_value == symbol)
        freshness[dataset] = {
            "state": batch.state,
            "payload_id": payload.id,
            "row_count": batch.row_count,
            "ingested_at": batch.source_timestamp.isoformat() if batch.source_timestamp else None,
            "may_withdraw_prior": batch.may_withdraw_prior,
        }
        if batch.state != "COMPLETE":
            diagnostics.extend(f"{dataset}:{item}" for item in batch.diagnostics or (batch.state,))
    return tuple(evidence), tuple(diagnostics), freshness


def _refresh_fund(context: JobContext, payload: dict[str, Any]) -> JobOutcome:
    from fip.services.data_service.adapters.akshare.classification_sources import (
        parse_fund_overview_observations,
        parse_snowball_detail,
        source_record_from_payload,
    )
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.classification.service import ClassificationService
    from fip.services.data_service.classification.workflow import (
        classify_v3_preview,
        merge_snapshot_observations,
        preview_classification,
        should_fetch_snowball,
    )
    from fip.services.data_service.ingest import IngestService

    fund_id, symbol, actor = payload.get("fund_id"), payload.get("symbol"), payload.get("actor")
    if type(fund_id) is not int or not isinstance(symbol, str) or not isinstance(actor, str):
        return JobOutcome.failed("INVALID_CLASSIFICATION_REQUEST", "Invalid fund refresh payload")
    if len(symbol) != 6 or not symbol.isdigit() or not actor.strip():
        return JobOutcome.failed("INVALID_CLASSIFICATION_REQUEST", "Invalid symbol or actor")

    session = context.session
    adapter = AkShareSourceAdapter()
    ingest = IngestService(session, adapter, None)
    diagnostics: list[str] = []
    new_records = []
    new_evidence: list[Evidence] = []
    source_freshness: dict[str, Any] = {}

    # Reuse saved overview data for up to 30 days; otherwise make one isolated call.
    overview_payload = _latest_payload(session, "fund_overview", symbol=symbol)
    if overview_payload is not None and context.now - overview_payload.ingested_at <= dt.timedelta(
        days=30
    ):
        overview_record = source_record_from_payload(overview_payload, dataset="fund_overview")
        source_freshness["fund_overview"] = {
            "state": "REUSED",
            "payload_id": overview_payload.id,
            "ingested_at": overview_payload.ingested_at.isoformat(),
        }
    else:
        try:
            overview_record = adapter.fetch("fund_overview", symbol=symbol)
            overview_payload = ingest._store_raw(overview_record)
            new_records.append(overview_record)
            source_freshness["fund_overview"] = {
                "state": "REFRESHED",
                "payload_id": overview_payload.id,
                "ingested_at": overview_record.ingested_at.isoformat(),
            }
        except Exception as error:
            failed_record = getattr(error, "record", None)
            if failed_record is not None:
                stored_error = ingest._store_raw(failed_record)
                source_freshness["fund_overview"] = {
                    "state": "FAILED_WITH_DIAGNOSTIC_PAYLOAD",
                    "payload_id": stored_error.id,
                }
            else:
                source_freshness["fund_overview"] = {"state": "FAILED"}
            diagnostics.append(f"fund_overview:{type(error).__name__}:{error}")
            overview_record = None
    if overview_record is not None and overview_payload is not None:
        try:
            new_evidence.extend(
                parse_fund_overview_observations(
                    overview_record,
                    payload_ref=f"raw_payload:{overview_payload.id}",
                    symbol=symbol,
                )
            )
        except Exception as error:
            diagnostics.append(f"fund_overview:PARSE_FAILED:{type(error).__name__}:{error}")

    membership, membership_diagnostics, index_freshness = _existing_index_evidence(session, symbol)
    new_evidence.extend(membership)
    diagnostics.extend(membership_diagnostics)
    source_freshness.update(index_freshness)
    service = ClassificationService(session)
    previous = service.latest(fund_id)
    baseline = None
    if previous:
        baseline_interval = next(
            (
                item
                for item in service.intervals(previous.id)
                if item[0] <= context.now.date()
                and (item[1] is None or context.now.date() < item[1])
            ),
            None,
        )
        baseline = baseline_interval[2] if baseline_interval else None
    evidence = merge_snapshot_observations(baseline, new_evidence)
    available_at = max((item.classified_at for item in evidence), default=context.now)
    proposed = classify_v3_preview(
        evidence,
        available_at=available_at,
        baseline=baseline,
        baseline_revision_id=previous.id if previous else None,
    )
    fetch_detail = should_fetch_snowball(proposed, available_at=context.now)
    if fetch_detail:
        try:
            detail_record = adapter.fetch("fund_detail_xq", symbol=symbol)
            detail_payload = ingest._store_raw(detail_record)
            new_records.append(detail_record)
            parsed = parse_snowball_detail(
                detail_record, payload_ref=f"raw_payload:{detail_payload.id}"
            )
            source_freshness["fund_detail_xq"] = {
                "state": parsed.state,
                "payload_id": detail_payload.id,
                "ingested_at": detail_record.ingested_at.isoformat(),
                "field_states": parsed.field_states,
            }
            new_evidence.extend(parsed.evidence)
            diagnostics.extend(parsed.diagnostics)
        except Exception as error:
            failed_record = getattr(error, "record", None)
            if failed_record is not None:
                detail_payload = ingest._store_raw(failed_record)
                source_freshness["fund_detail_xq"] = {
                    "state": "FAILED_WITH_DIAGNOSTIC_PAYLOAD",
                    "payload_id": detail_payload.id,
                }
            else:
                source_freshness["fund_detail_xq"] = {"state": "FAILED"}
            diagnostics.append(f"fund_detail_xq:{type(error).__name__}:{error}")
    else:
        source_freshness["fund_detail_xq"] = {
            "state": "NOT_REQUESTED",
            "reason": "strategy current and QUANTITATIVE tag evaluated",
        }

    merged = merge_snapshot_observations(baseline, new_evidence)
    available_at = max((item.classified_at for item in merged), default=context.now)
    final_snapshot = classify_v3_preview(
        merged,
        available_at=available_at,
        baseline=baseline,
        baseline_revision_id=previous.id if previous else None,
    )
    preview = preview_classification(
        final_snapshot,
        baseline=baseline,
        baseline_reviewed=bool(previous and previous.reviewed),
    )
    revision_id = None
    if preview.action != "NO_CHANGE":
        ingested_at = max((record.ingested_at for record in new_records), default=None)
        committed_available_at = max(context.now, ingested_at) if ingested_at else context.now
        revision = service.refresh_v3(
            fund_id,
            new_evidence,
            available_at=max(available_at, committed_available_at),
            actor=actor,
            reason="bounded classification refresh",
            diagnostics=diagnostics,
            ingested_at=ingested_at,
        )
        revision_id = revision.id
    context.job.result_payload = {
        "action": "refresh_fund",
        "actor": actor,
        "fund_id": fund_id,
        "symbol": symbol,
        "decision": preview.action,
        "revision_id": revision_id,
        "rule_version": final_snapshot.rule_version,
        "enum_version": final_snapshot.enum_version,
        "classification": final_snapshot.to_dict(),
        "source_freshness": source_freshness,
        "diagnostics": diagnostics,
        "paused_dimensions": ["geography", "product_structure", "market_attributes"],
    }
    context.job.progress = 1
    return JobOutcome.completed(result_ref=f"classification:{fund_id}:{revision_id or 'no-change'}")


def handle_fund_classification(context: JobContext) -> JobOutcome:
    """Dispatch a single bounded fund refresh or one centralized two-set refresh."""
    payload = context.job.job_payload or {}
    action = payload.get("action")
    actor = payload.get("actor")
    if not isinstance(actor, str) or not actor.strip():
        return JobOutcome.failed("INVALID_CLASSIFICATION_REQUEST", "Missing actor")
    if action == "refresh_index_sets":
        return _refresh_index_sets(context, actor)
    if action == "refresh_fund":
        return _refresh_fund(context, payload)
    return JobOutcome.failed("INVALID_CLASSIFICATION_REQUEST", "Unknown classification action")
