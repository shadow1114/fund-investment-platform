from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any, Literal, cast

from fastapi import APIRouter, Body, Depends, Header, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from fip.api.auth import get_principal
from fip.api.context import Principal
from fip.api.contracts import success
from fip.api.errors import ConflictError, ForbiddenError, NotFoundError, ServiceUnavailableError
from fip.api.schemas import (
    FundBasicInfoHistoryModel,
    FundIngestionSubmissionModel,
    FundIngestionTaskModel,
    StrictModel,
    TypedEnvelope,
)
from fip.platform.jobs.models import CalculationJob
from fip.platform.jobs.submitter import JobSubmitter

# FastAPI's dependency/body declarations intentionally live in signatures.
# ruff: noqa: B008

router = APIRouter()


class FundIngestionRequest(StrictModel):
    dataset: Literal["BASIC_INFO", "NAV"]


class FundIngestionBatchRequest(StrictModel):
    dataset: Literal["BASIC_INFO", "NAV"]
    fund_ids: list[str]


def _session(request: Request) -> Session:
    return Session(request.app.state.api_engine, future=True)


def _can_read_job(principal: Principal, job: CalculationJob) -> bool:
    return principal.can_manage_data_ingestion or (
        (job.job_payload or {}).get("actor") == principal.user_id
    )


