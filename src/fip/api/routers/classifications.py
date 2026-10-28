"""Five dimensional classification dictionary, PIT history and review commands."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.api.auth import get_principal
from fip.api.classification_policy import get_classification_policy
from fip.api.context import Principal
from fip.api.contracts import success
from fip.api.dependencies import get_api_repositories
from fip.api.errors import ConflictError, ForbiddenError, InvalidQueryError, NotFoundError
from fip.api.repositories import ApiRepositories
from fip.api.schemas import TypedEnvelope
from fip.platform.decision_data.pit import visible_until_for
from fip.services.data_service.classification import ClassificationSnapshot
from fip.services.data_service.classification.service import (
    ClassificationConflict,
    ClassificationService,
    ReviewDecision,
    StrategyTagDecision,
)
from fip.services.data_service.models.fund import (
    FundClassificationHistory,
    FundClassificationReviewCase,
)
from fip.services.data_service.repositories.classification import SqlClassificationPitRepository

# ruff: noqa: B008
router = APIRouter()


class CatalogPayload(BaseModel):
    scheme: str
    dimensions: dict[str, list[str]]
    statuses: list[str]
    confidence_grades: dict[str, str]
    active_dimensions: list[str]
    paused_dimensions: list[str]
    strategy_tags: list[str]


class ClassificationHistoryInterval(BaseModel):
    valid_from: str
    valid_to: str | None
    classification: ClassificationSnapshot
    trading_eligibility: dict[str, Any] | None


class ClassificationHistoryPayload(BaseModel):
    revision_id: int
    version: int
    available_at: str
    classified_at: str
    actor: str
    reason: str
    reviewed: bool
    intervals: list[ClassificationHistoryInterval]
    published_at: str | None = None
    provider_available_at: str | None = None
    ingested_at: str | None = None
    availability_quality: str | None = None


class ReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(gt=0)
    decisions: dict[str, ReviewDecision]
    reason: str = Field(min_length=1, max_length=1024)
    tag_decisions: dict[str, StrategyTagDecision] = Field(default_factory=dict)


class ReviewOutcome(BaseModel):
    revision_id: int
    version: int
    case_id: int


class ReviewCasePayload(BaseModel):
    case_id: int
    fund_id: int
    expected_revision: int
    issue_type: str
    status: str
    details: dict[str, Any]
    created_at: str
    resolved_at: str | None
    result_revision_id: int | None
    baseline: ClassificationSnapshot | None = None
    incoming: ClassificationSnapshot | None = None
    active_scope: list[str]
    historical_scope: list[str]
    evaluation_state: Literal["NOT_EVALUATED", "EVALUATED", "PAUSED"] | None = None


def _session(repositories: ApiRepositories) -> Session:
    session = repositories.funds.session
    if not isinstance(session, Session):
        raise InvalidQueryError("Classification persistence is unavailable")
    return session


def _view(
    case: FundClassificationReviewCase, cutoff: dt.datetime, session: Session
) -> ReviewCasePayload:
    resolved = case.resolved_at if case.resolved_at and case.resolved_at <= cutoff else None
    rows = list(
        session.scalars(
            select(FundClassificationHistory)
            .where(FundClassificationHistory.revision_id == case.revision_id)
            .order_by(FundClassificationHistory.valid_from)
        )
    )
    target = case.details.get("valid_from")
    baseline = next(
        (
            r.classification_result
            for r in rows
            if not target
            or (
                r.valid_from <= dt.date.fromisoformat(target)
                and (r.valid_to is None or dt.date.fromisoformat(target) < r.valid_to)
            )
        ),
        None,
    )
    incoming_intervals = case.details.get("intervals", [])
    incoming = incoming_intervals[0][2] if incoming_intervals else None
    source_scope = case.details.get("source_dimensions") or [case.details.get("dimension")]
    source_scope = [name for name in source_scope if isinstance(name, str)]
    paused = case.details.get("evaluation_state") == "PAUSED"
    active_scope = case.details.get("active_scope", [] if paused else source_scope)
    historical_scope = case.details.get("historical_source_dimensions", [])
    historical_scope = sorted(set(historical_scope) | (set(source_scope) - set(active_scope)))
    return ReviewCasePayload(
        active_scope=active_scope,
        historical_scope=historical_scope,
        evaluation_state=case.details.get("evaluation_state"),
        baseline=ClassificationSnapshot.model_validate(baseline) if baseline else None,
        incoming=ClassificationSnapshot.model_validate(incoming) if incoming else None,
        case_id=case.id,
        fund_id=case.fund_id,
        expected_revision=case.revision_id,
        issue_type=case.issue_type,
        status=case.status if resolved else "PENDING",
        details=case.details,
        created_at=case.created_at.isoformat(),
        resolved_at=resolved.isoformat() if resolved else None,
        result_revision_id=case.result_revision_id if resolved else None,
    )


@router.get(
    "/fund-classifications/catalog",
    operation_id="getClassificationCatalog",
    response_model=TypedEnvelope[CatalogPayload],
)
def catalog(
    request: Request,
) -> dict[str, Any]:
    if {"rule_version", "enum_version"}.intersection(request.query_params):
        raise InvalidQueryError("Classification catalogs use the single current ruleset")
    policy = get_classification_policy()
    return success(
        CatalogPayload(
            scheme=policy.scheme,
            dimensions={k: list(v) for k, v in policy.catalog.items()},
            active_dimensions=list(policy.active_dimensions),
            paused_dimensions=list(policy.paused_dimensions),
            strategy_tags=list(policy.strategy_tag_catalog),
            statuses=["CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"],
            confidence_grades={
                "OFFICIAL_DOCUMENT": "官方产品资料或名录",
                "PUBLIC_AGGREGATOR": "公开聚合资料字段",
                "NAME_HINT": "仅名称线索，需复核",
            },
        ).model_dump(),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/funds/{fund_id}/classification-history",
    operation_id="getClassificationHistory",
    response_model=TypedEnvelope[list[ClassificationHistoryPayload]],
)
def history(
    fund_id: str,
    request: Request,
    decision_at: dt.date | None = None,
    repositories: ApiRepositories = Depends(get_api_repositories),
) -> dict[str, Any]:
    fund, _ = repositories.funds._required_share_class(fund_id)
    cutoff = visible_until_for(decision_at) if decision_at else dt.datetime.now(dt.UTC)
    data = SqlClassificationPitRepository(_session(repositories), cutoff).history(fund.id)
    return success(
        data,
        request_id=getattr(request.state, "request_id", None),
        is_point_in_time=decision_at is not None,
        as_of_date=(decision_at or cutoff.date()).isoformat(),
    )


@router.get(
    "/classification-reviews",
    operation_id="listClassificationReviews",
    response_model=TypedEnvelope[list[ReviewCasePayload]],
)
def list_reviews(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    status: str | None = "PENDING",
    decision_at: dt.date | None = None,
    scope: Literal["ACTIVE", "HISTORY"] = "ACTIVE",
    repositories: ApiRepositories = Depends(get_api_repositories),
) -> dict[str, Any]:
    if status not in {None, "PENDING", "RESOLVED", "SUPERSEDED"}:
        raise InvalidQueryError("Invalid review status")
    cutoff = visible_until_for(decision_at) if decision_at else dt.datetime.now(dt.UTC)
    rows = (
        _session(repositories)
        .scalars(
            select(FundClassificationReviewCase)
            .where(
                FundClassificationReviewCase.created_at <= cutoff,
            )
            .order_by(FundClassificationReviewCase.id)
        )
        .all()
    )
    views = [_view(row, cutoff, _session(repositories)) for row in rows]
    if scope == "ACTIVE":
        views = [v for v in views if v.evaluation_state != "PAUSED"]
    views = [v for v in views if status is None or v.status == status]
    total = len(views)
    return success(
        [v.model_dump() for v in views[(page - 1) * page_size : page * page_size]],
        request_id=getattr(request.state, "request_id", None),
        pagination={
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@router.get(
    "/classification-reviews/{case_id}",
    operation_id="getClassificationReview",
    response_model=TypedEnvelope[ReviewCasePayload],
)
def get_review(
    case_id: int,
    request: Request,
    decision_at: dt.date | None = None,
    repositories: ApiRepositories = Depends(get_api_repositories),
) -> dict[str, Any]:
    cutoff = visible_until_for(decision_at) if decision_at else dt.datetime.now(dt.UTC)
    case = _session(repositories).get(FundClassificationReviewCase, case_id)
    if case is None or case.created_at > cutoff:
        raise NotFoundError("classification review", str(case_id))
    return success(
        _view(case, cutoff, _session(repositories)).model_dump(),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/classification-reviews/{case_id}/review",
    operation_id="reviewClassification",
    response_model=TypedEnvelope[ReviewOutcome],
)
def review(
    case_id: int,
    body: ReviewSubmission,
    request: Request,
    repositories: ApiRepositories = Depends(get_api_repositories),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    if not principal.can_review_classifications:
        raise ForbiddenError("Classification review capability required")
    session = _session(repositories)
    try:
        revision = ClassificationService(session).review(
            case_id,
            expected_revision=body.expected_revision,
            decisions=body.decisions,
            tag_decisions=body.tag_decisions,
            actor=principal.user_id,
            reason=body.reason,
            can_review=principal.can_review_classifications,
        )
        data = ReviewOutcome(revision_id=revision.id, version=revision.version, case_id=case_id)
        session.commit()
    except ClassificationConflict as exc:
        session.rollback()
        raise ConflictError(str(exc)) from exc
    except LookupError as exc:
        session.rollback()
        raise NotFoundError("classification review", str(case_id)) from exc
    except ValueError as exc:
        session.rollback()
        raise InvalidQueryError(str(exc)) from exc
    return success(data.model_dump(), request_id=getattr(request.state, "request_id", None))