def _task_model(job: CalculationJob) -> FundIngestionTaskModel:
    payload = job.job_payload or {}
    result = job.result_payload or {}
    dataset = payload.get("dataset")
    if dataset not in {"BASIC_INFO", "NAV"}:
        raise ConflictError("Stored ingestion job has an unsupported dataset")
    raw_fund_ids = payload.get("fund_ids", [])
    raw_subjects = payload.get("subjects", [])
    raw_items = result.get("items", [])
    raw_status = job.status
    if raw_status not in {"RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED"}:
        raise ConflictError("Stored ingestion job has an unsupported status")
    raw_task_status = result.get("task_status")
    if raw_task_status not in {None, "SUCCESS", "PARTIAL_SUCCESS", "FAILED"}:
        raise ConflictError("Stored ingestion result has an unsupported status")
    raw_requested_count = result.get("requested_count")
    if not isinstance(raw_requested_count, int):
        raw_requested_count = len(raw_subjects) if isinstance(raw_subjects, list) else 0
    raw_success_count = result.get("success_count")
    raw_failure_count = result.get("failure_count")
    failure = job.error_detail if job.status in {"FAILED", "BLOCKED"} else None
    return FundIngestionTaskModel(
        operation_id=job.execution_id,
        fund_id=str(job.resource_id or ""),
        fund_ids=[str(value) for value in raw_fund_ids]
        if isinstance(raw_fund_ids, list)
        else [],
        dataset=cast(Literal["BASIC_INFO", "NAV"], dataset),
        source=str(payload.get("source") or "AKSHARE"),
        actor=str(payload.get("actor") or "UNKNOWN"),
        status=cast(
            Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED"],
            raw_status,
        ),
        task_status=cast(Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED"] | None, raw_task_status),
        requested_count=raw_requested_count,
        success_count=raw_success_count if isinstance(raw_success_count, int) else None,
        failure_count=raw_failure_count if isinstance(raw_failure_count, int) else None,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        items=[item for item in raw_items if isinstance(item, dict)]
        if isinstance(raw_items, list)
        else [],
        failure=failure,
    )


@router.post(
    "/funds/{fund_id}/ingestions",
    operation_id="submitFundIngestion",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TypedEnvelope[FundIngestionSubmissionModel],
)
def submit_fund_ingestion(
    fund_id: str,
    request: Request,
    payload: FundIngestionRequest = Body(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    if not principal.can_manage_data_ingestion:
        raise ForbiddenError("Data ingestion permission is required")
    if not getattr(request.app.state, "persistent_operations", False):
        raise ServiceUnavailableError("Durable data ingestion workers are not enabled")
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.models.fund import Fund, FundShareClass, ProviderFundIdentity
    from fip.services.data_service.models.governance import AuditLog, DataProvider

    session = _session(request)
    try:
        fund = session.scalar(select(Fund).where(Fund.fund_code == fund_id))
        if fund is None:
            raise NotFoundError("fund", fund_id)
        mappings = session.execute(
            select(FundShareClass.id, ProviderFundIdentity.provider_fund_id)
            .join(ProviderFundIdentity, ProviderFundIdentity.share_class_id == FundShareClass.id)
            .join(DataProvider, DataProvider.id == ProviderFundIdentity.provider_id)
            .where(
                FundShareClass.fund_id == fund.id,
                DataProvider.provider_code == AkShareSourceAdapter.provider_code,
                ProviderFundIdentity.valid_to.is_(None),
            )
            .order_by(FundShareClass.share_class_code, ProviderFundIdentity.provider_fund_id)
        ).all()
        if not mappings:
            raise ConflictError("Fund has no active AKShare share-class identity")
        if payload.dataset == "BASIC_INFO":
            mappings = mappings[:1]

        job_type = (
            "fund_basic_info_ingest" if payload.dataset == "BASIC_INFO" else "fund_nav_ingest"
        )
        scoped_key = (
            f"fund-ingestion|{principal.user_id}|{idempotency_key}|{fund_id}|{payload.dataset}"
        )
        existing = session.execute(
            select(CalculationJob).where(CalculationJob.idempotency_key == scoped_key)
        ).scalar_one_or_none()
        job = JobSubmitter(session).submit(
            job_type=job_type,
            idempotency_key=scoped_key,
            resource_id=fund_id,
            result_ref="/api/v1/ingestions/{operation_id}",
            job_payload={
                "dataset": payload.dataset,
                "source": AkShareSourceAdapter.provider_code,
                "actor": principal.user_id,
                "subjects": [
                    {
                        "fund_id": fund.id,
                        "public_fund_id": fund_id,
                        "share_class_id": int(share_class_id),
                        "symbol": str(symbol),
                    }
                    for share_class_id, symbol in mappings
                ],
                "fund_ids": [fund_id],
            },
        )
        if existing is None:
            job.result_ref = f"/api/v1/ingestions/{job.execution_id}"
            session.add(
                AuditLog(
                    resource_type="fund_ingestion",
                    resource_id=job.execution_id,
                    action="SUBMITTED",
                    operator=principal.user_id,
                    detail={
                        "fund_id": fund_id,
                        "dataset": payload.dataset,
                        "share_class_count": len(mappings),
                    },
                )
            )
        session.commit()
        model = FundIngestionSubmissionModel(
            operation_id=job.execution_id,
            fund_id=fund_id,
            dataset=payload.dataset,
            fund_ids=[fund_id],
            status=cast(
                Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED"],
                job.status,
            ),
        )
        return success(model.model_dump(mode="json"), request_id=request.state.request_id)
    finally:
        session.close()


@router.get(
    "/funds/{fund_id}/basic-info-history",
    operation_id="getFundBasicInfoHistory",
    response_model=TypedEnvelope[list[FundBasicInfoHistoryModel]],
)
def get_fund_basic_info_history(
    fund_id: str,
    request: Request,
    as_of_date: date | None = None,
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    from fip.services.data_service.models.fund import Fund, FundBasicInfoHistory
    from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
    from fip.services.data_service.models.raw import RawPayload

    session = _session(request)
    try:
        fund = session.scalar(select(Fund).where(Fund.fund_code == fund_id))
        if fund is None:
            raise NotFoundError("fund", fund_id)
        stmt = (
            select(FundBasicInfoHistory, DataProvider, DataProviderDataset)
            .join(RawPayload, RawPayload.id == FundBasicInfoHistory.raw_payload_id)
            .join(DataProviderDataset, DataProviderDataset.id == RawPayload.dataset_id)
            .join(DataProvider, DataProvider.id == DataProviderDataset.provider_id)
            .where(FundBasicInfoHistory.fund_id == fund.id)
        )
        if as_of_date is not None:
            visible_until = datetime.combine(as_of_date, time.max, tzinfo=UTC)
            stmt = stmt.where(FundBasicInfoHistory.available_at <= visible_until)
        rows = session.execute(
            stmt.order_by(
                FundBasicInfoHistory.available_at.desc(), FundBasicInfoHistory.version.desc()
            ).limit(limit)
        ).all()
        data = [
            FundBasicInfoHistoryModel(
                fund_id=fund_id,
                version=history.version,
                raw_fields=history.raw_fields,
                normalized_fields=history.normalized_fields,
                source=provider.provider_code,
                adapter_version=dataset.adapter_version,
                library_version=dataset.library_version,
                available_at=history.available_at,
                availability_quality=history.availability_quality,
            ).model_dump(mode="json")
            for history, provider, dataset in rows
        ]
        return success(data, request_id=request.state.request_id)
    finally:
        session.close()


@router.get(
    "/funds/{fund_id}/ingestions",
    operation_id="listFundIngestions",
    response_model=TypedEnvelope[list[FundIngestionTaskModel]],
)
def list_fund_ingestions(
    fund_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    if not getattr(request.app.state, "persistent_operations", False):
        raise ServiceUnavailableError("Durable data ingestion workers are not enabled")
    session = _session(request)
    try:
        from fip.services.data_service.models.fund import Fund

        if session.scalar(select(Fund.id).where(Fund.fund_code == fund_id)) is None:
            raise NotFoundError("fund", fund_id)
        stmt = (
            select(CalculationJob)
            .where(
                or_(
                    CalculationJob.resource_id == fund_id,
                    CalculationJob.job_payload["fund_ids"].contains([fund_id]),
                ),
                CalculationJob.job_type.in_(("fund_basic_info_ingest", "fund_nav_ingest")),
            )
            .order_by(CalculationJob.created_at.desc(), CalculationJob.id.desc())
            .limit(limit)
        )
        if not principal.can_manage_data_ingestion:
            stmt = stmt.where(CalculationJob.job_payload["actor"].astext == principal.user_id)
        jobs = session.scalars(stmt).all()
        visible = [job for job in jobs if _can_read_job(principal, job)]
        return success(
            [_task_model(job).model_dump(mode="json", exclude_none=True) for job in visible],
            request_id=request.state.request_id,
        )
    finally:
        session.close()


@router.post(
    "/fund-ingestions",
    operation_id="submitFundIngestionBatch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TypedEnvelope[FundIngestionSubmissionModel],
)
def submit_fund_ingestion_batch(
    request: Request,
    payload: FundIngestionBatchRequest = Body(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    if not principal.can_manage_data_ingestion:
        raise ForbiddenError("Data ingestion permission is required")
    if not getattr(request.app.state, "persistent_operations", False):
        raise ServiceUnavailableError("Durable data ingestion workers are not enabled")
    fund_ids = list(dict.fromkeys(payload.fund_ids))
    if not fund_ids or len(fund_ids) > 100:
        from fip.api.errors import InvalidQueryError

        raise InvalidQueryError("fund_ids must contain between 1 and 100 unique fund IDs")

    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.models.fund import Fund, FundShareClass, ProviderFundIdentity
    from fip.services.data_service.models.governance import AuditLog, DataProvider

    session = _session(request)
    try:
        funds = session.scalars(select(Fund).where(Fund.fund_code.in_(fund_ids))).all()
        found_ids = {fund.fund_code for fund in funds}
        missing = [value for value in fund_ids if value not in found_ids]
        if missing:
            raise NotFoundError("fund", ",".join(missing))
        rows = session.execute(
            select(
                Fund.fund_code, Fund.id, FundShareClass.id, ProviderFundIdentity.provider_fund_id
            )
            .join(FundShareClass, FundShareClass.fund_id == Fund.id)
            .join(ProviderFundIdentity, ProviderFundIdentity.share_class_id == FundShareClass.id)
            .join(DataProvider, DataProvider.id == ProviderFundIdentity.provider_id)
            .where(
                Fund.fund_code.in_(fund_ids),
                DataProvider.provider_code == AkShareSourceAdapter.provider_code,
                ProviderFundIdentity.valid_to.is_(None),
            )
            .order_by(Fund.fund_code, FundShareClass.share_class_code)
        ).all()
        grouped: dict[str, list[tuple[int, int, str]]] = {value: [] for value in fund_ids}
        for public_id, internal_id, share_class_id, symbol in rows:
            grouped[str(public_id)].append((int(internal_id), int(share_class_id), str(symbol)))
        missing_mappings = [value for value, entries in grouped.items() if not entries]
        if missing_mappings:
            raise ConflictError(
                "Some funds have no active AKShare share-class identity",
                {"fund_ids": missing_mappings},
            )
        subjects: list[dict[str, int | str]] = []
        for public_id in fund_ids:
            entries = grouped[public_id]
            if payload.dataset == "BASIC_INFO":
                entries = entries[:1]
            subjects.extend(
                {
                    "fund_id": internal_id,
                    "public_fund_id": public_id,
                    "share_class_id": share_class_id,
                    "symbol": symbol,
                }
                for internal_id, share_class_id, symbol in entries
            )
        canonical = ",".join(sorted(fund_ids))
        scoped_key = (
            f"fund-ingestion-batch|{principal.user_id}|{idempotency_key}|"
            f"{payload.dataset}|{canonical}"
        )
        job_type = (
            "fund_basic_info_ingest" if payload.dataset == "BASIC_INFO" else "fund_nav_ingest"
        )
        existing = session.execute(
            select(CalculationJob).where(CalculationJob.idempotency_key == scoped_key)
        ).scalar_one_or_none()
        job = JobSubmitter(session).submit(
            job_type=job_type,
            idempotency_key=scoped_key,
            resource_id="BATCH",
            result_ref="/api/v1/ingestions/{operation_id}",
            job_payload={
                "dataset": payload.dataset,
                "source": AkShareSourceAdapter.provider_code,
                "actor": principal.user_id,
                "fund_ids": fund_ids,
                "subjects": subjects,
            },
        )
        if existing is None:
            job.result_ref = f"/api/v1/ingestions/{job.execution_id}"
            session.add(
                AuditLog(
                    resource_type="fund_ingestion",
                    resource_id=job.execution_id,
                    action="SUBMITTED",
                    operator=principal.user_id,
                    detail={
                        "fund_ids": fund_ids,
                        "dataset": payload.dataset,
                        "share_class_count": len(subjects),
                    },
                )
            )
        session.commit()
        model = FundIngestionSubmissionModel(
            operation_id=job.execution_id,
            fund_id="BATCH",
            fund_ids=fund_ids,
            dataset=payload.dataset,
            status=cast(
                Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED"],
                job.status,
            ),
        )
        return success(model.model_dump(mode="json"), request_id=request.state.request_id)
    finally:
        session.close()


@router.get(
    "/ingestions/{operation_id}",
    operation_id="getFundIngestion",
    response_model=TypedEnvelope[FundIngestionTaskModel],
)
def get_fund_ingestion(
    operation_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    if not getattr(request.app.state, "persistent_operations", False):
        raise ServiceUnavailableError("Durable data ingestion workers are not enabled")
    session = _session(request)
    try:
        job = session.execute(
            select(CalculationJob).where(
                CalculationJob.execution_id == operation_id,
                CalculationJob.job_type.in_(("fund_basic_info_ingest", "fund_nav_ingest")),
            )
        ).scalar_one_or_none()
        if job is None:
            raise NotFoundError("fund ingestion", operation_id)
        if not _can_read_job(principal, job):
            raise ForbiddenError()
        return success(
            _task_model(job).model_dump(mode="json", exclude_none=True),
            request_id=request.state.request_id,
        )
    finally:
        session.close()
